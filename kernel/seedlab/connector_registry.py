"""Durable lifecycle records for Seed connectors.

Registration is deliberately separate from source provenance.  Provenance records the immutable
snapshot that was inspected; this registry records whether that connector is currently registered,
revoked, removed, or failed.  Removal therefore leaves a durable tombstone and an audit event
instead of making the connector disappear from history.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session as SqlSession

from kernel.platform_db import SeedConnectorRow, open_archive_session
from kernel.seedlab.audit_registry import AuditStore, configured_audit_store
from kernel.seedlab.source_connector import ConnectorManifest, SourceConnectorError, SourceRecord
from kernel.shelf.atomic_write import atomic_write_text


class ConnectorRegistryError(SourceConnectorError):
    """A connector lifecycle record is invalid or conflicts with durable state."""


_ACTIVE_STATES = frozenset({"registered", "active"})
_STATES = frozenset({"registered", "active", "revoked", "removed", "failed"})


def _safe_segment(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


def _source_to_dict(source: SourceRecord | None) -> dict[str, object] | None:
    if source is None:
        return None
    return {
        "source_id": source.source_id,
        "provenance": {
            "source_id": source.provenance.source_id,
            "owner": source.provenance.owner,
            "license": source.provenance.license,
            "visibility": source.provenance.visibility,
            "allowed_use": source.provenance.allowed_use,
        },
        "root": source.root,
        "file_count": source.file_count,
        "branch": source.branch,
        "commit": source.commit,
        "digest": source.digest,
    }


def _source_from_dict(value: object) -> SourceRecord | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ConnectorRegistryError("connector source must be a mapping or null")
    provenance = value.get("provenance")
    if not isinstance(provenance, dict):
        raise ConnectorRegistryError("connector provenance must be a mapping")
    try:
        from kernel.seedlab.project_model import Provenance

        return SourceRecord(
            source_id=str(value["source_id"]),
            provenance=Provenance(**provenance),
            root=str(value["root"]),
            file_count=int(value["file_count"]),
            branch=None if value.get("branch") is None else str(value["branch"]),
            commit=None if value.get("commit") is None else str(value["commit"]),
            digest=str(value.get("digest", "")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConnectorRegistryError(f"malformed connector source: {exc}") from exc


@dataclass(frozen=True)
class ConnectorRegistration:
    """The current durable lifecycle state for one Seed/source connector pair."""

    registration_id: str
    seed_id: str
    connector_id: str
    source: SourceRecord | None
    manifest: dict[str, object]
    state: str
    actor: str
    created_at: str
    updated_at: str
    correlation_id: str = ""
    reason: str = ""
    failure: str = ""

    def __post_init__(self) -> None:
        if not self.registration_id or not self.seed_id or not self.connector_id:
            raise ConnectorRegistryError("connector registration identity is required")
        if self.state not in _STATES:
            raise ConnectorRegistryError(f"unknown connector state {self.state!r}")
        if not isinstance(self.manifest, dict):
            raise ConnectorRegistryError("connector manifest must be a mapping")

    def to_dict(self) -> dict[str, object]:
        return {
            "registration_id": self.registration_id,
            "seed_id": self.seed_id,
            "connector_id": self.connector_id,
            "source": _source_to_dict(self.source),
            "manifest": dict(self.manifest),
            "state": self.state,
            "actor": self.actor,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "correlation_id": self.correlation_id,
            "reason": self.reason,
            "failure": self.failure,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ConnectorRegistration:
        try:
            manifest = data["manifest"]
            if not isinstance(manifest, dict):
                raise TypeError("manifest must be a mapping")
            return cls(
                registration_id=str(data["registration_id"]),
                seed_id=str(data["seed_id"]),
                connector_id=str(data["connector_id"]),
                source=_source_from_dict(data.get("source")),
                manifest=dict(manifest),
                state=str(data["state"]),
                actor=str(data["actor"]),
                created_at=str(data["created_at"]),
                updated_at=str(data["updated_at"]),
                correlation_id=str(data.get("correlation_id", "")),
                reason=str(data.get("reason", "")),
                failure=str(data.get("failure", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ConnectorRegistryError(f"malformed connector registration: {exc}") from exc


@runtime_checkable
class ConnectorRegistry(Protocol):
    """Persistence seam for connector lifecycle state."""

    def register(
        self,
        seed_id: str,
        source: SourceRecord,
        manifest: ConnectorManifest | dict[str, object],
        *,
        actor: str,
        correlation_id: str = "",
        now: str | None = None,
    ) -> ConnectorRegistration: ...

    def remove(
        self,
        seed_id: str,
        source_id: str,
        *,
        actor: str,
        reason: str = "",
        correlation_id: str = "",
        now: str | None = None,
    ) -> ConnectorRegistration: ...

    def revoke(
        self,
        seed_id: str,
        source_id: str,
        *,
        actor: str,
        reason: str = "",
        correlation_id: str = "",
        now: str | None = None,
    ) -> ConnectorRegistration: ...

    def record_failure(
        self,
        seed_id: str,
        source_id: str,
        *,
        actor: str,
        failure: str,
        correlation_id: str = "",
        now: str | None = None,
    ) -> ConnectorRegistration: ...

    def load(self, seed_id: str, source_id: str) -> ConnectorRegistration | None: ...

    def all_for_seed(self, seed_id: str) -> list[ConnectorRegistration]: ...

    def active_for_seed(self, seed_id: str) -> list[ConnectorRegistration]: ...


@dataclass
class FileConnectorRegistry:
    """Atomic JSON lifecycle snapshots with a shared tamper-evident audit ledger."""

    root: Path
    audit: AuditStore | None = None
    clock: Callable[[], str] | None = None

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        if self.audit is None:
            self.audit = configured_audit_store(self.root.parent / "connector-audit.jsonl")

    def _path(self, seed_id: str, source_id: str) -> Path:
        return self.root / _safe_segment(seed_id) / f"{_safe_segment(source_id)}.json"

    def _now(self, supplied: str | None) -> str:
        if supplied is not None:
            return supplied
        if self.clock is not None:
            return self.clock()
        from datetime import UTC, datetime

        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def _save(self, registration: ConnectorRegistration) -> None:
        target = self._path(registration.seed_id, registration.registration_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target, json.dumps(registration.to_dict(), indent=2, sort_keys=True))

    def _audit(self, action: str, registration: ConnectorRegistration) -> None:
        assert self.audit is not None
        payload: dict[str, object] = {
            "ts": registration.updated_at,
            "actor": registration.actor,
            "action": action,
            "seed_id": registration.seed_id,
            "connector_id": registration.connector_id,
            "registration_id": registration.registration_id,
            "source_id": (
                registration.source.source_id
                if registration.source
                else registration.registration_id
            ),
            "state": registration.state,
            "correlation_id": registration.correlation_id,
        }
        if registration.source is not None:
            payload["source_digest"] = registration.source.digest
        if registration.reason:
            payload["reason"] = registration.reason
        if registration.failure:
            payload["failure"] = registration.failure
        self.audit.append(payload)

    def register(
        self,
        seed_id: str,
        source: SourceRecord,
        manifest: ConnectorManifest | dict[str, object],
        *,
        actor: str,
        correlation_id: str = "",
        now: str | None = None,
    ) -> ConnectorRegistration:
        payload = manifest.to_dict() if isinstance(manifest, ConnectorManifest) else dict(manifest)
        connector_id = str(payload.get("connector_id", ""))
        if not seed_id or not source.source_id or not connector_id:
            raise ConnectorRegistryError("seed, source, and connector identities are required")
        registration_id = source.source_id
        existing = self.load(seed_id, registration_id)
        if existing is not None and existing.state in _ACTIVE_STATES:
            if existing.source == source and existing.manifest == payload:
                return existing
            raise ConnectorRegistryError(
                f"connector {source.source_id!r} is already registered with different evidence"
            )
        stamp = self._now(now)
        registration = ConnectorRegistration(
            registration_id=registration_id,
            seed_id=seed_id,
            connector_id=connector_id,
            source=source,
            manifest=payload,
            state="registered",
            actor=actor,
            created_at=stamp,
            updated_at=stamp,
            correlation_id=correlation_id,
        )
        self._audit("connector.registered", registration)
        self._save(registration)
        return registration

    def _transition(
        self,
        seed_id: str,
        source_id: str,
        state: str,
        *,
        actor: str,
        reason: str,
        failure: str,
        correlation_id: str,
        now: str | None,
    ) -> ConnectorRegistration:
        current = self.load(seed_id, source_id)
        if current is None:
            raise ConnectorRegistryError(f"connector {source_id!r} is not registered")
        if current.state == state:
            return current
        if current.state == "removed":
            raise ConnectorRegistryError(f"connector {source_id!r} has already been removed")
        stamp = self._now(now)
        updated = ConnectorRegistration(
            registration_id=current.registration_id,
            seed_id=current.seed_id,
            connector_id=current.connector_id,
            source=current.source,
            manifest=current.manifest,
            state=state,
            actor=actor,
            created_at=current.created_at,
            updated_at=stamp,
            correlation_id=correlation_id or current.correlation_id,
            reason=reason,
            failure=failure,
        )
        self._audit(f"connector.{state}", updated)
        self._save(updated)
        return updated

    def remove(
        self,
        seed_id: str,
        source_id: str,
        *,
        actor: str,
        reason: str = "",
        correlation_id: str = "",
        now: str | None = None,
    ) -> ConnectorRegistration:
        return self._transition(
            seed_id,
            source_id,
            "removed",
            actor=actor,
            reason=reason,
            failure="",
            correlation_id=correlation_id,
            now=now,
        )

    def revoke(
        self,
        seed_id: str,
        source_id: str,
        *,
        actor: str,
        reason: str = "",
        correlation_id: str = "",
        now: str | None = None,
    ) -> ConnectorRegistration:
        return self._transition(
            seed_id,
            source_id,
            "revoked",
            actor=actor,
            reason=reason,
            failure="",
            correlation_id=correlation_id,
            now=now,
        )

    def record_failure(
        self,
        seed_id: str,
        source_id: str,
        *,
        actor: str,
        failure: str,
        correlation_id: str = "",
        now: str | None = None,
    ) -> ConnectorRegistration:
        current = self.load(seed_id, source_id)
        if current is None:
            stamp = self._now(now)
            failed = ConnectorRegistration(
                registration_id=source_id,
                seed_id=seed_id,
                connector_id="connector.local-source",
                source=None,
                manifest={},
                state="failed",
                actor=actor,
                created_at=stamp,
                updated_at=stamp,
                correlation_id=correlation_id,
                failure=failure,
            )
            self._audit("connector.failed", failed)
            self._save(failed)
            return failed
        return self._transition(
            seed_id,
            source_id,
            "failed",
            actor=actor,
            reason="",
            failure=failure,
            correlation_id=correlation_id,
            now=now,
        )

    def load(self, seed_id: str, source_id: str) -> ConnectorRegistration | None:
        path = self._path(seed_id, source_id)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise TypeError("record must be a mapping")
            return ConnectorRegistration.from_dict(raw)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            ConnectorRegistryError,
        ) as exc:
            raise ConnectorRegistryError(f"corrupt connector registration {path}") from exc

    def all_for_seed(self, seed_id: str) -> list[ConnectorRegistration]:
        root = self.root / _safe_segment(seed_id)
        if not root.is_dir():
            return []
        return [
            registration
            for path in sorted(root.glob("*.json"))
            if (registration := self.load(seed_id, path.stem)) is not None
        ]

    def active_for_seed(self, seed_id: str) -> list[ConnectorRegistration]:
        return [
            registration
            for registration in self.all_for_seed(seed_id)
            if registration.state in _ACTIVE_STATES
        ]


@dataclass
class SqlConnectorRegistry(FileConnectorRegistry):
    """SQL lifecycle snapshots using the same domain record and audit seam as the file store."""

    session_factory: Callable[[], SqlSession] = open_archive_session

    def _save(self, registration: ConnectorRegistration) -> None:
        payload = json.dumps(registration.to_dict(), sort_keys=True, separators=(",", ":"))
        with self.session_factory() as session, session.begin():
            row = session.get(
                SeedConnectorRow, (registration.seed_id, registration.registration_id)
            )
            if row is None:
                session.add(
                    SeedConnectorRow(
                        seed_id=registration.seed_id,
                        registration_id=registration.registration_id,
                        registration_json=payload,
                    )
                )
            else:
                row.registration_json = payload

    def load(self, seed_id: str, source_id: str) -> ConnectorRegistration | None:
        with self.session_factory() as session:
            row = session.get(SeedConnectorRow, (seed_id, source_id))
        if row is None:
            return None
        try:
            raw = json.loads(row.registration_json)
            if not isinstance(raw, dict):
                raise TypeError("record must be a mapping")
            return ConnectorRegistration.from_dict(raw)
        except (json.JSONDecodeError, TypeError, ConnectorRegistryError) as exc:
            raise ConnectorRegistryError(
                f"corrupt SQL connector registration {seed_id}/{source_id}"
            ) from exc

    def all_for_seed(self, seed_id: str) -> list[ConnectorRegistration]:
        with self.session_factory() as session:
            rows = (
                session.query(SeedConnectorRow)
                .filter(SeedConnectorRow.seed_id == seed_id)
                .order_by(SeedConnectorRow.registration_id)
                .all()
            )
        return [self.load(seed_id, row.registration_id) for row in rows if row is not None]


def configured_connector_registry(home: Path) -> ConnectorRegistry:
    """Open the durable connector lifecycle registry for a SeedLab home."""
    backend = os.environ.get("CODEFORGE_CONNECTOR_REGISTRY", "file").strip() or "file"
    if backend in {"sql", "sql-dual-read"}:
        return SqlConnectorRegistry(Path(home) / "connectors")
    if backend != "file":
        raise ConnectorRegistryError(
            f"unknown connector registry backend {backend!r}; expected file or sql"
        )
    return FileConnectorRegistry(Path(home) / "connectors")
