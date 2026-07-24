"""Test twin for parts.world.consumables: quaff a carried consumable for a one-shot restore.

Acceptance (a healing draught restores HP and is spent) AND refusal (not carried, not drinkable),
plus engine-tick reachability. The fixture snapshots ITEMS so cloned draughts never leak.
"""

import copy

import pytest

import forge  # noqa: F401 -- boot the world before the fixture clones items
from parts.world import items
from parts.world.consumables import quaff
from parts.world.jobs import bind_calling
from parts.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_items():
    snap = copy.deepcopy(items.ITEMS)
    SESSIONS.clear()
    yield
    items.ITEMS.clear()
    items.ITEMS.update(snap)
    SESSIONS.clear()


def _drinker() -> Session:
    s = Session(player_id="drinker", location="courtyard")  # first-forge: healing_draught here
    SESSIONS["drinker"] = s
    bind_calling(s, "vanguard")
    return s


def test_quaffing_a_draught_restores_hp_and_spends_it():
    s = _drinker()
    s.resources["hp"] = s.resources["hp"].damage(15)
    before = s.resources["hp"].current
    items.clone("healing_draught", "player")
    out = quaff(s, "draught")
    assert "You quaff" in out and "HP" in out
    assert s.resources["hp"].current > before  # healed
    assert not items.items_in("player")  # the draught is spent


def test_quaffing_restores_at_most_to_full():
    s = _drinker()  # already at full HP
    full = s.resources["hp"].current
    items.clone("healing_draught", "player")
    quaff(s, "draught")
    assert s.resources["hp"].current == full  # clamped, never over the maximum


def test_quaffing_something_not_carried_is_refused():
    assert "aren't carrying" in quaff(_drinker(), "draught")


def test_quaffing_a_non_drinkable_is_refused():
    s = _drinker()
    items.clone("forge_wrench", "player")  # a weapon, not a consumable
    assert "not something you can drink" in quaff(s, "wrench")


def test_quaff_is_reachable_through_the_engine_tick():
    s = _drinker()
    s.resources["hp"] = s.resources["hp"].damage(10)
    items.clone("healing_draught", "player")
    assert "You quaff" in forge.handle_command(s, "quaff draught")
