"""Test twin for kernel/domains/game_session.py -- operate a linked region's quest, then RESUME it
after a restart, on the real quest engine.

Acceptance: a travel-driven quest (each step fires on entering a room) is driven to its terminal by
walking the region, the player's progress + location are backed up, a restart is simulated (unload,
reload from the durable file, restore), and the player resumes at the same terminal -> RESUMED.

Refusal (fail loud, never a false RESUMED): a region that does not link, or ships no quest, is
REFUSED; a quest that cannot be completed by travel alone (a step needs a manual event) is
INOPERABLE. And the proof never LEAKS global state -- the quest is unregistered afterward whatever
the verdict.
"""

from __future__ import annotations

from pathlib import Path

from kernel.domains.game_linker import GameSpec, QuestArc, QuestStep, RoomSpec
from kernel.domains.game_session import (
    INOPERABLE,
    REFUSED,
    RESUMED,
    operate_and_recover,
)

# A travel-driven journey: enter waypoint_one, then waypoint_two, and the arc completes.
_JOURNEY = GameSpec(
    region="the_road",
    start="gate",
    rooms=(
        RoomSpec(label="gate", exits={"north": "waypoint_one"}),
        RoomSpec(label="waypoint_one", exits={"north": "waypoint_two", "south": "gate"}),
        RoomSpec(label="waypoint_two", exits={"south": "waypoint_one"}),
    ),
    quest=QuestArc(
        id="probe_journey",
        start="setting_out",
        steps=(
            QuestStep(state="setting_out", event="reach1", to="midway", on_enter="waypoint_one"),
            QuestStep(state="midway", event="reach2", to="arrived", on_enter="waypoint_two"),
        ),
        terminal=("arrived",),
    ),
)


def _quest_registered(quest_id: str) -> bool:
    from kernel.world.quest import _QUESTS  # noqa: PLC0415

    return quest_id in _QUESTS


# --- acceptance: operate to terminal, then resume after restart -----------------------------------


def test_a_travel_driven_quest_operates_and_resumes(tmp_path: Path) -> None:
    report = operate_and_recover(_JOURNEY, tmp_path)
    assert report.verdict == RESUMED and report.ok is True
    assert report.quest_id == "probe_journey" and report.terminal == "arrived"


def test_the_quest_is_unregistered_after_no_global_leak(tmp_path: Path) -> None:
    assert not _quest_registered("probe_journey")  # clean slate before
    operate_and_recover(_JOURNEY, tmp_path)
    assert not _quest_registered("probe_journey")  # torn down after -> no leaked global state


# --- refusal: fail loud, never a false RESUMED ---------------------------------------------------


def test_a_region_without_a_quest_is_refused(tmp_path: Path) -> None:
    rooms_only = GameSpec(
        region="empty_road",
        start="gate",
        rooms=(RoomSpec(label="gate", exits={"north": "yard"}), RoomSpec(label="yard")),
    )
    report = operate_and_recover(rooms_only, tmp_path)
    assert report.verdict == REFUSED and "no quest" in report.detail


def test_a_region_that_does_not_link_is_refused(tmp_path: Path) -> None:
    broken = GameSpec(
        region="broken", start="gate", rooms=(RoomSpec(label="gate", exits={"north": "nowhere"}),)
    )
    report = operate_and_recover(broken, tmp_path)
    assert report.verdict == REFUSED and "did not link" in report.detail


def test_a_quest_needing_a_manual_step_is_inoperable(tmp_path: Path) -> None:
    # The first step advances on a manual `accept` event, not on entering a room: travel alone
    # cannot complete it. INOPERABLE, not a hang -- and still no global leak (unregistered).
    manual = GameSpec(
        region="gated_road",
        start="gate",
        rooms=(
            RoomSpec(label="gate", exits={"north": "shrine"}),
            RoomSpec(label="shrine", exits={"south": "gate"}),
        ),
        quest=QuestArc(
            id="probe_manual",
            start="offered",
            steps=(
                QuestStep(state="offered", event="accept", to="accepted"),  # no on_enter: manual
                QuestStep(state="accepted", event="pray", to="done", on_enter="shrine"),
            ),
            terminal=("done",),
        ),
    )
    report = operate_and_recover(manual, tmp_path)
    assert report.verdict == INOPERABLE
    assert not _quest_registered("probe_manual")  # torn down even on the refusal path


# --- coverage: the honest failure paths (never a false RESUMED) ----------------------------------


def test_state_of_is_empty_for_unknown_or_malformed(monkeypatch) -> None:
    from kernel.domains import game_session  # noqa: PLC0415

    assert game_session._state_of("nobody_here", "q") == ""  # no runs -> empty save
    monkeypatch.setattr("kernel.world.quest.save_state", lambda pid: "not-json")
    assert game_session._state_of("whoever", "q") == ""  # malformed save -> empty, never a crash


def test_a_failed_restore_is_not_a_false_resume(tmp_path, monkeypatch) -> None:
    # If the restart can't restore the player's progress, report the miss, not RESUMED.
    monkeypatch.setattr("kernel.world.quest.restore_state", lambda pid, raw: None)  # restore no-ops
    report = operate_and_recover(_JOURNEY, tmp_path)
    assert report.verdict == INOPERABLE and "did not resume" in report.detail
    assert not _quest_registered("probe_journey")  # still torn down
