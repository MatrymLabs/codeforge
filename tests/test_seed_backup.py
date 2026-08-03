"""Test twin for kernel/seedlab/backup.py -- snapshot, verify, restore, roll back a Seed.

Acceptance: the mandatory lifecycle the platform requires of every Seed feature --
create -> operate -> backup -> LOSE -> restore -> verify. A Seed that is backed up survives total
loss of its store (not just a restart), and a fresh Kernel over the recovered store reads back the
exact identity + state. Restore is rollback: a later backup can undo a bad change. `verify` reports
an honest integrity verdict (INTACT / CORRUPT / MISSING).

Refusal (fail loud, never restore a lie): a non-owner cannot restore; a corrupt or missing snapshot
is refused rather than reinstated; a tampered snapshot verifies CORRUPT, not INTACT.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.seedlab.backup import (
    CORRUPT,
    INTACT,
    MISSING,
    BackupError,
    SeedBackups,
    restore,
)
from kernel.seedlab.kernel import (
    RUNNING,
    STOPPED,
    FileSeedStore,
    SeedAuthError,
    SeedKernel,
    SeedNotFound,
)

# A fixed clock so backup ids (which embed the timestamp) are deterministic across a run.
_CLOCK = iter(f"2026-08-02T00:00:{n:02d}+00:00" for n in range(60))


def _tick() -> str:
    return next(_CLOCK)


def _kernel(root: Path) -> SeedKernel:
    return SeedKernel(FileSeedStore(root / "seeds"), clock=_tick)


def _backups(root: Path) -> SeedBackups:
    return SeedBackups(root / "backups", clock=_tick)


# --- acceptance: the mandatory create -> operate -> backup -> LOSE -> restore -> verify ----------


def test_seed_survives_total_loss_via_backup_restore(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    backups = _backups(tmp_path)

    # create -> operate
    record = kernel.create_seed("Task Ledger", "josh", "a tiny tracker", seed_id="seed-01")
    kernel.start("seed-01", "josh")
    stopped = kernel.stop("seed-01", "josh")
    assert stopped.status == STOPPED

    # backup captures the operated state
    ref = backups.backup(stopped)
    assert ref.seed_id == "seed-01"
    assert backups.verify("seed-01", ref.backup_id) == INTACT

    # LOSE the store entirely (not a restart -- a deletion)
    seed_file = tmp_path / "seeds" / "seed-01.json"
    assert seed_file.is_file()
    seed_file.unlink()
    with pytest.raises(SeedNotFound):
        _kernel(tmp_path).get("seed-01")  # gone

    # restore through the Kernel (owner-authorized), then a FRESH Kernel recovers the exact state
    restored = restore(kernel, backups, "seed-01", ref.backup_id, "josh")
    assert restored.status == STOPPED
    recovered = _kernel(tmp_path).get("seed-01")
    assert recovered.identity == record.identity
    assert recovered.status == STOPPED
    assert recovered.identity.owner == "josh"
    # the restore is itself audited (traceable rollback)
    assert recovered.audit[-1].action == "reinstated"


def test_restore_is_rollback_undoes_a_bad_change(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    backups = _backups(tmp_path)
    kernel.create_seed("World", "josh", "", seed_id="seed-02")
    kernel.start("seed-02", "josh")  # CREATED -> RUNNING
    good = kernel.stop("seed-02", "josh")  # RUNNING -> STOPPED (the "good" state)
    ref = backups.backup(good)

    # a "bad change": start it again (now RUNNING)
    now_running = kernel.start("seed-02", "josh")
    assert now_running.status == RUNNING

    # roll back to the STOPPED snapshot
    rolled = restore(kernel, backups, "seed-02", ref.backup_id, "josh")
    assert rolled.status == STOPPED
    assert kernel.get("seed-02").status == STOPPED


def test_verify_reports_intact_missing_and_corrupt(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    backups = _backups(tmp_path)
    record = kernel.create_seed("Probe", "josh", "", seed_id="seed-03")
    ref = backups.backup(record)

    assert backups.verify("seed-03", ref.backup_id) == INTACT
    assert backups.verify("seed-03", "bk-does-not-exist") == MISSING

    # tamper the stored record bytes WITHOUT updating the recorded hash -> CORRUPT
    path = Path(ref.path)
    text = path.read_text(encoding="utf-8").replace('"josh"', '"mallory"')
    path.write_text(text, encoding="utf-8")
    assert backups.verify("seed-03", ref.backup_id) == CORRUPT


def test_list_backups_returns_refs_newest_last(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    backups = _backups(tmp_path)
    record = kernel.create_seed("Multi", "josh", "", seed_id="seed-04")
    first = backups.backup(record)
    second = backups.backup(kernel.start("seed-04", "josh"))
    refs = backups.list_backups("seed-04")
    assert [r.backup_id for r in refs] == sorted([first.backup_id, second.backup_id])
    assert backups.list_backups("no-such-seed") == []


# --- refusal: fail loud, never restore a lie ---------------------------------------------------


def test_non_owner_cannot_restore(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    backups = _backups(tmp_path)
    record = kernel.create_seed("Owned", "josh", "", seed_id="seed-05")
    ref = backups.backup(record)
    with pytest.raises(SeedAuthError):
        restore(kernel, backups, "seed-05", ref.backup_id, "mallory")


def test_restore_of_corrupt_backup_is_refused(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    backups = _backups(tmp_path)
    record = kernel.create_seed("Fragile", "josh", "", seed_id="seed-06")
    ref = backups.backup(record)
    path = Path(ref.path)
    path.write_text(path.read_text(encoding="utf-8").replace('"josh"', '"eve"'), encoding="utf-8")
    with pytest.raises(BackupError):
        restore(kernel, backups, "seed-06", ref.backup_id, "josh")


def test_restore_of_missing_backup_is_refused(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    backups = _backups(tmp_path)
    kernel.create_seed("Present", "josh", "", seed_id="seed-07")
    with pytest.raises(BackupError):
        restore(kernel, backups, "seed-07", "bk-nope", "josh")
