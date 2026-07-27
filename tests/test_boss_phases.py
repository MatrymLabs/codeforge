"""Test twin for parts/world/boss_phases.py -- a wounded boss enrages and hits harder.

Acceptance: a boss-tier foe at or below the enrage threshold scales its blow up and announces once;
a non-boss, or a boss above the line, is untouched (normal combat stays byte-identical). The flag
self-heals when the boss recovers above the line, so a rematch re-announces.
"""

from __future__ import annotations

from parts.world.boss_phases import (
    ENRAGE_AT,
    ENRAGE_MULT,
    boss_phase,
    is_boss,
    is_enraged,
)
from parts.world.seed import Npc


def _boss(hp: int, hp_now: int) -> Npc:
    return Npc(
        name="the Warden of The Black Hollow",
        keywords=["warden"],
        location="depths",
        dialogue=[],
        next_line=0,
        hp=hp,
        hp_now=hp_now,
        xp=0,
        atk=40,
        tier="boss",
    )


def test_a_healthy_boss_strikes_exactly_as_before():
    boss = _boss(hp=100, hp_now=80)  # well above the 30% line
    assert boss_phase(boss, 40) == (40, ""), "no scaling, no announcement above the threshold"
    assert not is_enraged(boss)


def test_a_wounded_boss_enrages_and_announces_once():
    boss = _boss(hp=100, hp_now=25)  # below the line
    blow, line = boss_phase(boss, 40)
    assert blow == int(40 * ENRAGE_MULT) and blow > 40, "the enraged blow lands harder"
    assert "enrages" in line, "the room hears the enrage the first time"
    assert is_enraged(boss)
    # a second blow while still enraged keeps the scaling but does NOT re-announce
    blow2, line2 = boss_phase(boss, 40)
    assert blow2 == blow and line2 == ""


def test_the_flag_self_heals_when_the_boss_recovers():
    boss = _boss(hp=100, hp_now=20)
    boss_phase(boss, 40)  # enraged
    assert is_enraged(boss)
    boss["hp_now"] = 100  # a rematch after recovery
    blow, line = boss_phase(boss, 40)
    assert (blow, line) == (40, "") and not is_enraged(boss), "healthy again: calm and re-armed"
    boss["hp_now"] = 10  # wounded once more -> announces again
    _, line2 = boss_phase(boss, 40)
    assert "enrages" in line2


def test_a_non_boss_never_enrages():
    trash = _boss(hp=100, hp_now=1)  # all but dead, but only an elite
    trash["tier"] = "elite"
    assert boss_phase(trash, 40) == (40, "")
    assert not is_boss(trash)
    dummy = _boss(hp=100, hp_now=1)
    del dummy["tier"]
    assert boss_phase(dummy, 40) == (40, ""), "a foe with no tier is not a boss"


def test_the_threshold_is_the_boundary():
    boss = _boss(hp=100, hp_now=int(100 * ENRAGE_AT))  # exactly at the line
    _, line = boss_phase(boss, 40)
    assert "enrages" in line, "at the threshold counts as enraged"
