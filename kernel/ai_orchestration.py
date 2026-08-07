"""Provider-neutral, human-governed AI run and tool-grant evidence.

This module records AI work and authorizes narrow tool requests; it deliberately does not invoke
models, subprocesses, connectors, or deployment code. Execution remains owned by the existing Seed
workflow and policy boundaries.
"""

from __future__ import annotations

import json
import re
import secrets
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Protocol

from kernel.hubble.autonomy import ASSISTANT, AutonomyError, permits
from kernel.permission_policy import PermissionDenied, PermissionPolicy
from kernel.session_identity import SessionIdentity, SessionIdentityError
from kernel.shelf.atomic_write import atomic_write_text

PROPOSED = "proposed"
AWAITING_REVIEW = "awaiting_review"
APPROVED = "approved"
COMPLETED = "completed"
REJECTED = "rejected"
_RUN_STATUSES = {PROPOSED, AWAITING_REVIEW, APPROVED, COMPLETED, REJECTED}
_RUN_TRANSITIONS = {
    PROPOSED: {PROPOSED, AWAITING_REVIEW, COMPLETED},
    AWAITING_REVIEW: {APPROVED, REJECTED},
    APPROVED: {COMPLETED},
    COMPLETED: {COMPLETED},
    REJECTED: {REJECTED},
}
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]+$")


class AIOrchestrationError(ValueError):
    """An AI run or tool grant is malformed, unauthorized, or in an invalid state."""


def _required(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AIOrchestrationError(f"{field} must be a non-empty string")
    return value.strip()


def _timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AIOrchestrationError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise AIOrchestrationError(f"{field} must include a timezone")
    return parsed.astimezone(UTC)


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class AIProviderManifest:
    """Provider metadata, separate from the Seed's authority and model output."""

    provider_id: str
    model_id: str
    model_version: str
    capabilities: tuple[str, ...] = ()
    classification_ceiling: str = "internal"

    def __post_init__(self) -> None:
        for field_name in (
            "provider_id",
            "model_id",
            "model_version",
            "classification_ceiling",
        ):
            _required(getattr(self, field_name), field_name)
        object.__setattr__(
            self,
            "capabilities",
            tuple(_required(item, "capability") for item in self.capabilities),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ToolGrant:
    """A resource- and action-scoped grant for one AI run."""

    tool_id: str
    seed_id: str
    principal_id: str
    actions: tuple[str, ...]
    scope: tuple[str, ...] = ()
    denied: tuple[str, ...] = ()
    expires_at: str = ""
    classification_ceiling: str = "internal"
    approval_id: str = ""

    def __post_init__(self) -> None:
        for field_name in ("tool_id", "seed_id", "principal_id", "classification_ceiling"):
            _required(getattr(self, field_name), field_name)
        if not self.actions:
            raise AIOrchestrationError("tool grant requires at least one action")
        object.__setattr__(
            self, "actions", tuple(_required(item, "action") for item in self.actions)
        )
        object.__setattr__(self, "scope", tuple(_required(item, "scope") for item in self.scope))
        object.__setattr__(
            self,
            "denied",
            tuple(_required(item, "denied action") for item in self.denied),
        )
        if self.expires_at:
            _timestamp(self.expires_at, "expires_at")

    def assert_allowed(
        self,
        *,
        identity: SessionIdentity,
        policy: PermissionPolicy,
        action: str,
        resource: str = "",
        now: datetime | None = None,
    ) -> None:
        try:
            identity.require_seed(self.seed_id)
        except SessionIdentityError as exc:
            raise AIOrchestrationError(str(exc)) from exc
        if identity.principal_id != self.principal_id or not identity.is_active(now):
            raise AIOrchestrationError("tool grant principal or session is not active")
        if action not in self.actions or action in self.denied:
            raise AIOrchestrationError(f"tool action is not granted: {action}")
        if self.scope and not any(fnmatchcase(resource, pattern) for pattern in self.scope):
            raise AIOrchestrationError("tool resource is outside the grant scope")
        if self.expires_at and (now or datetime.now(UTC)) >= _timestamp(
            self.expires_at, "expires_at"
        ):
            raise AIOrchestrationError("tool grant has expired")
        try:
            policy.require(
                identity.permission_context(),
                capability=f"ai.tool.{self.tool_id}",
                scope=self.seed_id,
            )
        except PermissionDenied as exc:
            raise AIOrchestrationError(str(exc)) from exc

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AIJobBinding:
    """Evidence link from an AI run to an existing durable Seed job."""

    job_id: str
    seed_id: str
    correlation_id: str
    status: str

    def __post_init__(self) -> None:
        for field_name in ("job_id", "seed_id", "correlation_id", "status"):
            _required(getattr(self, field_name), field_name)
        if not _SAFE_ID.fullmatch(self.job_id):
            raise AIOrchestrationError("job_id contains unsafe characters")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AIRun:
    """Durable evidence for one provider invocation or proposed AI task."""

    ai_run_id: str
    provider: AIProviderManifest
    task: str
    principal_id: str
    seed_id: str
    session_id: str
    correlation_id: str
    requested_autonomy: str
    allowed_autonomy: str
    context_digest: str
    prompt_digest: str
    tool_grants: tuple[ToolGrant, ...] = ()
    job_bindings: tuple[AIJobBinding, ...] = ()
    resource_budget: Mapping[str, int] = field(default_factory=dict)
    status: str = PROPOSED
    output: str = ""
    citations: tuple[str, ...] = ()
    evaluations: tuple[str, ...] = ()
    human_reviewer: str = ""
    decision: str = ""
    created_at: str = ""
    completed_at: str = ""
    audit_id: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "ai_run_id",
            "task",
            "principal_id",
            "seed_id",
            "session_id",
            "correlation_id",
            "requested_autonomy",
            "allowed_autonomy",
            "context_digest",
            "prompt_digest",
        ):
            _required(getattr(self, field_name), field_name)
        if not _SAFE_ID.fullmatch(self.ai_run_id):
            raise AIOrchestrationError("ai_run_id contains unsafe characters")
        if self.status not in _RUN_STATUSES:
            raise AIOrchestrationError(f"unknown AI run status: {self.status}")
        object.__setattr__(self, "tool_grants", tuple(self.tool_grants))
        object.__setattr__(self, "job_bindings", tuple(self.job_bindings))
        object.__setattr__(self, "citations", tuple(self.citations))
        object.__setattr__(self, "evaluations", tuple(self.evaluations))
        object.__setattr__(self, "resource_budget", dict(self.resource_budget))

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["provider"] = self.provider.to_dict()
        value["tool_grants"] = [grant.to_dict() for grant in self.tool_grants]
        value["job_bindings"] = [binding.to_dict() for binding in self.job_bindings]
        return value

    @classmethod
    def from_dict(cls, raw: object) -> AIRun:
        if not isinstance(raw, dict):
            raise AIOrchestrationError("AI run must be an object")
        try:
            provider_raw = raw["provider"]
            grants_raw = raw.get("tool_grants", [])
            bindings_raw = raw.get("job_bindings", [])
            if (
                not isinstance(provider_raw, dict)
                or not isinstance(grants_raw, list)
                or not isinstance(bindings_raw, list)
            ):
                raise TypeError(
                    "provider must be an object and tool_grants/job_bindings must be lists"
                )
            provider = AIProviderManifest(**provider_raw)
            grants = tuple(ToolGrant(**grant) for grant in grants_raw if isinstance(grant, dict))
            bindings = tuple(
                AIJobBinding(**binding) for binding in bindings_raw if isinstance(binding, dict)
            )
            if len(grants) != len(grants_raw):
                raise TypeError("tool grants must be objects")
            if len(bindings) != len(bindings_raw):
                raise TypeError("job bindings must be objects")
            return cls(
                ai_run_id=str(raw["ai_run_id"]),
                provider=provider,
                task=str(raw["task"]),
                principal_id=str(raw["principal_id"]),
                seed_id=str(raw["seed_id"]),
                session_id=str(raw["session_id"]),
                correlation_id=str(raw["correlation_id"]),
                requested_autonomy=str(raw["requested_autonomy"]),
                allowed_autonomy=str(raw["allowed_autonomy"]),
                context_digest=str(raw["context_digest"]),
                prompt_digest=str(raw["prompt_digest"]),
                tool_grants=grants,
                job_bindings=bindings,
                resource_budget=dict(raw.get("resource_budget", {})),
                status=str(raw.get("status", PROPOSED)),
                output=str(raw.get("output", "")),
                citations=tuple(str(item) for item in raw.get("citations", [])),
                evaluations=tuple(str(item) for item in raw.get("evaluations", [])),
                human_reviewer=str(raw.get("human_reviewer", "")),
                decision=str(raw.get("decision", "")),
                created_at=str(raw.get("created_at", "")),
                completed_at=str(raw.get("completed_at", "")),
                audit_id=str(raw.get("audit_id", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AIOrchestrationError(f"malformed AI run: {exc}") from exc


class AIRunStore(Protocol):
    def save(self, run: AIRun) -> None: ...

    def get(self, ai_run_id: str) -> AIRun: ...


class FileAIRunStore:
    """Atomic JSON persistence for AI run evidence."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, ai_run_id: str) -> Path:
        if not _SAFE_ID.fullmatch(ai_run_id):
            raise AIOrchestrationError("ai_run_id contains unsafe characters")
        return self.root / f"{ai_run_id}.json"

    def save(self, run: AIRun) -> None:
        path = self._path(run.ai_run_id)
        encoded = json.dumps(run.to_dict(), indent=2, sort_keys=True) + "\n"
        if path.is_file():
            existing = self.get(run.ai_run_id)
            immutable_fields = (
                "ai_run_id",
                "provider",
                "task",
                "principal_id",
                "seed_id",
                "session_id",
                "correlation_id",
                "requested_autonomy",
                "allowed_autonomy",
                "context_digest",
                "prompt_digest",
                "tool_grants",
                "resource_budget",
                "created_at",
            )
            if any(getattr(existing, name) != getattr(run, name) for name in immutable_fields):
                raise AIOrchestrationError("AI run request evidence cannot be overwritten")
            if run.status not in _RUN_TRANSITIONS[existing.status]:
                raise AIOrchestrationError(
                    f"invalid AI run transition: {existing.status} -> {run.status}"
                )
            if existing == run:
                return
        atomic_write_text(path, encoded)

    def get(self, ai_run_id: str) -> AIRun:
        path = self._path(ai_run_id)
        if not path.is_file():
            raise AIOrchestrationError(f"unknown AI run: {ai_run_id}")
        try:
            return AIRun.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AIOrchestrationError(f"cannot read AI run {ai_run_id}: {exc}") from exc


class AIOrchestrator:
    """Create and review AI evidence without granting the AI ambient execution authority."""

    def __init__(
        self,
        store: AIRunStore,
        audit_sink: Callable[[str, str, str], None] | None = None,
    ) -> None:
        self.store = store
        self.audit_sink = audit_sink

    def _audit(self, run: AIRun, action: str, detail: str) -> str:
        if self.audit_sink is None:
            return ""
        audit_id = f"audit-{secrets.token_hex(6)}"
        payload = json.dumps(
            {
                "ai_run_id": run.ai_run_id,
                "correlation_id": run.correlation_id,
                "seed_id": run.seed_id,
                "status": run.status,
                "audit_id": audit_id,
                "detail": detail,
            },
            sort_keys=True,
        )
        self.audit_sink(run.session_id, action, payload)
        return audit_id

    def request(
        self,
        *,
        provider: AIProviderManifest,
        task: str,
        identity: SessionIdentity,
        policy: PermissionPolicy,
        context_digest: str,
        prompt_digest: str,
        requested_autonomy: str = ASSISTANT,
        context_flags: set[str] | None = None,
        tool_grants: tuple[ToolGrant, ...] = (),
        resource_budget: Mapping[str, int] | None = None,
        ai_run_id: str | None = None,
        now: str | None = None,
    ) -> AIRun:
        request_time = _timestamp(now, "now") if now else None
        try:
            identity.require_seed(identity.seed_id)
            if not identity.is_active(request_time):
                raise PermissionDenied("AI request identity is inactive")
            policy.require(
                identity.permission_context(), capability="ai.run", scope=identity.seed_id
            )
            verdict = permits(requested_autonomy, context_flags or set())
        except (PermissionDenied, AutonomyError) as exc:
            raise AIOrchestrationError(str(exc)) from exc
        if not verdict.permitted:
            raise AIOrchestrationError(
                f"requested autonomy is denied: allowed mode is {verdict.allowed_mode}"
            )
        for grant in tool_grants:
            if grant.seed_id != identity.seed_id or grant.principal_id != identity.principal_id:
                raise AIOrchestrationError("tool grant is outside the requesting identity scope")
        run = AIRun(
            ai_run_id=ai_run_id or f"ai-{secrets.token_hex(6)}",
            provider=provider,
            task=task,
            principal_id=identity.principal_id,
            seed_id=identity.seed_id,
            session_id=identity.session_id,
            correlation_id=identity.correlation_id,
            requested_autonomy=requested_autonomy,
            allowed_autonomy=verdict.allowed_mode,
            context_digest=context_digest,
            prompt_digest=prompt_digest,
            tool_grants=tool_grants,
            resource_budget=resource_budget or {},
            status=AWAITING_REVIEW if requested_autonomy != ASSISTANT else PROPOSED,
            created_at=now or _now(),
        )
        run = replace(run, audit_id=self._audit(run, "ai.requested", "AI run requested"))
        self.store.save(run)
        return run

    def approve(
        self,
        ai_run_id: str,
        reviewer: SessionIdentity,
        *,
        policy: PermissionPolicy,
        decision: str = "approved",
    ) -> AIRun:
        run = self.store.get(ai_run_id)
        if run.status != AWAITING_REVIEW:
            raise AIOrchestrationError(f"AI run is not awaiting review: {run.status}")
        try:
            reviewer.require_seed(run.seed_id)
            if not reviewer.is_active():
                raise PermissionDenied("reviewer identity is inactive")
            if reviewer.principal_kind != "human":
                raise PermissionDenied("AI run requires a human reviewer")
            policy.require(reviewer.permission_context(), capability="ai.run", scope=run.seed_id)
        except (PermissionDenied, SessionIdentityError) as exc:
            raise AIOrchestrationError(str(exc)) from exc
        if reviewer.principal_id == run.principal_id:
            raise AIOrchestrationError("AI run requires an independent human reviewer")
        if decision != "approved":
            updated = replace(
                run, status=REJECTED, human_reviewer=reviewer.principal_id, decision=decision
            )
        else:
            updated = replace(
                run, status=APPROVED, human_reviewer=reviewer.principal_id, decision=decision
            )
        updated = replace(
            updated,
            audit_id=self._audit(updated, "ai.reviewed", f"AI run {decision}"),
        )
        self.store.save(updated)
        return updated

    def record_output(
        self,
        ai_run_id: str,
        *,
        identity: SessionIdentity,
        policy: PermissionPolicy,
        output: str,
        citations: tuple[str, ...] = (),
        evaluations: tuple[str, ...] = (),
        completed_at: str | None = None,
    ) -> AIRun:
        run = self.store.get(ai_run_id)
        if run.status not in {PROPOSED, APPROVED}:
            raise AIOrchestrationError(f"AI run cannot record output in state {run.status}")
        try:
            identity.require_seed(run.seed_id)
            if identity.principal_id != run.principal_id or not identity.is_active():
                raise PermissionDenied("AI output identity is not active or does not own the run")
            policy.require(identity.permission_context(), capability="ai.run", scope=run.seed_id)
        except (PermissionDenied, SessionIdentityError) as exc:
            raise AIOrchestrationError(str(exc)) from exc
        if not output.strip():
            raise AIOrchestrationError("AI output must not be empty")
        updated = replace(
            run,
            status=COMPLETED,
            output=output,
            citations=tuple(citations),
            evaluations=tuple(evaluations),
            completed_at=completed_at or _now(),
        )
        updated = replace(
            updated,
            audit_id=self._audit(updated, "ai.completed", "AI output recorded"),
        )
        self.store.save(updated)
        return updated

    def bind_job(
        self,
        ai_run_id: str,
        job: object,
        *,
        identity: SessionIdentity,
        policy: PermissionPolicy,
    ) -> AIRun:
        """Attach a durable Seed ``JobRecord`` to an AI run without executing it.

        The binding is intentionally evidence-only.  The existing JobRunner remains the authority
        for execution, retries, cancellation, and tool policy; this method proves that AI context
        can be correlated to those durable outcomes without creating a second job runtime.
        """

        run = self.store.get(ai_run_id)
        try:
            identity.require_seed(run.seed_id)
            if identity.principal_id != run.principal_id or not identity.is_active():
                raise PermissionDenied(
                    "AI job binding identity is not active or does not own the run"
                )
            policy.require(identity.permission_context(), capability="ai.run", scope=run.seed_id)
        except (PermissionDenied, SessionIdentityError) as exc:
            raise AIOrchestrationError(str(exc)) from exc

        job_id = getattr(job, "job_id", "")
        seed_id = getattr(job, "seed_id", "")
        correlation_id = getattr(job, "correlation_id", "")
        status = getattr(job, "status", "")
        if not all(isinstance(value, str) and value.strip() for value in (job_id, seed_id, status)):
            raise AIOrchestrationError("job binding requires a durable job id, Seed, and status")
        if seed_id != run.seed_id:
            raise AIOrchestrationError("job binding is outside the AI run Seed scope")
        if correlation_id != run.correlation_id:
            raise AIOrchestrationError("job binding correlation does not match the AI run")
        binding = AIJobBinding(job_id, seed_id, correlation_id, status)
        existing = next((item for item in run.job_bindings if item.job_id == job_id), None)
        if existing is not None and existing != binding:
            raise AIOrchestrationError("job binding evidence cannot be overwritten")
        if existing is not None:
            return run
        updated = replace(run, job_bindings=run.job_bindings + (binding,))
        updated = replace(updated, audit_id=self._audit(updated, "ai.job_bound", job_id))
        self.store.save(updated)
        return updated
