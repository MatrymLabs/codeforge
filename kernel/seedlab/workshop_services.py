"""Authoritative service projection for the Creator Workshop.

The in-world Workshop remains a presentation layer. This module supplies the real
catalog, governed drafts, bounded jobs, durable records, typed events, and audit
correlation that a future text, native, or Console projection can call.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kernel.event_envelope import EventEnvelope
from kernel.hardware import Part, load_catalog
from kernel.hardware_activation import ActivationApproval, ActivationApprovalLedger
from kernel.hardware_runtime import HardwareRuntimeController, HardwareRuntimeError
from kernel.permission_policy import PermissionDenied, PermissionPolicy
from kernel.seedlab.approval import ApprovalStore, FileApprovalStore
from kernel.seedlab.creator_draft import CreatorDraft, CreatorDraftStore, FileCreatorDraftStore
from kernel.seedlab.event_bridge import publish_seed_event
from kernel.seedlab.event_replay import EventReplayStore, FileEventReplayStore
from kernel.seedlab.jobs import (
    DEFAULT_TIMEOUT,
    OUTPUT_CAP,
    FileJobStore,
    InMemoryJobStore,
    JobError,
    JobRecord,
    JobRunner,
    JobStore,
)
from kernel.seedlab.project_model import Provenance
from kernel.seedlab.source_connector import LocalSource
from kernel.session_identity import SessionIdentity, SessionIdentityError


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class CreatorWorkshopService:
    """The governed Workshop application service.

    Pass file-backed stores for a durable deployment. Defaults are deliberately volatile
    so isolated experiments cannot silently write production state.
    """

    drafts: CreatorDraftStore
    jobs: JobStore
    event_publisher: Callable[[EventEnvelope], None]
    replay_store: EventReplayStore | None
    approval_store: ApprovalStore | None
    hardware_runtime: HardwareRuntimeController[object] | None

    def __init__(
        self,
        *,
        drafts: CreatorDraftStore | None = None,
        jobs: JobStore | None = None,
        event_publisher: Callable[[EventEnvelope], None] | None = None,
        replay_store: EventReplayStore | None = None,
        approval_store: ApprovalStore | None = None,
        hardware_runtime: HardwareRuntimeController[object] | None = None,
    ) -> None:
        self.drafts = drafts or CreatorDraftStore()
        self.jobs = jobs or InMemoryJobStore()
        self.replay_store = replay_store
        self.approval_store = approval_store
        self.hardware_runtime = hardware_runtime
        self.event_publisher = event_publisher or self._publish_event

    def _publish_event(self, event: EventEnvelope) -> None:
        if self.replay_store is not None:
            self.replay_store.append(event)
        if self.hardware_runtime is not None:
            self.hardware_runtime.publish_event(event, publish_seed_event)
        else:
            publish_seed_event(event)

    def activate_hardware(
        self,
        component_id: str,
        *,
        approval: ActivationApproval,
        ledger: ActivationApprovalLedger,
        identity: SessionIdentity,
        policy: PermissionPolicy,
        now: datetime | None = None,
        artifact_digest: str = "",
    ) -> None:
        """Activate Hardware through the same service used by Workshop projections."""
        if self.hardware_runtime is None:
            raise HardwareRuntimeError("Creator Workshop has no configured Hardware runtime")
        self.hardware_runtime.activate(
            component_id,
            approval=approval,
            ledger=ledger,
            identity=identity,
            policy=policy,
            now=now,
            artifact_digest=artifact_digest,
        )

    @classmethod
    def durable(
        cls,
        root: Path,
        *,
        hardware_runtime: HardwareRuntimeController[object] | None = None,
    ) -> CreatorWorkshopService:
        """Construct an explicitly durable Workshop service under ``root``."""
        root = Path(root)
        return cls(
            drafts=FileCreatorDraftStore(root / "drafts.json"),
            jobs=FileJobStore(root / "jobs"),
            replay_store=FileEventReplayStore(root / "events.jsonl"),
            approval_store=FileApprovalStore(root / "approvals"),
            hardware_runtime=hardware_runtime,
        )

    def shelf(self) -> tuple[Part, ...]:
        """Return the authoritative Hardware Store catalog, without source activation."""
        return tuple(load_catalog())

    def create_draft(
        self, draft_id: str, seed_id: str, owner_id: str, payload: Mapping[str, object]
    ) -> CreatorDraft:
        return self.drafts.create(CreatorDraft(draft_id, seed_id, owner_id, dict(payload)))

    def edit_draft(
        self, draft_id: str, actor_id: str, changes: Mapping[str, object]
    ) -> CreatorDraft:
        draft = self.drafts.get(draft_id).edit(actor_id, changes)
        return self.drafts.save(draft)

    def transition_draft(self, draft_id: str, target: str, actor_id: str) -> CreatorDraft:
        draft = self.drafts.get(draft_id).transition(target, actor_id)
        return self.drafts.save(draft)

    def _run(
        self,
        kind: str,
        source_root: Path,
        *,
        seed_id: str,
        actor_id: str,
        profile: str,
        source_id: str,
        source_license: str,
        source_visibility: str = "private",
        allowed_use: str = "internal CodeForge testing",
        allowlist: dict[str, list[str]] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        cap: int = OUTPUT_CAP,
        retries: int = 0,
        cancel_check: Callable[[], bool] | None = None,
        identity: SessionIdentity | None = None,
        policy: PermissionPolicy | None = None,
        approval_store: ApprovalStore | None = None,
        approval_id: str = "",
        approval_evidence_digest: str = "",
        activity_id: str = "",
        idempotency_key: str = "",
        clock: Callable[[], str] = _utcnow,
    ) -> JobRecord:
        if not source_license.strip():
            raise ValueError("source_license is required before a Workshop job may run")
        if (identity is None) != (policy is None):
            raise ValueError("identity and policy must be supplied together")
        if identity is not None:
            try:
                identity.require_seed(seed_id)
            except SessionIdentityError as exc:
                raise PermissionDenied(str(exc)) from exc
            if identity.principal_id != actor_id:
                raise ValueError("actor_id must match the authenticated principal")
        source = LocalSource(
            Path(source_root),
            Provenance(
                source_id,
                owner=actor_id,
                license=source_license,
                visibility=source_visibility,
                allowed_use=allowed_use,
            ),
        )
        resolved_idempotency_key = idempotency_key.strip() or (
            f"{kind}:{seed_id}:{source_id}:{profile}"
        )
        request_fingerprint = _job_request_fingerprint(
            kind=kind,
            seed_id=seed_id,
            actor_id=actor_id,
            profile=profile,
            source_root=source_root,
            source_id=source_id,
            source_license=source_license,
            allowlist=allowlist,
            timeout=timeout,
            cap=cap,
            activity_id=activity_id,
            approval_id=approval_id,
            approval_evidence_digest=approval_evidence_digest,
        )
        existing = _latest_idempotent_job(self.jobs.for_seed(seed_id), resolved_idempotency_key)
        if existing is not None:
            if (
                existing.requested_by != actor_id
                or existing.kind != kind
                or existing.profile != profile
            ):
                raise JobError("idempotency key was reused with different job intent")
            if existing.request_fingerprint and existing.request_fingerprint != request_fingerprint:
                raise JobError("idempotency key was reused with different request fingerprint")
            if activity_id and existing.activity_id and existing.activity_id != activity_id:
                raise JobError("idempotency key was reused with different activity")
            return existing
        runner = JobRunner(
            source,
            seed_id=seed_id,
            requested_by=actor_id,
            clock=clock,
            cancel_check=cancel_check,
            identity=identity,
            policy=policy,
            correlation_id=identity.correlation_id if identity else "",
            activity_id=activity_id,
            idempotency_key=resolved_idempotency_key,
            request_fingerprint=request_fingerprint,
            checkpoint=self.jobs.save,
            approval_store=approval_store or self.approval_store,
            approval_id=approval_id,
            approval_evidence_digest=approval_evidence_digest,
        )
        job = (
            runner.test(profile, allowlist=allowlist, timeout=timeout, cap=cap)
            if kind == "test"
            else runner.build(profile, allowlist=allowlist, timeout=timeout, cap=cap)
        )
        self.jobs.save(job)
        self.event_publisher(job.event())
        if retries < 0:
            raise ValueError("retries must not be negative")
        for _ in range(retries):
            if job.ok or job.status == "waiting_approval":
                break
            job = runner.retry(job, allowlist=allowlist, timeout=timeout, cap=cap)
            self.jobs.save(job)
            self.event_publisher(job.event())
        return job

    def run_test(self, source_root: Path, **kwargs: object) -> JobRecord:
        """Run and persist one bounded TestJob, then publish its typed completion event."""
        return self._run("test", source_root, **kwargs)  # type: ignore[arg-type]

    def run_build(self, source_root: Path, **kwargs: object) -> JobRecord:
        """Run and persist one bounded BuildJob, then publish its typed completion event."""
        return self._run("build", source_root, **kwargs)  # type: ignore[arg-type]

    def jobs_for_seed(self, seed_id: str) -> tuple[JobRecord, ...]:
        return self.jobs.for_seed(seed_id)


def _latest_idempotent_job(jobs: tuple[JobRecord, ...], key: str) -> JobRecord | None:
    """Return the latest durable attempt for an idempotency key, if one exists."""
    matches = [job for job in jobs if job.idempotency_key == key]
    if not matches:
        return None
    return max(matches, key=lambda job: (job.attempt, job.created_at, job.job_id))


def _job_request_fingerprint(
    *,
    kind: str,
    seed_id: str,
    actor_id: str,
    profile: str,
    source_root: Path,
    source_id: str,
    source_license: str,
    allowlist: dict[str, list[str]] | None,
    timeout: float,
    cap: int,
    activity_id: str,
    approval_id: str,
    approval_evidence_digest: str,
) -> str:
    payload = {
        "kind": kind,
        "seed_id": seed_id,
        "actor_id": actor_id,
        "profile": profile,
        "source_root": str(Path(source_root).resolve()),
        "source_id": source_id,
        "source_license": source_license,
        "allowlist": allowlist or {},
        "timeout": timeout,
        "cap": cap,
        "activity_id": activity_id,
        "approval_id": approval_id,
        "approval_evidence_digest": approval_evidence_digest,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
