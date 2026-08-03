"""CARD: backup -- snapshot a Seed's persisted state to a portable, hash-verified archive and
restore (or roll back) from it, so a Seed survives loss, not just restart.

The Kernel (kernel/seedlab/kernel.py) already makes a Seed survive restart: a fresh Kernel over the
same store recovers every Seed. That is not the same as surviving LOSS -- a deleted or corrupted
store, or a bad change an owner wants to undo. The platform's definition of done for any Seed
feature includes back up -> restore -> roll back; this is that capability, kept small and honest:

  * `SeedBackups.backup(record)`        -- snapshot one SeedRecord to `<root>/<seed_id>/<id>.json`,
    wrapped with a schema version, timestamp, and a sha256 of the canonical record bytes.
  * `SeedBackups.list_backups(seed_id)` -- the refs for a Seed, newest last.
  * `SeedBackups.verify(seed_id, id)`   -- re-hash the snapshot and return an integrity VERDICT
    (INTACT / CORRUPT / MISSING) -- a verdict word, never a bare bool.
  * `SeedBackups.load_record(seed_id, id)` -- verify then rebuild the SeedRecord, failing loud on a
    corrupt or missing snapshot rather than restoring a lie.
  * `restore(kernel, backups, seed_id, id, actor)` -- the composed path: load the snapshot, then
    reinstate it THROUGH the Kernel (owner-authorized + audited). Restore is rollback; the same call
    undoes a bad change or recovers a lost Seed.

Grammar before worlds: this is domain-neutral platform code -- no game import, no world graph. The
clock is injected (deterministic ids in tests); durability is plain files. Status: PROTOTYPED
(see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kernel.seedlab.kernel import SeedKernel, SeedKernelError, SeedRecord

# --- integrity verdict words (a distinct vocabulary: "is this snapshot trustworthy?") ----------
INTACT = "intact"  # the snapshot's bytes hash to its recorded sha256
CORRUPT = "corrupt"  # the snapshot exists but its bytes no longer match the recorded hash
MISSING = "missing"  # no snapshot with that id for that Seed

_SCHEMA = 1  # the on-disk wrapper version, so an old backup can be read (or refused) knowingly
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


class BackupError(SeedKernelError):
    """A backup could not be written, found, read, or trusted. Fails loud, never restores a lie."""


def _utcnow() -> str:
    """Wall clock as ISO-8601 UTC. Injected so tests pin a fixed clock and get stable ids."""
    return datetime.now(UTC).isoformat()


def _canonical(record: SeedRecord) -> bytes:
    """The canonical bytes a snapshot hashes over: the record dict, key-sorted, compact. Two runs
    of the same record produce identical bytes, so the sha256 is a stable content fingerprint."""
    return json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class BackupRef:
    """A pointer to one snapshot: which Seed, when, its content hash, and where it lives. Frozen;
    a ref is a fact about a snapshot that already exists on disk."""

    backup_id: str
    seed_id: str
    when: str
    sha256: str
    path: str


@dataclass
class SeedBackups:
    """Durable, hash-verified snapshots of Seed records under `root`, one directory per Seed. Owns
    durability + integrity only; it never authorizes a write to live state -- `restore` routes that
    through the Kernel so the control plane stays the single door to a Seed's current state."""

    root: Path
    clock: Callable[[], str] = _utcnow

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _seed_dir(self, seed_id: str) -> Path:
        return self.root / _UNSAFE.sub("_", seed_id)

    def backup(self, record: SeedRecord) -> BackupRef:
        """Snapshot `record` to a portable, self-verifying archive; return its ref. Write-to-temp-
        then-replace, so a crash mid-write never leaves a half-written snapshot."""
        when = self.clock()
        sha256 = hashlib.sha256(_canonical(record)).hexdigest()
        backup_id = f"bk-{_UNSAFE.sub('_', when)}-{sha256[:8]}"
        seed_dir = self._seed_dir(record.identity.seed_id)
        seed_dir.mkdir(parents=True, exist_ok=True)
        target = seed_dir / f"{backup_id}.json"
        wrapper = {
            "schema": _SCHEMA,
            "seed_id": record.identity.seed_id,
            "backup_id": backup_id,
            "when": when,
            "sha256": sha256,
            "record": record.to_dict(),
        }
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(wrapper, indent=2), encoding="utf-8")
        tmp.replace(target)
        return BackupRef(backup_id, record.identity.seed_id, when, sha256, str(target))

    def list_backups(self, seed_id: str) -> list[BackupRef]:
        """Every snapshot for a Seed, oldest first (sorted by id, which begins with the timestamp).
        A snapshot too corrupt to even parse its wrapper is skipped here (surface it via
        `verify`)."""
        seed_dir = self._seed_dir(seed_id)
        if not seed_dir.is_dir():
            return []
        refs: list[BackupRef] = []
        for path in sorted(seed_dir.glob("bk-*.json")):
            try:
                w = json.loads(path.read_text(encoding="utf-8"))
                refs.append(
                    BackupRef(w["backup_id"], w["seed_id"], w["when"], w["sha256"], str(path))
                )
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        return refs

    def _read_wrapper(self, seed_id: str, backup_id: str) -> dict | None:
        path = self._seed_dir(seed_id) / f"{backup_id}.json"
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise BackupError(f"unreadable backup {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise BackupError(f"malformed backup {path}: not an object")
        return data

    def verify(self, seed_id: str, backup_id: str) -> str:
        """Integrity verdict for one snapshot: INTACT if its stored record still hashes to its
        recorded sha256, CORRUPT if the bytes have drifted, MISSING if there is no such snapshot."""
        wrapper = self._read_wrapper(seed_id, backup_id)
        if wrapper is None:
            return MISSING
        try:
            record = SeedRecord.from_dict(wrapper["record"])
            recorded = wrapper["sha256"]
        except (KeyError, SeedKernelError):
            return CORRUPT
        return INTACT if hashlib.sha256(_canonical(record)).hexdigest() == recorded else CORRUPT

    def load_record(self, seed_id: str, backup_id: str) -> SeedRecord:
        """Rebuild the SeedRecord from a snapshot, refusing anything but an INTACT one. Fails loud
        so a corrupt or missing snapshot can never be restored as if it were the truth."""
        verdict = self.verify(seed_id, backup_id)
        if verdict != INTACT:
            raise BackupError(f"backup {backup_id!r} for Seed {seed_id!r} is {verdict}")
        wrapper = self._read_wrapper(seed_id, backup_id)
        assert wrapper is not None  # verify already proved it exists and is intact
        return SeedRecord.from_dict(wrapper["record"])


def restore(
    kernel: SeedKernel,
    backups: SeedBackups,
    seed_id: str,
    backup_id: str,
    actor: str,
) -> SeedRecord:
    """Restore (or roll back) a Seed to a snapshot: load the verified record, then reinstate it
    THROUGH the Kernel so the write is owner-authorized and audited. The same call recovers a lost
    Seed and undoes a bad change -- restore is rollback. Fails loud if the snapshot is not
    intact."""
    record = backups.load_record(seed_id, backup_id)
    return kernel.reinstate(record, actor, detail=f"restored from backup {backup_id}")
