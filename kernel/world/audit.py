"""CARD: audit -- a tamper-evident log of who did what: admin and economy actions, hash-chained.

Phase 3 observability. Significant actions (an owner granting a rank, an auction sale, a ban) are
appended here as an evidence record, so a live server can be held accountable and an incident
reconstructed. The log is a hash-chained JSONL ledger (kernel.shelf.hashchain): each entry seals a
sha256 over its own payload AND the previous entry's hash, so any later edit, reorder, or removal of
a PAST record is caught the next time the log is read. Integrity, not authenticity: it proves the
history was not altered, not who altered it.

Append-only and off to the side of the world: recording an action never mutates game state and never
fails a command (a broken audit path must not stop the forge). The path is env-overridable
(CODEFORGE_AUDIT) and defaults beside the database at the repo root; runtime state, git-ignored.
"""

from __future__ import annotations

import contextlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kernel.shelf import hashchain
from kernel.world.db import AuditEventRow, open_archive_session
from kernel.world.paths import resolved_path


class AuditStoreError(ValueError):
    """The world-owned audit ledger is malformed or its chain is broken."""


def _audit_path() -> Path:
    """Where the audit ledger lives: CODEFORGE_AUDIT, else `audit.jsonl` at the repo root. Resolved
    at call time so tests (and a container) can quarantine it via the env var."""
    return resolved_path(
        "CODEFORGE_AUDIT",
        Path(__file__).resolve().parent.parent.parent / "audit.jsonl",  # kernel/world/ -> repo root
    )


def _file_records() -> list[dict[str, Any]]:
    try:
        return [link.payload for link in hashchain.read(_audit_path())]
    except hashchain.HashChainError as exc:
        raise AuditStoreError(str(exc)) from exc


def _sql_records() -> list[dict[str, Any]]:
    with open_archive_session() as session:
        rows = session.query(AuditEventRow).order_by(AuditEventRow.sequence).all()
    previous = hashchain.GENESIS
    records: list[dict[str, Any]] = []
    for expected, row in enumerate(rows):
        try:
            payload = json.loads(row.payload_json)
        except json.JSONDecodeError as exc:
            raise AuditStoreError(f"corrupt SQL audit record {row.sequence}") from exc
        if (
            not isinstance(payload, dict)
            or row.sequence != expected
            or row.prior_hash != previous
            or row.content_hash
            != hashchain.content_hash(
                {"seq": row.sequence, "payload": payload, "prior_hash": row.prior_hash}
            )
        ):
            raise AuditStoreError("audit chain is corrupt")
        records.append(payload)
        previous = row.content_hash
    return records


def _records() -> list[dict[str, Any]]:
    backend = os.environ.get("CODEFORGE_AUDIT_BACKEND", "").strip()
    if not backend:
        backend = os.environ.get("CODEFORGE_SEED_REGISTRY", "file").strip() or "file"
    if backend == "file":
        return _file_records()
    if backend == "sql":
        return _sql_records()
    if backend == "sql-dual-read":
        records = [*_sql_records(), *_file_records()]
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for payload in records:
            key = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            if key not in seen:
                seen.add(key)
                unique.append(payload)
        return unique
    raise AuditStoreError(
        f"unknown audit store backend {backend!r}; expected file, sql, or sql-dual-read"
    )


def record(actor: str, action: str, detail: str = "", *, ts: str | None = None) -> None:
    """Append one audit entry: who (actor), what (action), and any detail, timestamped. Best-effort:
    an unwritable audit path is swallowed, because failing to LOG an action must never abort the
    action itself. Pass `ts` in tests for a deterministic stamp."""
    stamp = ts or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {"ts": stamp, "actor": actor, "action": action, "detail": detail}
    with contextlib.suppress(OSError, AuditStoreError, hashchain.HashChainError):
        backend = os.environ.get("CODEFORGE_AUDIT_BACKEND", "").strip()
        if not backend:
            backend = os.environ.get("CODEFORGE_SEED_REGISTRY", "file").strip() or "file"
        if backend == "file":
            hashchain.append(_audit_path(), entry)
            return
        if backend == "sql" or backend == "sql-dual-read":
            encoded = json.dumps(entry, sort_keys=True, separators=(",", ":"))
            with open_archive_session() as session, session.begin():
                previous = (
                    session.query(AuditEventRow).order_by(AuditEventRow.sequence.desc()).first()
                )
                sequence = 0 if previous is None else previous.sequence + 1
                prior_hash = hashchain.GENESIS if previous is None else previous.content_hash
                content_hash = hashchain.content_hash(
                    {"seq": sequence, "payload": entry, "prior_hash": prior_hash}
                )
                session.add(
                    AuditEventRow(
                        sequence=sequence,
                        payload_json=encoded,
                        prior_hash=prior_hash,
                        content_hash=content_hash,
                    )
                )
            if backend == "sql-dual-read":
                hashchain.append(_audit_path(), entry)
            return
        raise AuditStoreError(
            f"unknown audit store backend {backend!r}; expected file, sql, or sql-dual-read"
        )


def tail(limit: int = 20) -> list[dict[str, Any]]:
    """The most recent audit entries (their payloads), oldest of the slice first. Verifies the chain
    on read; a tampered ledger raises HashChainError rather than returning a dishonest history."""
    if limit <= 0:
        return []
    return _records()[-limit:]


def verify() -> bool:
    """True if the audit ledger reads clean end to end, False if any past record was tampered."""
    try:
        _records()
        return True
    except (AuditStoreError, OSError, hashchain.HashChainError):
        return False
