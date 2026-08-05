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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kernel.seedlab.audit_registry import AuditStoreError, configured_audit_store
from kernel.shelf import hashchain
from kernel.world.paths import resolved_path


def _audit_path() -> Path:
    """Where the audit ledger lives: CODEFORGE_AUDIT, else `audit.jsonl` at the repo root. Resolved
    at call time so tests (and a container) can quarantine it via the env var."""
    return resolved_path(
        "CODEFORGE_AUDIT",
        Path(__file__).resolve().parent.parent.parent / "audit.jsonl",  # kernel/world/ -> repo root
    )


def record(actor: str, action: str, detail: str = "", *, ts: str | None = None) -> None:
    """Append one audit entry: who (actor), what (action), and any detail, timestamped. Best-effort:
    an unwritable audit path is swallowed, because failing to LOG an action must never abort the
    action itself. Pass `ts` in tests for a deterministic stamp."""
    stamp = ts or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {"ts": stamp, "actor": actor, "action": action, "detail": detail}
    with contextlib.suppress(OSError, AuditStoreError, hashchain.HashChainError):
        configured_audit_store(_audit_path()).append(entry)


def tail(limit: int = 20) -> list[dict[str, Any]]:
    """The most recent audit entries (their payloads), oldest of the slice first. Verifies the chain
    on read; a tampered ledger raises HashChainError rather than returning a dishonest history."""
    return configured_audit_store(_audit_path()).tail(limit)


def verify() -> bool:
    """True if the audit ledger reads clean end to end, False if any past record was tampered."""
    return configured_audit_store(_audit_path()).verify()
