"""Test twin for kernel/domains/game_linker.py -- the game domain's Spec -> persistent-world Linker.

Acceptance: a valid GameSpec emits real `rooms.yaml` that loads through the ENGINE'S OWN loader
(kernel.world.seed.load_rooms, not a mock) with every room reachable from the start -> LINKED; the
emit is deterministic (byte-identical + same checksums), so a Seed booting it is reproducible.

Refusal (fail loud, never a vacuous LINKED): a dangling exit or a bad/duplicate label is REFUSED by
the engine's gate; an orphan room the start cannot reach is UNREACHABLE (the reachability walk bites
where load_rooms alone would not); an empty spec or a start that names no room raises GameLinkError.

No instancing (J3): the output is canonical seed content -- persistent by construction. Grammar
before worlds is enforced by the import-linter contract (make check), not this twin; here we prove
the Linker genuinely binds the real world loader.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.domains.game_linker import (
    LINKED,
    REFUSED,
    UNREACHABLE,
    GameLinkError,
    GameSpec,
    QuestArc,
    QuestStep,
    RoomSpec,
    link_and_validate,
    link_region,
    validate_region,
)
from kernel.world.seed import load_quest, load_rooms

# A small, valid region: gate -> yard -> hall, all reachable from `gate`.
_GOOD = GameSpec(
    region="ironhold",
    start="gate",
    rooms=(
        RoomSpec(label="gate", name="Iron Gate", desc="A studded gate.", exits={"north": "yard"}),
        RoomSpec(label="yard", desc="A muddy yard.", exits={"north": "hall", "south": "gate"}),
        RoomSpec(label="hall", exits={"south": "yard"}),
    ),
)


# --- acceptance -----------------------------------------------------------------------------------


def test_a_valid_region_links_and_all_rooms_reachable(tmp_path: Path) -> None:
    linked, verdict = link_and_validate(_GOOD, tmp_path)
    assert verdict.verdict == LINKED and verdict.ok is True
    assert linked.rooms_linked == 3 and verdict.rooms == 3
    # The emitted content is real seed content: the ENGINE'S loader accepts it directly.
    rooms = load_rooms(tmp_path / "rooms.yaml")
    assert set(rooms) == {"gate", "yard", "hall"}
    assert rooms["gate"]["exits"] == {"north": "yard"}


def test_emitted_content_is_deterministic(tmp_path: Path) -> None:
    a = link_region(_GOOD, tmp_path / "a")
    b = link_region(_GOOD, tmp_path / "b")
    assert a.checksums == b.checksums  # same spec -> byte-identical content
    assert (tmp_path / "a" / "rooms.yaml").read_text() == (
        tmp_path / "b" / "rooms.yaml"
    ).read_text()


# --- refusal: fail loud, never a vacuous LINKED ---------------------------------------------------


def test_a_dangling_exit_is_refused_loud(tmp_path: Path) -> None:
    spec = GameSpec(
        region="broken",
        start="gate",
        rooms=(RoomSpec(label="gate", exits={"north": "nowhere_room"}),),
    )
    _, verdict = link_and_validate(spec, tmp_path)
    assert verdict.verdict == REFUSED and "nowhere_room" in verdict.error


def test_an_orphan_room_is_flagged_unreachable(tmp_path: Path) -> None:
    # `island` loads fine (no dangling exit) but nothing links to it from the start.
    spec = GameSpec(
        region="split",
        start="gate",
        rooms=(
            RoomSpec(label="gate", exits={"north": "yard"}),
            RoomSpec(label="yard", exits={"south": "gate"}),
            RoomSpec(label="island"),
        ),
    )
    _, verdict = link_and_validate(spec, tmp_path)
    assert verdict.verdict == UNREACHABLE and verdict.unreachable == ("island",)


def test_a_bad_label_is_refused_loud(tmp_path: Path) -> None:
    spec = GameSpec(region="bad", start="Bad Label", rooms=(RoomSpec(label="Bad Label"),))
    _, verdict = link_and_validate(spec, tmp_path)
    assert verdict.verdict == REFUSED  # the engine's snake_case gate rejects it


def test_empty_rooms_is_refused_loud(tmp_path: Path) -> None:
    with pytest.raises(GameLinkError):
        link_region(GameSpec(region="empty", start="x", rooms=()), tmp_path)


def test_start_naming_no_room_is_refused_loud(tmp_path: Path) -> None:
    spec = GameSpec(region="r", start="ghost", rooms=(RoomSpec(label="gate"),))
    with pytest.raises(GameLinkError):
        link_region(spec, tmp_path)


def test_empty_region_name_is_refused_loud(tmp_path: Path) -> None:
    with pytest.raises(GameLinkError):
        link_region(GameSpec(region="  ", start="gate", rooms=(RoomSpec(label="gate"),)), tmp_path)


# --- the verdict mirrors the flag ----------------------------------------------------------------


def test_validate_can_run_standalone_on_a_linked_artifact(tmp_path: Path) -> None:
    linked = link_region(_GOOD, tmp_path)
    assert validate_region(linked).verdict == LINKED


# --- sub-slice 2: a region WITH a quest arc, validated through the real load_quest ----------------

# A rooms-and-quest region: two rooms, and an arc that ends when the player enters `greenhold`.
_QUEST = QuestArc(
    id="first_road",
    start="offered",
    steps=(
        QuestStep(state="offered", event="accept", to="accepted"),
        QuestStep(
            state="accepted", event="enter", to="done", on_enter="greenhold", effect="award_xp"
        ),
    ),
    terminal=("done",),
    labels={"offered": "Accept the road.", "done": "*** The journey has begun. ***"},
    name="The First Road",
    reward_xp=60,
)
_WITH_QUEST = GameSpec(
    region="veridia",
    start="gate",
    rooms=(
        RoomSpec(label="gate", exits={"north": "greenhold"}),
        RoomSpec(label="greenhold", exits={"south": "gate"}),
    ),
    quest=_QUEST,
)


def test_a_region_with_a_valid_quest_links(tmp_path: Path) -> None:
    linked, verdict = link_and_validate(_WITH_QUEST, tmp_path)
    assert verdict.verdict == LINKED and verdict.quest is True
    assert linked.has_quest is True and "quest.yaml" in linked.files
    # The emitted quest is real seed content: the ENGINE'S own load_quest accepts it directly.
    quest = load_quest(tmp_path / "quest.yaml")
    assert quest is not None and quest["id"] == "first_road" and quest["terminal"] == ["done"]


def test_quest_emit_is_deterministic(tmp_path: Path) -> None:
    a = link_region(_WITH_QUEST, tmp_path / "a")
    b = link_region(_WITH_QUEST, tmp_path / "b")
    assert a.checksums == b.checksums  # same spec (rooms + quest) -> byte-identical


def test_no_quest_still_links_rooms_only(tmp_path: Path) -> None:
    linked, verdict = link_and_validate(_GOOD, tmp_path)  # _GOOD has no quest
    assert verdict.verdict == LINKED and verdict.quest is False
    assert linked.has_quest is False and "quest.yaml" not in linked.files
    assert not (tmp_path / "quest.yaml").exists()


def test_a_malformed_quest_is_refused_loud(tmp_path: Path) -> None:
    # An empty-steps quest: load_quest rejects it ("steps must be non-empty") -> REFUSED.
    spec = GameSpec(
        region="r",
        start="gate",
        rooms=(RoomSpec(label="gate"),),
        quest=QuestArc(id="broken", start="offered", steps=()),
    )
    _, verdict = link_and_validate(spec, tmp_path)
    assert verdict.verdict == REFUSED and "quest" in verdict.error


def test_a_quest_on_enter_to_a_missing_room_is_refused(tmp_path: Path) -> None:
    # The step fires on entering `ghost_room`, which is not a room here: broken cross-link.
    spec = GameSpec(
        region="r",
        start="gate",
        rooms=(RoomSpec(label="gate"),),
        quest=QuestArc(
            id="q",
            start="offered",
            steps=(QuestStep(state="offered", event="enter", to="done", on_enter="ghost_room"),),
            terminal=("done",),
        ),
    )
    _, verdict = link_and_validate(spec, tmp_path)
    assert verdict.verdict == REFUSED and "ghost_room" in verdict.error


def test_a_quest_with_an_unreachable_terminal_is_flagged(tmp_path: Path) -> None:
    # `done` is a declared terminal but no transition reaches it from the start: incompletable.
    spec = GameSpec(
        region="r",
        start="gate",
        rooms=(RoomSpec(label="gate"),),
        quest=QuestArc(
            id="q",
            start="offered",
            steps=(QuestStep(state="offered", event="accept", to="accepted"),),
            terminal=("done",),
        ),
    )
    _, verdict = link_and_validate(spec, tmp_path)
    assert verdict.verdict == UNREACHABLE and verdict.unreachable == ("done",)
