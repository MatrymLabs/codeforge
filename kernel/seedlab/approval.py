"""Durable human approval records for restart-safe Seed jobs.

An approval is a scoped, expiring grant for one exact job activity.  It is persisted separately
from the job so a worker restart cannot turn an in-memory approval into ambient authority.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from kernel.permission_policy import PermissionPolicy
from kernel.session_identity import SessionIdentity
from kernel.shelf.atomic_write import atomic_write_text

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
CONSUMED = "consumed"
EXPIRED = "expired"


class ApprovalError(ValueError):
    """An approval is malformed, unavailable, or no longer usable."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _parse(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApprovalError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ApprovalError(f"{field} must include a timezone")
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class ApprovalRecord:
    approval_id: str
    job_id: str
    seed_id: str
    requested_by: str
    capability: str
    scope: str
    created_at: str
    expires_at: str
    activity_id: str = ""
    status: str = PENDING
    approver_id: str = ""
    approved_at: str = ""
    consumed_at: str = ""
    evidence_digest: str = ""
    correlation_id: str = ""

    def __post_init__(self) -> None:
        for field in ("approval_id", "job_id", "seed_id", "requested_by", "capability", "scope"):
            if not getattr(self, field).strip():
                raise ApprovalError(f"{field} must be a non-empty string")
        if self.status not in {PENDING, APPROVED, REJECTED, CONSUMED, EXPIRED}:
            raise ApprovalError(f"unknown approval status: {self.status}")
        if _parse(self.expires_at, "expires_at") <= _parse(self.created_at, "created_at"):
            raise ApprovalError("expires_at must be later than created_at")

    @property
    def active(self) -> bool:
        return self.status == APPROVED and _parse(self.expires_at, "expires_at") > datetime.now(UTC)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: object) -> ApprovalRecord:
        if not isinstance(raw, dict):
            raise ApprovalError("approval record must be an object")
        try:
            return cls(
                approval_id=str(raw["approval_id"]),
                job_id=str(raw["job_id"]),
                seed_id=str(raw["seed_id"]),
                requested_by=str(raw["requested_by"]),
                capability=str(raw["capability"]),
                scope=str(raw["scope"]),
                activity_id=str(raw.get("activity_id", "")),
                created_at=str(raw["created_at"]),
                expires_at=str(raw["expires_at"]),
                status=str(raw.get("status", PENDING)),
                approver_id=str(raw.get("approver_id", "")),
                approved_at=str(raw.get("approved_at", "")),
                consumed_at=str(raw.get("consumed_at", "")),
                evidence_digest=str(raw.get("evidence_digest", "")),
                correlation_id=str(raw.get("correlation_id", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ApprovalError(f"malformed approval record: {exc}") from exc


class ApprovalStore(Protocol):
    def save(self, approval: ApprovalRecord) -> None: ...

    def get(self, approval_id: str) -> ApprovalRecord: ...

    def approve(
        self, approval_id: str, approver_id: str, *, now: str | None = None
    ) -> ApprovalRecord: ...

    def reject(
        self, approval_id: str, approver_id: str, *, now: str | None = None
    ) -> ApprovalRecord: ...

    def consume(
        self,
        approval_id: str,
        *,
        identity: SessionIdentity,
        policy: PermissionPolicy,
        job_id: str,
        activity_id: str,
        evidence_digest: str = "",
        now: str | None = None,
    ) -> ApprovalRecord: ...


class FileApprovalStore:
    """JSON-backed approvals with a process lock around one-time consumption."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, approval_id: str) -> Path:
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
        if not approval_id or any(char not in allowed for char in approval_id):
            raise ApprovalError(f"unsafe approval id: {approval_id!r}")
        return self.root / f"{approval_id}.json"

    def save(self, approval: ApprovalRecord) -> None:
        payload = json.dumps(approval.to_dict(), indent=2, sort_keys=True) + "\n"
        atomic_write_text(self._path(approval.approval_id), payload)

    def get(self, approval_id: str) -> ApprovalRecord:
        try:
            raw = json.loads(self._path(approval_id).read_text(encoding="utf-8"))
            return ApprovalRecord.from_dict(raw)
        except FileNotFoundError as exc:
            raise ApprovalError(f"unknown approval: {approval_id}") from exc
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApprovalError(f"cannot load approval {approval_id}: {exc}") from exc

    def request(
        self,
        approval_id: str,
        *,
        job_id: str,
        seed_id: str,
        requested_by: str,
        capability: str,
        scope: str,
        expires_at: str,
        activity_id: str = "",
        evidence_digest: str = "",
        correlation_id: str = "",
        created_at: str | None = None,
    ) -> ApprovalRecord:
        record = ApprovalRecord(
            approval_id=approval_id,
            job_id=job_id,
            seed_id=seed_id,
            requested_by=requested_by,
            capability=capability,
            scope=scope,
            activity_id=activity_id,
            created_at=created_at or _now(),
            expires_at=expires_at,
            evidence_digest=evidence_digest,
            correlation_id=correlation_id,
        )
        with self._lock:
            try:
                existing = self.get(approval_id)
            except ApprovalError:
                self.save(record)
                return record
            if existing != record:
                raise ApprovalError("approval id already exists with different intent")
            return existing

    def _transition(
        self, approval_id: str, *, approver_id: str, status: str, now: str | None
    ) -> ApprovalRecord:
        with self._lock:
            current = self.get(approval_id)
            if current.status != PENDING:
                raise ApprovalError(f"approval is not pending: {current.status}")
            if approver_id == current.requested_by:
                raise ApprovalError("approval requires an independent principal")
            current_time = _parse(now or _now(), "now")
            if current_time >= _parse(current.expires_at, "expires_at"):
                expired = replace(current, status=EXPIRED)
                self.save(expired)
                raise ApprovalError("approval has expired")
            updated = replace(
                current,
                status=status,
                approver_id=approver_id,
                approved_at=now or _now() if status == APPROVED else "",
            )
            self.save(updated)
            return updated

    def approve(
        self, approval_id: str, approver_id: str, *, now: str | None = None
    ) -> ApprovalRecord:
        return self._transition(approval_id, approver_id=approver_id, status=APPROVED, now=now)

    def reject(
        self, approval_id: str, approver_id: str, *, now: str | None = None
    ) -> ApprovalRecord:
        return self._transition(approval_id, approver_id=approver_id, status=REJECTED, now=now)

    def consume(
        self,
        approval_id: str,
        *,
        identity: SessionIdentity,
        policy: PermissionPolicy,
        job_id: str,
        activity_id: str,
        evidence_digest: str = "",
        now: str | None = None,
    ) -> ApprovalRecord:
        with self._lock:
            current = self.get(approval_id)
            if current.status != APPROVED:
                raise ApprovalError(f"approval is not executable: {current.status}")
            current_time = _parse(now or _now(), "now")
            if current_time >= _parse(current.expires_at, "expires_at"):
                self.save(replace(current, status=EXPIRED))
                raise ApprovalError("approval has expired")
            if (
                current.job_id != job_id
                or (current.activity_id and current.activity_id != activity_id)
                or identity.principal_id != current.requested_by
            ):
                raise ApprovalError("approval is bound to a different job or principal")
            if identity.seed_id != current.seed_id or not identity.is_active(current_time):
                raise ApprovalError("approval identity is inactive or scoped to another Seed")
            if current.evidence_digest and current.evidence_digest != evidence_digest:
                raise ApprovalError("approval evidence digest does not match")
            policy.require(
                identity.permission_context(), capability=current.capability, scope=current.scope
            )
            updated = replace(current, status=CONSUMED, consumed_at=now or _now())
            self.save(updated)
            return updated
