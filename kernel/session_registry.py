"""Authoritative persistence for platform SessionIdentity records.

``SessionIdentity`` is the wire contract; this registry is the authority that decides whether a
serialized identity may resume after a process restart. Clients may present an identity, but they
cannot mint, widen, or revive one. Invalidation is a durable tombstone and an audit event.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session as SqlSession

from kernel.platform_db import SessionIdentityRow, open_archive_session
from kernel.seedlab.audit_registry import AuditStore, SqlAuditStore, configured_audit_store
from kernel.session_identity import SessionIdentity, SessionIdentityError
from kernel.shelf.atomic_write import atomic_write_text


class SessionRegistryError(SessionIdentityError):
    """A session is missing, revoked, malformed, or conflicts with durable authority."""


@dataclass(frozen=True)
class SessionRecord:
    identity: SessionIdentity
    state: str = "active"
    updated_at: str = ""
    invalidated_by: str = ""
    invalidation_reason: str = ""

    def __post_init__(self) -> None:
        if self.state not in {"active", "invalidated"}:
            raise SessionRegistryError(f"unknown session state {self.state!r}")

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity.to_dict(),
            "state": self.state,
            "updated_at": self.updated_at,
            "invalidated_by": self.invalidated_by,
            "invalidation_reason": self.invalidation_reason,
        }

    @classmethod
    def from_dict(cls, value: object) -> SessionRecord:
        if not isinstance(value, dict):
            raise SessionRegistryError("session record must be an object")
        try:
            return cls(
                identity=SessionIdentity.from_dict(value["identity"]),
                state=str(value.get("state", "active")),
                updated_at=str(value.get("updated_at", "")),
                invalidated_by=str(value.get("invalidated_by", "")),
                invalidation_reason=str(value.get("invalidation_reason", "")),
            )
        except (KeyError, TypeError, ValueError, SessionIdentityError) as exc:
            raise SessionRegistryError(f"malformed session record: {exc}") from exc


@runtime_checkable
class SessionRegistry(Protocol):
    def issue(
        self,
        identity: SessionIdentity,
        *,
        actor: str = "system",
        now: str | None = None,
    ) -> SessionRecord: ...

    def resume(self, session_id: str, *, now: datetime | None = None) -> SessionIdentity: ...

    def require_active(self, identity: SessionIdentity, *, now: datetime | None = None) -> None: ...

    def renew(
        self,
        identity: SessionIdentity,
        *,
        ttl: timedelta,
        actor: str,
        now: datetime | None = None,
    ) -> SessionIdentity: ...

    def invalidate(
        self,
        session_id: str,
        *,
        actor: str,
        reason: str,
        now: str | None = None,
    ) -> SessionRecord: ...

    def load(self, session_id: str) -> SessionRecord | None: ...


@dataclass
class FileSessionRegistry:
    root: Path
    audit: AuditStore | None = None
    clock: Callable[[], str] | None = None

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        if self.audit is None:
            self.audit = configured_audit_store(self.root.parent / "session-audit.jsonl")

    @staticmethod
    def _safe(value: str) -> str:
        return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)

    def _path(self, session_id: str) -> Path:
        return self.root / f"{self._safe(session_id)}.json"

    def _now(self, supplied: str | None) -> str:
        if supplied is not None:
            return supplied
        if self.clock is not None:
            return self.clock()
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def _save(self, record: SessionRecord) -> None:
        atomic_write_text(
            self._path(record.identity.session_id),
            json.dumps(record.to_dict(), indent=2, sort_keys=True),
        )

    def _audit(self, action: str, record: SessionRecord, actor: str) -> None:
        assert self.audit is not None
        self.audit.append(
            {
                "ts": record.updated_at,
                "actor": actor,
                "action": action,
                "session_id": record.identity.session_id,
                "principal_id": record.identity.principal_id,
                "principal_kind": record.identity.principal_kind,
                "seed_id": record.identity.seed_id,
                "correlation_id": record.identity.correlation_id,
                "state": record.state,
                "reason": record.invalidation_reason,
            }
        )

    def issue(
        self,
        identity: SessionIdentity,
        *,
        actor: str = "system",
        now: str | None = None,
    ) -> SessionRecord:
        existing = self.load(identity.session_id)
        if existing is not None:
            if existing.identity != identity:
                raise SessionRegistryError(
                    f"session {identity.session_id!r} already exists with different authority"
                )
            if existing.state != "active":
                raise SessionRegistryError(f"session {identity.session_id!r} is invalidated")
            return existing
        record = SessionRecord(identity=identity, updated_at=self._now(now))
        self._audit("session.issued", record, actor)
        self._save(record)
        return record

    def load(self, session_id: str) -> SessionRecord | None:
        path = self._path(session_id)
        if not path.is_file():
            return None
        try:
            return SessionRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, SessionRegistryError) as exc:
            raise SessionRegistryError(f"corrupt session record {path}") from exc

    def resume(self, session_id: str, *, now: datetime | None = None) -> SessionIdentity:
        record = self.load(session_id)
        if record is None:
            raise SessionRegistryError(f"unknown session {session_id!r}")
        self.require_active(record.identity, now=now)
        return record.identity

    def require_active(self, identity: SessionIdentity, *, now: datetime | None = None) -> None:
        record = self.load(identity.session_id)
        if record is None:
            raise SessionRegistryError(f"unknown session {identity.session_id!r}")
        if record.identity != identity:
            raise SessionRegistryError("presented session authority differs from the registry")
        if record.state != "active":
            raise SessionRegistryError(f"session {identity.session_id!r} is invalidated")
        if not identity.is_active(now):
            raise SessionRegistryError(
                f"session {identity.session_id!r} is expired or not yet active"
            )

    def renew(
        self,
        identity: SessionIdentity,
        *,
        ttl: timedelta,
        actor: str,
        now: datetime | None = None,
    ) -> SessionIdentity:
        """Extend an active session without changing its authority or scope."""
        if ttl <= timedelta(0):
            raise SessionRegistryError("session renewal ttl must be positive")
        current = self.load(identity.session_id)
        if current is None:
            raise SessionRegistryError(f"unknown session {identity.session_id!r}")
        effective_now = now or datetime.now(UTC)
        self.require_active(identity, now=effective_now)
        renewed = SessionIdentity(
            principal_id=identity.principal_id,
            principal_kind=identity.principal_kind,
            session_id=identity.session_id,
            seed_id=identity.seed_id,
            issued_at=identity.issued_at,
            expires_at=effective_now.astimezone(UTC) + ttl,
            correlation_id=identity.correlation_id,
            roles=identity.roles,
            capabilities=identity.capabilities,
        )
        record = SessionRecord(
            identity=renewed,
            state="active",
            updated_at=self._now(None),
        )
        self._audit("session.renewed", record, actor)
        self._save(record)
        return renewed

    def invalidate(
        self,
        session_id: str,
        *,
        actor: str,
        reason: str,
        now: str | None = None,
    ) -> SessionRecord:
        current = self.load(session_id)
        if current is None:
            raise SessionRegistryError(f"unknown session {session_id!r}")
        if current.state == "invalidated":
            return current
        record = SessionRecord(
            identity=current.identity,
            state="invalidated",
            updated_at=self._now(now),
            invalidated_by=actor,
            invalidation_reason=reason,
        )
        self._audit("session.invalidated", record, actor)
        self._save(record)
        return record


@dataclass
class SqlSessionRegistry:
    """SQL-backed SessionIdentity authority on the shared platform database."""

    root: Path
    audit: AuditStore | None = None
    session_factory: Callable[[], SqlSession] = open_archive_session

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        if self.audit is None:
            self.audit = SqlAuditStore(self.session_factory)

    def _now(self, supplied: str | None) -> str:
        if supplied is not None:
            return supplied
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _decode(row: SessionIdentityRow) -> SessionRecord:
        try:
            raw = json.loads(row.identity_json)
            if not isinstance(raw, dict):
                raise TypeError("identity must be an object")
            return SessionRecord(
                identity=SessionIdentity.from_dict(raw),
                state=row.state,
                updated_at=row.updated_at,
                invalidated_by=row.invalidated_by,
                invalidation_reason=row.invalidation_reason,
            )
        except (TypeError, ValueError, json.JSONDecodeError, SessionRegistryError) as exc:
            raise SessionRegistryError(f"malformed SQL session record {row.session_id!r}") from exc

    @staticmethod
    def _encode(record: SessionRecord) -> str:
        return json.dumps(record.identity.to_dict(), sort_keys=True, separators=(",", ":"))

    def _audit(self, action: str, record: SessionRecord, actor: str) -> None:
        assert self.audit is not None
        self.audit.append(
            {
                "ts": record.updated_at,
                "actor": actor,
                "action": action,
                "session_id": record.identity.session_id,
                "principal_id": record.identity.principal_id,
                "principal_kind": record.identity.principal_kind,
                "seed_id": record.identity.seed_id,
                "correlation_id": record.identity.correlation_id,
                "state": record.state,
                "reason": record.invalidation_reason,
            }
        )

    def _save(self, record: SessionRecord) -> None:
        payload = self._encode(record)
        with self.session_factory() as session, session.begin():
            row = session.get(SessionIdentityRow, record.identity.session_id)
            if row is None:
                session.add(
                    SessionIdentityRow(
                        session_id=record.identity.session_id,
                        identity_json=payload,
                        state=record.state,
                        updated_at=record.updated_at,
                        invalidated_by=record.invalidated_by,
                        invalidation_reason=record.invalidation_reason,
                    )
                )
            else:
                row.identity_json = payload
                row.state = record.state
                row.updated_at = record.updated_at
                row.invalidated_by = record.invalidated_by
                row.invalidation_reason = record.invalidation_reason

    def issue(
        self,
        identity: SessionIdentity,
        *,
        actor: str = "system",
        now: str | None = None,
    ) -> SessionRecord:
        existing = self.load(identity.session_id)
        if existing is not None:
            if existing.identity != identity:
                raise SessionRegistryError(
                    f"session {identity.session_id!r} already exists with different authority"
                )
            if existing.state != "active":
                raise SessionRegistryError(f"session {identity.session_id!r} is invalidated")
            return existing
        record = SessionRecord(identity=identity, updated_at=self._now(now))
        self._save(record)
        self._audit("session.issued", record, actor)
        return record

    def load(self, session_id: str) -> SessionRecord | None:
        with self.session_factory() as session:
            row = session.get(SessionIdentityRow, session_id)
        return None if row is None else self._decode(row)

    def resume(self, session_id: str, *, now: datetime | None = None) -> SessionIdentity:
        record = self.load(session_id)
        if record is None:
            raise SessionRegistryError(f"unknown session {session_id!r}")
        self.require_active(record.identity, now=now)
        return record.identity

    def require_active(self, identity: SessionIdentity, *, now: datetime | None = None) -> None:
        record = self.load(identity.session_id)
        if record is None:
            raise SessionRegistryError(f"unknown session {identity.session_id!r}")
        if record.identity != identity:
            raise SessionRegistryError("presented session authority differs from the registry")
        if record.state != "active":
            raise SessionRegistryError(f"session {identity.session_id!r} is invalidated")
        if not identity.is_active(now):
            raise SessionRegistryError(
                f"session {identity.session_id!r} is expired or not yet active"
            )

    def renew(
        self,
        identity: SessionIdentity,
        *,
        ttl: timedelta,
        actor: str,
        now: datetime | None = None,
    ) -> SessionIdentity:
        """Extend an active session without changing its authority or scope."""
        if ttl <= timedelta(0):
            raise SessionRegistryError("session renewal ttl must be positive")
        effective_now = now or datetime.now(UTC)
        self.require_active(identity, now=effective_now)
        renewed = SessionIdentity(
            principal_id=identity.principal_id,
            principal_kind=identity.principal_kind,
            session_id=identity.session_id,
            seed_id=identity.seed_id,
            issued_at=identity.issued_at,
            expires_at=effective_now.astimezone(UTC) + ttl,
            correlation_id=identity.correlation_id,
            roles=identity.roles,
            capabilities=identity.capabilities,
        )
        record = SessionRecord(
            identity=renewed,
            state="active",
            updated_at=self._now(None),
        )
        self._save(record)
        self._audit("session.renewed", record, actor)
        return renewed

    def invalidate(
        self,
        session_id: str,
        *,
        actor: str,
        reason: str,
        now: str | None = None,
    ) -> SessionRecord:
        current = self.load(session_id)
        if current is None:
            raise SessionRegistryError(f"unknown session {session_id!r}")
        if current.state == "invalidated":
            return current
        record = SessionRecord(
            identity=current.identity,
            state="invalidated",
            updated_at=self._now(now),
            invalidated_by=actor,
            invalidation_reason=reason,
        )
        self._save(record)
        self._audit("session.invalidated", record, actor)
        return record


def configured_session_registry(home: Path) -> SessionRegistry:
    """Open the file-backed session authority for the current SeedLab home."""
    backend = os.environ.get("CODEFORGE_SESSION_REGISTRY", "file").strip() or "file"
    if backend == "sql":
        return SqlSessionRegistry(Path(home) / "sessions")
    if backend != "file":
        raise SessionRegistryError(
            f"unknown session registry backend {backend!r}; expected file or sql"
        )
    return FileSessionRegistry(Path(home) / "sessions")
