"""Test twin for parts/quest.py -- the game adapter: a quest driven by the Workflow Engine."""

import pytest

from parts.jobs import bind_calling
from parts.quest import quest_view, reset_quests
from parts.session import SESSIONS, Session


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


def test_a_seed_quest_spec_builds_a_named_workflow():
    """A seed can ship its own arc as data; _from_seed turns that spec into the live workflow,
    carrying the seed's name and XP reward (proven here since the default test seed uses the
    built-in fallback)."""
    from parts.quest import _from_seed

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
