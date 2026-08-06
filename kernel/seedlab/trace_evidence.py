"""Correlation-chain evidence across Seed edge, execution, artifact, and deployment records."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass

from kernel.event_envelope import EventEnvelope
from kernel.seedlab.artifact_store import ArtifactRecord
from kernel.seedlab.deployment import DeploymentRun
from kernel.seedlab.jobs import JobRecord
from kernel.seedlab.tool_runner import ToolRunResult

_SAFE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_SENSITIVE_FIELD = re.compile(
    r"(?:password|passwd|secret|token|authorization|api[_-]?key|private[_-]?key)",
    re.IGNORECASE,
)


class TraceEvidenceError(ValueError):
    """A correlation chain is missing a hop or contains an unsafe identifier."""


def _safe(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or not _SAFE.fullmatch(value.strip()):
        raise TraceEvidenceError(f"{field} must be a safe non-empty identifier")
    return value.strip()


@dataclass(frozen=True)
class TraceEvidence:
    """The identifiers that must remain linked for one engineering action."""

    correlation_id: str
    session_id: str
    seed_id: str
    job_id: str
    worker_id: str
    artifact_id: str
    deployment_id: str
    audit_id: str

    def __post_init__(self) -> None:
        for field in self.__dataclass_fields__:
            _safe(getattr(self, field), field)

    def bind_event(self, event: EventEnvelope) -> None:
        if event.correlation_id != self.correlation_id or event.session_id != self.session_id:
            raise TraceEvidenceError("event is outside the correlation chain")

    def bind_job(self, job: JobRecord) -> None:
        if job.job_id != self.job_id or job.seed_id != self.seed_id:
            raise TraceEvidenceError("job is outside the correlation chain")
        if job.correlation_id and job.correlation_id != self.correlation_id:
            raise TraceEvidenceError("job correlation does not match the chain")

    def bind_tool_run(self, run: ToolRunResult) -> None:
        if run.seed_id != self.seed_id or run.correlation_id != self.correlation_id:
            raise TraceEvidenceError("worker result is outside the correlation chain")

    def bind_artifact(self, artifact: ArtifactRecord) -> None:
        if artifact.seed_id != self.seed_id or artifact.correlation_id != self.correlation_id:
            raise TraceEvidenceError("artifact is outside the correlation chain")

    def bind_deployment(self, deployment: DeploymentRun) -> None:
        if deployment.seed_id != self.seed_id or deployment.correlation_id != self.correlation_id:
            raise TraceEvidenceError("deployment is outside the correlation chain")

    def bind_audit(self, entry: Mapping[str, object]) -> None:
        """Validate a hash-chain audit payload emitted for this correlation."""
        if entry.get("actor") != self.session_id:
            raise TraceEvidenceError("audit actor is outside the correlation chain")
        action = entry.get("action")
        if not isinstance(action, str) or not action.strip():
            raise TraceEvidenceError("audit entry has no action")
        detail = entry.get("detail")
        if not isinstance(detail, str):
            raise TraceEvidenceError("audit entry detail is not structured")
        try:
            payload = json.loads(detail)
        except json.JSONDecodeError as exc:
            raise TraceEvidenceError("audit entry detail is not JSON") from exc
        if not isinstance(payload, dict):
            raise TraceEvidenceError("audit entry detail must be an object")
        if payload.get("correlation_id") != self.correlation_id:
            raise TraceEvidenceError("audit correlation does not match the chain")
        if payload.get("seed_id") != self.seed_id:
            raise TraceEvidenceError("audit Seed does not match the chain")
        if entry.get("event_id") and entry.get("event_id") != payload.get("event_id"):
            raise TraceEvidenceError("audit event identity is inconsistent")

    def bind_log(self, entry: Mapping[str, object]) -> None:
        """Validate a redacted worker or gateway log record against this chain.

        Logs are observational evidence, not authority.  They only join a trace when they carry
        the same correlation and Seed identifiers (and, when present, worker identity), and they
        are refused if structured fields look like credentials or bearer material.
        """
        if not isinstance(entry, Mapping):
            raise TraceEvidenceError("log entry must be structured")
        if entry.get("correlation_id") != self.correlation_id:
            raise TraceEvidenceError("log correlation does not match the chain")
        if entry.get("seed_id") != self.seed_id:
            raise TraceEvidenceError("log Seed does not match the chain")
        worker_id = entry.get("worker_id")
        if worker_id is not None and worker_id != self.worker_id:
            raise TraceEvidenceError("log worker does not match the chain")
        for key in entry:
            if not isinstance(key, str):
                raise TraceEvidenceError("log field name is not text")
            if _SENSITIVE_FIELD.search(key):
                raise TraceEvidenceError("log contains a sensitive field")
        for field in ("correlation_id", "seed_id", "worker_id"):
            value = entry.get(field)
            if value is not None:
                _safe(str(value), f"log {field}")

    def to_dict(self) -> dict[str, str]:
        return {field: getattr(self, field) for field in self.__dataclass_fields__}
