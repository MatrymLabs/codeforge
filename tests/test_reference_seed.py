"""Test twin for kernel/seedlab/reference_seed.py -- the game as a reference Seed (Stage 8).

Acceptance: the Aethryn game registers idempotently as a Seed with a stable id, is recognizable as
the reference Seed, appears in the Kernel's list beside engineering Seeds, and survives restart --
all through the same Kernel, with no game-specific fields added to it.
"""

from __future__ import annotations

from pathlib import Path

from kernel.seedlab.kernel import BlueprintKernel, FileSeedStore, InMemorySeedStore
from kernel.seedlab.reference_seed import (
    AETHRYN_SEED_ID,
    ensure_reference_seed,
    is_reference_seed,
)


def _kernel() -> BlueprintKernel:
    return BlueprintKernel(InMemorySeedStore(), clock=lambda: "2026-08-01T00:00:00+00:00")


def test_registers_the_game_with_a_stable_id() -> None:
    record = ensure_reference_seed(_kernel())
    assert record.identity.seed_id == AETHRYN_SEED_ID
    assert record.identity.name == "Aethryn" and "game" in record.identity.purpose
    assert is_reference_seed(record)


def test_is_idempotent() -> None:
    k = _kernel()
    first = ensure_reference_seed(k)
    second = ensure_reference_seed(k)  # a second call recovers, never duplicates
    assert first == second
    assert len(k.list_seeds()) == 1


def test_appears_beside_engineering_seeds() -> None:
    k = _kernel()
    k.create_seed("TaskLedger", "josh", "a tool", seed_id="seed-eng-1")
    ensure_reference_seed(k)
    ids = {r.identity.seed_id for r in k.list_seeds()}
    assert ids == {"seed-eng-1", AETHRYN_SEED_ID}


def test_detail_rides_the_purpose() -> None:
    record = ensure_reference_seed(_kernel(), detail="53,778 rooms")
    assert "53,778 rooms" in record.identity.purpose


def test_survives_restart(tmp_path: Path) -> None:
    ensure_reference_seed(BlueprintKernel(FileSeedStore(tmp_path / "seeds")))
    # A fresh Kernel over the same store recovers the reference Seed (idempotent, no duplicate).
    k2 = BlueprintKernel(FileSeedStore(tmp_path / "seeds"))
    again = ensure_reference_seed(k2)
    assert again.identity.seed_id == AETHRYN_SEED_ID and len(k2.list_seeds()) == 1


def test_a_plain_seed_is_not_the_reference() -> None:
    k = _kernel()
    other = k.create_seed("Other", "josh", "x", seed_id="seed-other")
    assert not is_reference_seed(other)
