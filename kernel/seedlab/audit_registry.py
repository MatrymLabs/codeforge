"""Configured persistence for the platform's tamper-evident audit ledger.

The legacy JSONL hash-chain remains the default. SQL and dual-read modes preserve the same payload
and chain semantics while allowing audit records to survive alongside the platform's other durable
SeedLab evidence.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session as SqlSession

from kernel.shelf import hashchain
from kernel.world.db import AuditEventRow, open_archive_session


class AuditStoreError(ValueError):
    """An audit record is malformed, corrupt, or its chain is broken."""


@runtime_checkable
class AuditStore(Protocol):
    """Persistence seam for append-only audit payloads."""

    def append(self, payload: dict[str, object]) -> None: ...

    def all_records(self) -> list[dict[str, object]]: ...

    def tail(self, limit: int = 20) -> list[dict[str, object]]: ...

    def verify(self) -> bool: ...


@dataclass
class FileAuditStore:
    """Hash-chain JSONL audit store used by the compatibility default."""

    path: Path

    def append(self, payload: dict[str, object]) -> None:
        try:
            hashchain.append(Path(self.path), payload)
        except hashchain.HashChainError as exc:
            raise AuditStoreError(str(exc)) from exc

    def tail(self, limit: int = 20) -> list[dict[str, object]]:
        if limit <= 0:
            return []
        return self.all_records()[-limit:]

    def all_records(self) -> list[dict[str, object]]:
        try:
            return [link.payload for link in hashchain.read(Path(self.path))]
        except hashchain.HashChainError as exc:
            raise AuditStoreError(str(exc)) from exc

    def verify(self) -> bool:
        return hashchain.verify(Path(self.path))


@dataclass
class SqlAuditStore:
    """Append-only hash-chain audit store using the platform SQL boundary."""

    session_factory: Callable[[], SqlSession] = open_archive_session

    def append(self, payload: dict[str, object]) -> None:
        try:
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise AuditStoreError(f"audit payload is not JSON-serializable: {exc}") from exc
        with self.session_factory() as session, session.begin():
            previous = (
                session.query(AuditEventRow)
                .order_by(AuditEventRow.sequence.desc())
                .first()
            )
            sequence = 0 if previous is None else previous.sequence + 1
            prior_hash = hashchain.GENESIS if previous is None else previous.content_hash
            content_hash = hashchain.content_hash(
                {
                    "seq": sequence,
                    "payload": payload,
                    "prior_hash": prior_hash,
                }
            )
            session.add(
                AuditEventRow(
                    sequence=sequence,
                    payload_json=encoded,
                    prior_hash=prior_hash,
                    content_hash=content_hash,
                )
            )

    def tail(self, limit: int = 20) -> list[dict[str, object]]:
        if limit <= 0:
            return []
        return self.all_records()[-limit:]

    def all_records(self) -> list[dict[str, object]]:
        if not self.verify():
            raise AuditStoreError("audit chain is corrupt")
        with self.session_factory() as session:
            rows = (
                session.query(AuditEventRow)
                .order_by(AuditEventRow.sequence)
                .all()
            )
        return [self._decode(row) for row in rows]

    def verify(self) -> bool:
        try:
            with self.session_factory() as session:
                rows = session.query(AuditEventRow).order_by(AuditEventRow.sequence).all()
            previous = hashchain.GENESIS
            for expected, row in enumerate(rows):
                payload = self._payload(row)
                if row.sequence != expected or row.prior_hash != previous:
                    return False
                expected_hash = hashchain.content_hash(
                    {
                        "seq": row.sequence,
                        "payload": payload,
                        "prior_hash": row.prior_hash,
                    }
                )
                if row.content_hash != expected_hash:
                    return False
                previous = row.content_hash
            return True
        except (AuditStoreError, OSError):
            return False

    @classmethod
    def _payload(cls, row: AuditEventRow) -> dict[str, object]:
        try:
            payload = json.loads(row.payload_json)
            if not isinstance(payload, dict):
                raise TypeError("payload must be a mapping")
            return payload
        except (TypeError, json.JSONDecodeError) as exc:
            raise AuditStoreError(f"corrupt SQL audit record {row.sequence}") from exc

    @classmethod
    def _decode(cls, row: AuditEventRow) -> dict[str, object]:
        return cls._payload(row)


@dataclass
class DualReadAuditStore:
    """Read legacy JSONL audit records while appending new records to SQL."""

    primary: AuditStore
    legacy: AuditStore

    def append(self, payload: dict[str, object]) -> None:
        self.primary.append(payload)

    def all_records(self) -> list[dict[str, object]]:
        seen: set[str] = set()
        records: list[dict[str, object]] = []
        for payload in [*self.primary.all_records(), *self.legacy.all_records()]:
            key = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            if key not in seen:
                seen.add(key)
                records.append(payload)
        return records

    def tail(self, limit: int = 20) -> list[dict[str, object]]:
        if limit <= 0:
            return []
        return self.all_records()[-limit:]

    def verify(self) -> bool:
        return self.primary.verify() and self.legacy.verify()


def audit_store(backend: str, path: Path) -> AuditStore:
    """Build the audit store selected by explicit or shared platform configuration."""
    if backend == "file":
        return FileAuditStore(Path(path))
    primary = SqlAuditStore()
    if backend == "sql":
        return primary
    if backend == "sql-dual-read":
        return DualReadAuditStore(primary, FileAuditStore(Path(path)))
    raise AuditStoreError(
        f"unknown audit store backend {backend!r}; expected file, sql, or sql-dual-read"
    )


def configured_audit_store(path: Path) -> AuditStore:
    """Open audit persistence, sharing the SeedLab backend unless explicitly overridden."""
    backend = os.environ.get("CODEFORGE_AUDIT_BACKEND", "").strip()
    if not backend:
        backend = os.environ.get("CODEFORGE_SEED_REGISTRY", "file").strip() or "file"
    return audit_store(backend, path)
