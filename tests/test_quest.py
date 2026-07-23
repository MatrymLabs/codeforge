"""Test twin for parts/world/quest.py -- the game adapter: a quest driven by the Workflow Engine."""

import pytest

from parts.world.jobs import bind_calling
from parts.world.quest import quest_view, reset_quests
from parts.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_quests():
    reset_quests()
    SESSIONS.clear()
    yield
    reset_quests()
    SESSIONS.clear()


def _player(job: str = "vanguard") -> Session:
    s = Session(player_id="matrym", location="courtyard")
    SESSIONS["matrym"] = s
    bind_calling(s, job)
    return s


def test_the_quest_starts_offered_and_advertises_its_move():
    out = quest_view(_player(), "")
    assert "waits at the board" in out
    assert "You can: accept" in out


def test_a_move_out_of_order_is_refused():
    out = quest_view(_player(), "finish")  # cannot finish before accepting
    assert "can't do that now" in out


def test_walking_the_quest_to_done_awards_xp():
    s = _player()
    quest_view(s, "accept")
    quest_view(s, "begin")
    out = quest_view(s, "finish")
    assert "fulfilled" in out
    assert "You gain 50 XP." in out  # the effect fired through the game adapter


def test_the_quest_verb_flows_through_the_engine_tick():
    from forge import handle_command

    s = _player()
    assert "Coilward Contract" in handle_command(s, "quest")
    assert "taken the contract" in handle_command(s, "quest accept")


def test_viewing_a_finished_quest_shows_its_done_label():
    """Status view after the arc is complete shows the terminal label, no further actions."""
    s = _player()
    quest_view(s, "accept")
    quest_view(s, "begin")
    quest_view(s, "finish")
    out = quest_view(s, "")  # status view of a completed quest
    assert "fulfilled" in out and "You can:" not in out


def test_open_door_effect_reforges_a_barrier():
    """A quest step's open_door effect opens a world barrier (the workflow names it, the game
    applies it). Proven against the default seed's oak_door standing in for aethryn's bridge."""
    import copy

    from parts.world import doors
    from parts.world.quest import _apply_effect

    snap = copy.deepcopy(doors.DOORS)
    try:
        doors.DOORS["oak_door"]["locked"] = True
        _apply_effect("open_door:oak_door", _player())
        assert doors.DOORS["oak_door"]["locked"] is False
    finally:
        doors.DOORS.clear()
        doors.DOORS.update(snap)


def test_build_triggers_maps_every_world_event_kind():
    """Each step's on_take/on_enter/on_defeat becomes a (kind, label) -> event entry; a step with
    no trigger contributes nothing, and a seed with no quest yields an empty map."""
    from parts.world.quest import _build_triggers

    spec = {
        "id": "x",
        "name": "X",
        "start": "a",
        "reward_xp": 0,
        "steps": [
            {"state": "a", "event": "e1", "to": "b", "on_take": "item1"},
            {"state": "b", "event": "e2", "to": "c", "on_enter": "room1"},
            {"state": "c", "event": "e3", "to": "d", "on_defeat": "boss1"},
            {"state": "d", "event": "e4", "to": "e"},  # no trigger
        ],
        "terminal": ["e"],
        "labels": {},
    }
    assert _build_triggers(spec) == {
        ("take", "item1"): "e1",
        ("enter", "room1"): "e2",
        ("defeat", "boss1"): "e3",
    }
    assert _build_triggers(None) == {}  # a seed with no quest has no triggers


def test_on_event_advances_the_arc_when_a_world_action_triggers_a_step(monkeypatch):
    """A world action (defeat/take/enter) can fire a quest step. Wired here to the built-in quest's
    first event so the behavior is pinned without depending on the aethryn seed being loaded."""
    import parts.world.quest as quest_mod

    monkeypatch.setattr(quest_mod, "_TRIGGERS", {("defeat", "warren_boss"): "accept"})
    s = _player()
    line = quest_mod.on_event(s, "defeat", "warren_boss")
    assert line is not None and "taken the contract" in line  # the arc advanced


def test_on_event_is_none_for_an_untriggered_action():
    from parts.world.quest import on_event

    assert on_event(_player(), "defeat", "some_random_rat") is None  # triggers no step
    assert on_event(_player(), "take", "a_pebble") is None


def test_on_event_is_none_when_the_step_is_not_reachable_yet(monkeypatch):
    """Firing a trigger before the arc reaches that beat completes nothing (the move is refused)."""
    import parts.world.quest as quest_mod

    monkeypatch.setattr(quest_mod, "_TRIGGERS", {("enter", "deep_vault"): "finish"})
    assert quest_mod.on_event(_player(), "enter", "deep_vault") is None  # can't finish yet


def test_taking_an_item_surfaces_a_triggered_quest_line(monkeypatch):
    """The take tick rides the quest hook: picking up a triggering item advances the arc."""
    import parts.world.quest as quest_mod
    from forge import handle_command

    monkeypatch.setattr(
        quest_mod,
        "on_event",
        lambda s, kind, target: "[Quest] a pickup beat" if kind == "take" else None,
    )
    s = Session(player_id="m", location="library")
    SESSIONS["m"] = s
    out = handle_command(s, "take key")  # the copper key lives in the library
    assert "You take" in out and "[Quest] a pickup beat" in out


def test_entering_a_room_surfaces_a_triggered_quest_line(monkeypatch):
    """The movement tick rides the quest hook: entering a triggering room advances the arc."""
    import parts.world.quest as quest_mod
    from forge import handle_command

    monkeypatch.setattr(
        quest_mod,
        "on_event",
        lambda s, kind, target: "[Quest] an entry beat" if kind == "enter" else None,
    )
    s = Session(player_id="m", location="forge")
    SESSIONS["m"] = s
    out = handle_command(s, "north")  # forge -> courtyard, an open exit
    assert "Courtyard" in out and "[Quest] an entry beat" in out


def test_apply_effect_is_inert_without_a_calling_or_a_known_effect():
    """award_xp needs a calling (stats) to grant; an unrecognized effect does nothing, quietly."""
    from parts.world.quest import _apply_effect
    from parts.world.session import Session

    rookie = Session(player_id="rookie")  # no calling -> stats is None
    assert _apply_effect("award_xp", rookie) == ""  # nothing to grant
    assert _apply_effect("mystery_effect", _player()) == ""  # unknown effect: inert


def test_a_seed_quest_spec_builds_a_named_workflow():
    """A seed can ship its own arc as data; _from_seed turns that spec into the live workflow,
    carrying the seed's name and XP reward (proven here since the default test seed uses the
    built-in fallback)."""
    from parts.world.quest import _from_seed

    spec = {
        "id": "test_arc",
        "name": "Test Arc",
        "start": "a",
        "reward_xp": 10,
        "steps": [{"state": "a", "event": "go", "to": "b", "effect": "award_xp"}],
        "terminal": ["b"],
        "labels": {"a": "at the start", "b": "at the end"},
    }
    workflow, name, reward = _from_seed(spec)
    assert name == "Test Arc" and reward == 10
    assert workflow.workflow_id == "test_arc" and "b" in workflow.terminal
