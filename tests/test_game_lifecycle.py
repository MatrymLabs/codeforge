"""Test twin for kernel/domains/game_lifecycle.py -- the linked-region durability lifecycle.

Acceptance: a linked region (rooms, and rooms+quest) survives the CREATE -> BACKUP -> RESTORE ->
VERIFY loop -> RECOVERED, its files coming back byte-identical and still booting through the real
loader. The snapshot IS the emitted files' fingerprint.

Refusal (fail loud, never a false RECOVERED): a region that never links is REFUSED (nothing to
prove); a file whose bytes changed, or that went missing, after backup is CORRUPTED; content that is
byte-intact but no longer forms a valid world (an orphan crept in) is CORRUPTED, not RECOVERED.
"""

from __future__ import annotations

from pathlib import Path

from kernel.domains.game_lifecycle import (
    CORRUPTED,
    RECOVERED,
    REFUSED,
    prove_lifecycle,
    snapshot,
    verify_recovery,
)
from kernel.domains.game_linker import (
    GameSpec,
    QuestArc,
    QuestStep,
    RoomSpec,
    _sha256,
    link_and_validate,
    link_region,
)

_REGION = GameSpec(
    region="veridia",
    start="gate",
    rooms=(
        RoomSpec(label="gate", exits={"north": "greenhold"}),
        RoomSpec(label="greenhold", exits={"south": "gate"}),
    ),
    quest=QuestArc(
        id="first_road",
        start="offered",
        steps=(
            QuestStep(state="offered", event="accept", to="accepted"),
            QuestStep(state="accepted", event="enter", to="done", on_enter="greenhold"),
        ),
        terminal=("done",),
    ),
)
_ROOMS_ONLY = GameSpec(
    region="ironhold",
    start="gate",
    rooms=(
        RoomSpec(label="gate", exits={"north": "yard"}),
        RoomSpec(label="yard", exits={"south": "gate"}),
    ),
)


# --- acceptance: the full loop recovers ----------------------------------------------------------


def test_a_linked_region_with_a_quest_survives_the_full_loop(tmp_path: Path) -> None:
    report = prove_lifecycle(_REGION, tmp_path)
    assert report.verdict == RECOVERED and report.ok is True
    assert report.files == (
        "quest.yaml",
        "rooms.yaml",
    )  # both durable files verified byte-identical


def test_a_rooms_only_region_recovers(tmp_path: Path) -> None:
    report = prove_lifecycle(_ROOMS_ONLY, tmp_path)
    assert report.verdict == RECOVERED and report.files == ("rooms.yaml",)


def test_snapshot_is_the_files_fingerprint(tmp_path: Path) -> None:
    linked = link_region(_REGION, tmp_path)
    assert snapshot(linked) == linked.checksums


# --- refusal: fail loud, never a false RECOVERED -------------------------------------------------


def test_a_region_that_does_not_link_is_refused(tmp_path: Path) -> None:
    broken = GameSpec(
        region="broken", start="gate", rooms=(RoomSpec(label="gate", exits={"north": "nowhere"}),)
    )
    report = prove_lifecycle(broken, tmp_path)
    assert report.verdict == REFUSED and "did not link" in report.detail


def test_tampered_bytes_after_backup_are_corrupt(tmp_path: Path) -> None:
    linked, _ = link_and_validate(_REGION, tmp_path)
    snap = snapshot(linked)
    # A byte changes on disk after the backup (bit-rot / bad edit); the snapshot no longer matches.
    (tmp_path / "rooms.yaml").write_text("gate:\n  exits: {north: greenhold}\ngreenhold: {}\n")
    report = verify_recovery(linked, snap)
    assert report.verdict == CORRUPTED and "rooms.yaml" in report.detail


def test_a_missing_file_after_backup_is_corrupt(tmp_path: Path) -> None:
    linked, _ = link_and_validate(_REGION, tmp_path)
    snap = snapshot(linked)
    (tmp_path / "quest.yaml").unlink()  # the quest file is lost after backup
    report = verify_recovery(linked, snap)
    assert (
        report.verdict == CORRUPTED and "missing" in report.detail and "quest.yaml" in report.detail
    )


def test_byte_intact_but_no_longer_a_valid_world_is_corrupt(tmp_path: Path) -> None:
    # Bytes on disk match the snapshot, but the content no longer forms a valid world (an orphan
    # room the start can't reach). Recovery must catch it (CORRUPTED), not a false RECOVERED.
    linked = link_region(_ROOMS_ONLY, tmp_path)
    orphaned = "gate:\n  exits: {north: yard}\nisland: {}\nyard:\n  exits: {south: gate}\n"
    (tmp_path / "rooms.yaml").write_text(orphaned, encoding="utf-8")
    snap = {"rooms.yaml": _sha256(orphaned)}  # a backup taken OF the (loadable but orphaned) bytes
    report = verify_recovery(linked, snap)
    assert report.verdict == CORRUPTED and "no longer links" in report.detail
