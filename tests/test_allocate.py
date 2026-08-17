"""Test twin for kernel/world/allocate.py -- spend the attribute points a level-up grants.

Acceptance: points are earned by level and derived (earned - spent), a spend raises the attribute
(and HP/MP for stamina/magic), and the allocation persists through the StatBlock and a save/restore.
Refusal: no calling, a bad attribute, over-spending, and the per-stat cap all fail loud.
"""

from __future__ import annotations

import pytest

import forge
from kernel.world import allocate
from kernel.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def _hero(level: int = 5) -> Session:
    s = Session(player_id="hero")
    forge.handle_command(s, "job vanguard")
    s.level = level  # 5 -> 4 levels gained -> 20 points, cap 12/attribute
    return s


def test_points_are_earned_by_level_and_derived():
    s = _hero(level=5)
    assert allocate.earned(5) == 20 and allocate.earned(1) == 0
    assert allocate.unspent(s) == 20  # nothing spent yet
    assert allocate.per_stat_cap(5) == 12


def test_spending_raises_the_attribute_and_shrinks_the_pool():
    s = _hero()
    before = s.stats.get("strength").base
    out = forge.handle_command(s, "allocate strength 3")
    assert "+3" in out
    assert s.stats.get("strength").base == before + 3  # folded into the live StatBlock
    assert allocate.unspent(s) == 17


def test_stamina_and_magic_grow_the_hp_mp_pool_at_once():
    s = _hero()
    hp, mp = s.resources["hp"].maximum, s.resources["mp"].maximum
    forge.handle_command(s, "allocate stamina 2")
    forge.handle_command(s, "allocate magic 1")
    assert s.resources["hp"].maximum == hp + 2 and s.resources["mp"].maximum == mp + 1


def test_the_bare_verb_shows_the_pool():
    out = forge.handle_command(_hero(), "allocate")
    assert "unspent" in out and "strength" in out and "allocate <stat>" in out


def test_over_spending_and_the_per_stat_cap_are_refused():
    s = _hero()
    assert "only" in forge.handle_command(s, "allocate luck 99")  # more than the 20 in the pool
    # fill strength to its level cap (12), then one more is refused
    forge.handle_command(s, "allocate strength 12")
    assert "At most 12 into strength" in forge.handle_command(s, "allocate strength 1")


def test_a_bad_attribute_or_no_calling_fails_loud():
    s = _hero()
    assert "not an attribute" in forge.handle_command(s, "allocate charisma 1")
    jobless = Session(player_id="drifter")
    assert "no calling" in allocate.allocate(jobless, "strength")


def test_the_allocation_persists_through_serialize_and_restore():
    s = _hero()
    forge.handle_command(s, "allocate strength 3")
    forge.handle_command(s, "allocate stamina 2")
    raw = allocate.serialize(s)
    fresh = Session(player_id="clone")
    allocate.restore(fresh, raw)
    assert fresh.allocated == {"stamina": 2, "strength": 3}
    # an unknown attribute (a cross-seed save) is dropped, not crashed
    allocate.restore(fresh, '{"charisma": 5, "strength": 1}')
    assert fresh.allocated == {"strength": 1}


def test_allocation_survives_a_character_restore_folded_into_stats():
    from kernel.world.characters import restore_character

    casefile = {
        "job": "vanguard",
        "level": 5,
        "xp": 0,
        "location": "courtyard",
        "allocated": '{"strength": 6}',
    }
    s = Session(player_id="saved")
    restore_character(s, casefile)
    assert s.allocated == {"strength": 6}
    # the +6 is folded into the rebuilt StatBlock (first-forge vanguard base strength 14 + 6)
    assert s.stats is not None and s.stats.get("strength").base == 20
