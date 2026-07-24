"""Test twin for parts/world/quest.py -- the game adapter: a quest driven by the Workflow Engine."""

import copy

import pytest

from parts.world import items
from parts.world.jobs import bind_calling
from parts.world.quest import quest_view, reset_quests
from parts.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_quests():
    items_snap = copy.deepcopy(items.ITEMS)  # `take key` moves items; restore so nothing leaks
    reset_quests()
    SESSIONS.clear()
    yield
    reset_quests()
    items.ITEMS.clear()
    items.ITEMS.update(items_snap)
    SESSIONS.clear()


def _player(job: str = "vanguard") -> Session:
    s = Session(player_id="matrym", location="courtyard")
    SESSIONS["matrym"] = s
    bind_calling(s, job)
    return s


def test_the_quest_list_shows_each_arc_and_its_moves():
    out = quest_view(_player(), "")
    assert "Your quests:" in out
    assert "waits at the board" in out
    assert "accept" in out  # the available move is advertised in the listing


def test_a_move_out_of_order_is_refused():
    out = quest_view(_player(), "finish")  # a known event, but not legal before accepting
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
        from parts.world.quest import _QUESTS

        quest = next(iter(_QUESTS.values()))
        _apply_effect(quest, "open_door:oak_door", _player())
        assert doors.DOORS["oak_door"]["locked"] is False
    finally:
        doors.DOORS.clear()
        doors.DOORS.update(snap)


def test_a_quest_derives_its_triggers_from_the_spec_steps():
    """Each step's on_take/on_enter/on_defeat becomes a (kind, label) -> event trigger on the quest;
    a step with no trigger contributes nothing."""
    from parts.world.quest import _from_seed, _Quest

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
    wf, name, xp = _from_seed(spec)
    quest = _Quest(wf, name, xp, spec)
    assert quest.triggers == {
        ("take", "item1"): "e1",
        ("enter", "room1"): "e2",
        ("defeat", "boss1"): "e3",
    }


def test_on_event_advances_the_arc_when_a_world_action_triggers_a_step(monkeypatch):
    """A world action (defeat/take/enter) can fire a quest step. Routed here onto the built-in
    quest's first event so the behavior is pinned without depending on the aethryn seed."""
    import parts.world.quest as quest_mod

    qid = next(iter(quest_mod._QUESTS))
    monkeypatch.setitem(quest_mod._QUESTS[qid].triggers, ("defeat", "warren_boss"), "accept")
    monkeypatch.setitem(quest_mod._EVENT_ROUTES, ("defeat", "warren_boss"), qid)
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

    qid = next(iter(quest_mod._QUESTS))
    monkeypatch.setitem(quest_mod._QUESTS[qid].triggers, ("enter", "deep_vault"), "finish")
    monkeypatch.setitem(quest_mod._EVENT_ROUTES, ("enter", "deep_vault"), qid)
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
    from parts.world.quest import _QUESTS, _apply_effect
    from parts.world.session import Session

    quest = next(iter(_QUESTS.values()))
    rookie = Session(player_id="rookie")  # no calling -> stats is None
    assert _apply_effect(quest, "award_xp", rookie) == ""  # nothing to grant
    assert _apply_effect(quest, "mystery_effect", _player()) == ""  # unknown effect: inert


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


def test_aethryn_relighting_arc_self_completes_from_natural_play():
    # the aethryn arc must play itself cradle-to-grave: after the opt-in `accept`, every beat fires
    # from a real world action (a natural trigger), and it ends on felling the boss with a reward.
    from pathlib import Path

    from parts.world.seed import load_quest

    seeds = Path(__file__).resolve().parent.parent / "seeds"
    spec = load_quest(seeds / "aethryn" / "quest.yaml")
    assert spec is not None and spec["name"] == "The Relighting"
    for step in spec["steps"]:
        if step["event"] == "accept":
            continue
        natural = step.get("on_take") or step.get("on_enter") or step.get("on_defeat")
        assert natural, f"step '{step['event']}' has no natural trigger -- the arc would soft-lock"
    face = next(s for s in spec["steps"] if s["to"] == "done")
    assert face.get("on_defeat") == "cinder_wight" and face.get("effect") == "award_xp"
    assert "done" in spec["terminal"]


def test_save_state_reports_a_quest_state_map_and_empty_before_any_run():
    import json

    from parts.world.quest import _QUESTS, save_state

    reset_quests()
    assert save_state("nobody") == ""  # no run yet -> empty (a fresh character stores nothing)
    primary = next(iter(_QUESTS))
    s = Session(player_id="hero", location="courtyard")
    quest_view(s, "accept")
    assert json.loads(save_state("hero")) == {primary: "accepted"}  # a {quest_id: state} map


def test_restore_state_seeds_the_runs_so_stories_survive_a_restart():
    import json

    from parts.world.quest import _QUESTS, restore_state, save_state

    reset_quests()
    primary = next(iter(_QUESTS))
    restore_state("hero", json.dumps({primary: "accepted"}))  # as if reloaded after a restart
    assert json.loads(save_state("hero")) == {primary: "accepted"}


def test_restore_state_honors_a_legacy_bare_state_string():
    """A single-quest-era value (a bare state, not JSON) is matched to the primary quest."""
    import json

    from parts.world.quest import _QUESTS, restore_state, save_state

    reset_quests()
    primary = next(iter(_QUESTS))
    restore_state("hero", "accepted")  # the pre-multi-quest format
    assert json.loads(save_state("hero")) == {primary: "accepted"}


def test_restore_state_ignores_an_unknown_quest_or_state():
    from parts.world.quest import restore_state, save_state

    reset_quests()
    restore_state("hero", '{"ghost_quest": "somewhere"}')  # unknown quest id
    restore_state("hero", "not_a_real_state")  # unknown bare state
    assert save_state("hero") == ""  # nothing seeded -- a clean fresh run
