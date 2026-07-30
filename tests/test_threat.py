"""Test twin for parts/world/threat.py -- the per-NPC aggro table (the trinity's tank seam).

Acceptance: damage-shaped threat accrues and reads back; top_target picks the highest-threat hero
PRESENT, breaks ties stably, and returns None when no present hero has threat; taunt spikes the
taunter above the current top; drop/clear forget. Refusal: a non-positive amount never moves the
table; a departed hero's stale threat never gets picked (top_target filters by who is present).
"""

from __future__ import annotations

from typing import Any

import pytest

from parts.world import threat
from parts.world.session import Session


@pytest.fixture(autouse=True)
def _fresh() -> Any:
    threat._reset()
    yield
    threat._reset()


def _present(*ids: str) -> dict[str, Session]:
    return {pid: Session(player_id=pid) for pid in ids}


def test_damage_accrues_threat():
    threat.add("gob", "bram", 10)
    threat.add("gob", "bram", 5)
    assert threat.score("gob", "bram") == 15


def test_a_non_positive_amount_never_moves_the_table():
    threat.add("gob", "bram", 0)
    threat.add("gob", "bram", -4)
    assert threat.score("gob", "bram") == 0


def test_top_target_picks_the_highest_threat_present_hero():
    threat.add("gob", "bram", 3)
    threat.add("gob", "cleo", 20)
    present = _present("bram", "cleo")
    assert threat.top_target("gob", present) is present["cleo"]


def test_top_target_ignores_a_hero_who_is_not_present():
    threat.add("gob", "cleo", 99)  # cleo has the most threat...
    present = _present("bram")  # ...but only bram is in the room
    threat.add("gob", "bram", 1)
    assert threat.top_target("gob", present) is present["bram"]


def test_top_target_is_none_when_no_present_hero_has_threat():
    threat.add("gob", "cleo", 5)
    assert threat.top_target("gob", _present("bram")) is None  # bram has none, cleo absent
    assert threat.top_target("unknown", _present("bram")) is None  # no table at all


def test_top_target_breaks_ties_stably():
    threat.add("gob", "aaron", 10)
    threat.add("gob", "zed", 10)  # equal threat
    present = _present("aaron", "zed")
    first = threat.top_target("gob", present)
    assert threat.top_target("gob", present) is first  # same pick every beat, no jitter


def test_taunt_sets_the_taunter_above_the_current_top():
    threat.add("gob", "dps", 50)
    new = threat.taunt("gob", "tank", ["dps", "tank"])
    assert new == 51
    present = _present("dps", "tank")
    assert threat.top_target("gob", present) is present["tank"]  # the tank now holds the foe


def test_drop_forgets_one_hero_and_prunes_an_empty_table():
    threat.add("gob", "bram", 4)
    threat.drop("gob", "bram")
    assert threat.score("gob", "bram") == 0
    assert threat.top_target("gob", _present("bram")) is None  # table pruned


def test_clear_wipes_a_felled_foes_grudges():
    threat.add("gob", "bram", 7)
    threat.clear("gob")
    assert threat.score("gob", "bram") == 0


def test_drop_keeps_the_other_heroes_threat():
    threat.add("gob", "bram", 4)
    threat.add("gob", "cleo", 9)
    threat.drop("gob", "bram")
    assert threat.score("gob", "cleo") == 9  # cleo's grudge survives
    assert threat.score("gob", "bram") == 0


def test_drop_on_an_unknown_foe_is_harmless():
    threat.drop("never-fought", "bram")  # no table -> no error
    assert threat.score("never-fought", "bram") == 0
