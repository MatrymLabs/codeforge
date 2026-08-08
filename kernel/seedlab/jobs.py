"""Governed BuildJob and TestJob records over the existing bounded tool runner."""

from __future__ import annotations

import json
import re
import secrets
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from kernel.event_envelope import EventEnvelope
from kernel.permission_policy import PermissionDenied, PermissionPolicy
from kernel.seedlab.approval import ApprovalError, ApprovalStore
from kernel.seedlab.source_connector import LocalSource
from kernel.seedlab.tool_runner import DEFAULT_TIMEOUT, OUTPUT_CAP, ToolRunResult, run_tool
from kernel.session_identity import SessionIdentity
from kernel.session_registry import SessionRegistry
from kernel.shelf.atomic_write import atomic_write_text

JobKind = Literal["build", "test"]
(
    CREATED,
    RUNNING,
    WAITING_APPROVAL,
    SUCCEEDED,
    FAILED,
    TIMED_OUT,
    CANCELLED,
    ENVIRONMENT_UNAVAILABLE,
    ERROR,
) = (
    "created",
    "running",
    "waiting_approval",
    "succeeded",
    "failed",
    "timed_out",
    "cancelled",
    "environment_unavailable",
    "error",
)


class JobError(ValueError):
    """A job request is invalid."""


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    seed_id: str
    requested_by: str
    kind: JobKind
    profile: str
    status: str
    created_at: str
    finished_at: str = ""
    result: ToolRunResult | None = None
    attempt: int = 1
    retry_of: str = ""
    correlation_id: str = ""
    activity_id: str = ""
    idempotency_key: str = ""
    request_fingerprint: str = ""
    outcome_reason: str = ""

    @property
    def ok(self) -> bool:
        return self.status == SUCCEEDED

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        return value

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> JobRecord:
        """Restore durable job evidence and reject malformed records."""
        try:
            result = raw.get("result")
            parsed_result = ToolRunResult.from_dict(result) if isinstance(result, dict) else None
            kind = str(raw["kind"])
            if kind not in ("build", "test"):
                raise ValueError(f"unknown job kind: {kind}")
            attempt = raw.get("attempt", 1)
            if not isinstance(attempt, int):
                raise TypeError("attempt must be an integer")
            return cls(
                job_id=str(raw["job_id"]),
                seed_id=str(raw["seed_id"]),
                requested_by=str(raw["requested_by"]),
                kind=kind,  # type: ignore[arg-type]
                profile=str(raw["profile"]),
                status=str(raw["status"]),
                created_at=str(raw["created_at"]),
                finished_at=str(raw.get("finished_at", "")),
                result=parsed_result,
                attempt=attempt,
                retry_of=str(raw.get("retry_of", "")),
                correlation_id=str(raw.get("correlation_id", "")),
                activity_id=str(raw.get("activity_id", "")),
                idempotency_key=str(raw.get("idempotency_key", "")),
                request_fingerprint=str(raw.get("request_fingerprint", "")),
                outcome_reason=str(raw.get("outcome_reason", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise JobError(f"malformed persisted job: {exc}") from exc

    def event(self) -> EventEnvelope:
        """Build a typed completion event with both fallbacks."""
        if self.status == RUNNING:
            raise JobError("cannot emit a completion event for a running job")
        event_type = (
            f"{self.kind}.awaiting_approval"
            if self.status == WAITING_APPROVAL
            else f"{self.kind}.cancelled"
            if self.status == CANCELLED
            else f"{self.kind}.completed"
        )
        text = (
            f"{self.kind.title()} job {self.job_id} passed."
            if self.ok
            else f"{self.kind.title()} job {self.job_id} did not pass."
        )
        summary = (
            "The job is waiting for an independent human approval."
            if self.status == WAITING_APPROVAL
            else f"The {self.kind} job passed."
            if self.ok
            else f"The {self.kind} job failed or timed out."
        )
        return EventEnvelope(
            protocol="codeforge.seed",
            version="1.0",
            event_id=f"evt-{self.job_id}",
            seed_id=self.seed_id,
            session_id=self.requested_by,
            event_type=event_type,
            timestamp=self.finished_at,
            classification="internal",
            payload={
                "job_id": self.job_id,
                "kind": self.kind,
                "status": self.status,
                "profile": self.profile,
                "exit_code": self.result.exit_code if self.result else None,
            },
            text_fallback=text,
            accessibility_summary=summary,
            correlation_id=self.correlation_id or self.job_id,
            localization_key=f"{self.kind}.completed",
            semantic_channel=self.kind,
        )


class JobRunner:
    """Execute only named, bounded profiles inside an approved LocalSource."""

    def __init__(
        self,
        source: LocalSource,
        *,
        seed_id: str,
        requested_by: str,
        clock: Callable[[], str] = _utcnow,
        id_minter: Callable[[str], str] | None = None,
        cancel_check: Callable[[], bool] | None = None,
        identity: SessionIdentity | None = None,
        policy: PermissionPolicy | None = None,
        session_registry: SessionRegistry | None = None,
        correlation_id: str = "",
        activity_id: str = "",
        idempotency_key: str = "",
        request_fingerprint: str = "",
        checkpoint: Callable[[JobRecord], None] | None = None,
        approval_store: ApprovalStore | None = None,
        approval_id: str = "",
        approval_evidence_digest: str = "",
    ) -> None:
        if (identity is None) != (policy is None):
            raise PermissionDenied("identity and policy must be supplied together")
        if identity is not None and identity.principal_id != requested_by:
            raise PermissionDenied("requested_by must match the authenticated principal")
        self.source = source
        self.seed_id = seed_id
        self.requested_by = requested_by
        self.clock = clock
        self.id_minter = id_minter or (lambda kind: f"job-{kind}-{secrets.token_hex(4)}")
        self.cancel_check = cancel_check or (lambda: False)
        self.identity = identity
        self.policy = policy
        self.session_registry = session_registry
        self.correlation_id = correlation_id.strip()
        self.activity_id = activity_id.strip()
        self.idempotency_key = idempotency_key.strip()
        self.request_fingerprint = request_fingerprint.strip()
        self.checkpoint = checkpoint
        if approval_id and approval_store is None:
            raise ApprovalError("approval_store is required when approval_id is supplied")
        if approval_id and (identity is None or policy is None):
            raise PermissionDenied(
                "approval execution requires an authenticated identity and policy"
            )
        self.approval_store = approval_store
        self.approval_id = approval_id.strip()
        self.approval_evidence_digest = approval_evidence_digest.strip()

    def build(
        self,
        profile: str = "python-build",
        *,
        allowlist: dict[str, list[str]] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        cap: int = OUTPUT_CAP,
    ) -> JobRecord:
        return self._run("build", profile, allowlist=allowlist, timeout=timeout, cap=cap)

    def test(
        self,
        profile: str = "pytest",
        *,
        allowlist: dict[str, list[str]] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        cap: int = OUTPUT_CAP,
    ) -> JobRecord:
        return self._run("test", profile, allowlist=allowlist, timeout=timeout, cap=cap)

    def retry(
        self,
        previous: JobRecord,
        *,
        allowlist: dict[str, list[str]] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        cap: int = OUTPUT_CAP,
    ) -> JobRecord:
        """Retry a failed/timed-out/cancelled job as a new auditable attempt."""
        if previous.ok:
            raise JobError("successful jobs cannot be retried")
        return self._run(
            previous.kind,
            previous.profile,
            allowlist=allowlist,
            timeout=timeout,
            cap=cap,
            attempt=previous.attempt + 1,
            retry_of=previous.job_id,
        )

    def _run(
        self,
        kind: JobKind,
        profile: str,
        *,
        allowlist: dict[str, list[str]] | None,
        timeout: float,
        cap: int,
        attempt: int = 1,
        retry_of: str = "",
    ) -> JobRecord:
        job_id = self.id_minter(kind)
        created = self.clock()
        activity_id = self.activity_id or f"activity-{job_id}"
        idempotency_key = self.idempotency_key or (
            f"{kind}:{self.seed_id}:{self.source.provenance.source_id}:{profile}"
        )
        if self.cancel_check():
            return JobRecord(
                job_id=job_id,
                seed_id=self.seed_id,
                requested_by=self.requested_by,
                kind=kind,
                profile=profile,
                status=CANCELLED,
                created_at=created,
                finished_at=self.clock(),
                attempt=attempt,
                retry_of=retry_of,
                correlation_id=self.correlation_id,
                activity_id=activity_id,
                idempotency_key=idempotency_key,
                request_fingerprint=self.request_fingerprint,
            )
        if self.approval_store is not None and self.approval_id:
            try:
                self.approval_store.consume(
                    self.approval_id,
                    identity=self.identity,  # type: ignore[arg-type]
                    policy=self.policy,  # type: ignore[arg-type]
                    job_id=job_id,
                    activity_id=activity_id,
                    evidence_digest=self.approval_evidence_digest,
                )
            except ApprovalError as exc:
                pending = self.approval_store.get(self.approval_id).status == "pending"
                waiting = JobRecord(
                    job_id=job_id,
                    seed_id=self.seed_id,
                    requested_by=self.requested_by,
                    kind=kind,
                    profile=profile,
                    status=WAITING_APPROVAL if pending else FAILED,
                    created_at=created,
                    finished_at=self.clock(),
                    attempt=attempt,
                    retry_of=retry_of,
                    correlation_id=self.correlation_id,
                    activity_id=activity_id,
                    idempotency_key=idempotency_key,
                    request_fingerprint=self.request_fingerprint,
                    outcome_reason=str(exc),
                )
                if self.checkpoint is not None:
                    self.checkpoint(waiting)
                return waiting
        running = JobRecord(
            job_id=job_id,
            seed_id=self.seed_id,
            requested_by=self.requested_by,
            kind=kind,
            profile=profile,
            status=RUNNING,
            created_at=created,
            attempt=attempt,
            retry_of=retry_of,
            correlation_id=self.correlation_id,
            activity_id=activity_id,
            idempotency_key=idempotency_key,
            request_fingerprint=self.request_fingerprint,
        )
        if self.checkpoint is not None:
            self.checkpoint(running)
        result = run_tool(
            self.source,
            profile,
            seed_id=self.seed_id,
            kind=kind,
            allowlist=allowlist,
            timeout=timeout,
            cap=cap,
            clock=self.clock,
            identity=self.identity,
            policy=self.policy,
            session_registry=self.session_registry,
            correlation_id=self.correlation_id,
            cancel_check=self.cancel_check,
        )
        status = (
            CANCELLED
            if result.cancelled
            else TIMED_OUT
            if result.timed_out
            else ENVIRONMENT_UNAVAILABLE
            if result.exit_code == 127
            else SUCCEEDED
            if result.ok
            else FAILED
        )
        return JobRecord(
            job_id=job_id,
            seed_id=self.seed_id,
            requested_by=self.requested_by,
            kind=kind,
            profile=profile,
            status=status,
            created_at=created,
            finished_at=result.when,
            result=result,
            attempt=attempt,
            retry_of=retry_of,
            correlation_id=self.correlation_id,
            activity_id=activity_id,
            idempotency_key=idempotency_key,
            request_fingerprint=self.request_fingerprint,
        )


class JobStore(Protocol):
    """Persistence seam for governed BuildJob and TestJob evidence."""

    def save(self, job: JobRecord) -> None: ...

    def get(self, job_id: str) -> JobRecord: ...

    def for_seed(self, seed_id: str) -> tuple[JobRecord, ...]: ...


@dataclass
class InMemoryJobStore:
    """Volatile job store for isolated tests and non-durable experiments."""

    _jobs: dict[str, JobRecord]

    def __init__(self) -> None:
        self._jobs = {}

    def save(self, job: JobRecord) -> None:
        self._jobs[job.job_id] = job

    def get(self, job_id: str) -> JobRecord:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise JobError(f"unknown job: {job_id}") from exc

    def for_seed(self, seed_id: str) -> tuple[JobRecord, ...]:
        return tuple(job for job in self._jobs.values() if job.seed_id == seed_id)


_SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass
class FileJobStore:
    """One immutable JSON record per job, surviving a Workshop/Seed restart."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path:
        if not _SAFE_JOB_ID.fullmatch(job_id):
            raise JobError(f"unsafe job id: {job_id!r}")
        return self.root / f"{job_id}.json"

    def save(self, job: JobRecord) -> None:
        atomic_write_text(
            self._path(job.job_id),
            json.dumps(job.to_dict(), indent=2, sort_keys=True) + "\n",
        )

    def get(self, job_id: str) -> JobRecord:
        path = self._path(job_id)
        if not path.is_file():
            raise JobError(f"unknown job: {job_id}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise TypeError("job record must be an object")
            return JobRecord.from_dict(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, JobError) as exc:
            raise JobError(f"cannot load job {job_id}: {exc}") from exc

    def for_seed(self, seed_id: str) -> tuple[JobRecord, ...]:
        records: list[JobRecord] = []
        for path in sorted(self.root.glob("*.json")):
            job = self.get(path.stem)
            if job.seed_id == seed_id:
                records.append(job)
        records.sort(key=lambda job: (job.created_at, job.attempt, job.job_id))
        return tuple(records)

    def recover_interrupted(self, *, reason: str = "worker restarted") -> tuple[JobRecord, ...]:
        """Convert persisted in-flight jobs into explicit errors without rerunning them."""
        recovered: list[JobRecord] = []
        for path in sorted(self.root.glob("*.json")):
            job = self.get(path.stem)
            if job.status != RUNNING:
                continue
            interrupted = replace(
                job,
                status=ERROR,
                finished_at=_utcnow(),
                outcome_reason=reason,
            )
            self.save(interrupted)
            recovered.append(interrupted)
        return tuple(recovered)
