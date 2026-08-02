"""Test twin for kernel/world/mortality.py -- a felled foe dies and respawns, the dummy reassembles.

Acceptance: a mortal foe felled at beat B is DEAD (absent) until B + its tier delay, then revives at
full HP in place. Refusal: a foe marked `reassembles` NEVER dies -- it is restored to full at once,
no matter the beat. Hostile cases: the exact respawn beat (boundary), an unknown tier, and that a
foe never felled is trivially alive.
"""

from __future__ import annotations

from typing import cast

from kernel.world import mortality
from kernel.world.seed import Npc


def _foe(tier: str = "normal", hp: int = 100, **extra: object) -> Npc:
    npc = cast(Npc, {"name": "a grey wolf", "hp": hp, "hp_now": hp, "keywords": ["wolf"]})
    npc.update(extra)  # type: ignore[typeddict-item]
    if tier:
        npc["tier"] = tier
    return npc


def test_a_felled_mortal_foe_dies_and_is_absent_until_its_respawn_beat():
    foe = _foe("normal")
    died = mortality.fell(foe, beat=100)
    assert died is True
    assert foe["hp_now"] == 0
    # dead for the whole normal delay window...
    assert mortality.is_dead(foe, beat=100) is True
    assert mortality.is_dead(foe, beat=100 + mortality.RESPAWN_BEATS["normal"] - 1) is True


def test_a_dead_foe_revives_at_full_on_its_respawn_beat():
    foe = _foe("normal", hp=80)
    mortality.fell(foe, beat=100)
    due = 100 + mortality.RESPAWN_BEATS["normal"]
    # the exact respawn beat (boundary) revives it, in place, at full health...
    assert mortality.is_dead(foe, beat=due) is False
    assert foe["hp_now"] == 80
    assert "dead_until" not in foe


def test_a_reassembling_foe_never_dies():
    dummy = _foe("normal", hp=20, reassembles=True)
    dummy["hp_now"] = 0  # just took the finishing blow
    died = mortality.fell(dummy, beat=100)
    assert died is False  # it did NOT die
    assert dummy["hp_now"] == 20  # stood right back up at full
    assert "dead_until" not in dummy  # never marked dead
    assert mortality.is_dead(dummy, beat=100) is False


def test_boss_stays_cleared_far_longer_than_trash():
    assert mortality.RESPAWN_BEATS["boss"] > mortality.RESPAWN_BEATS["normal"]
    assert mortality.RESPAWN_BEATS["raid"] > mortality.RESPAWN_BEATS["boss"]


def test_unknown_tier_gets_the_default_delay():
    foe = _foe("")  # no tier at all
    foe.pop("tier", None)
    assert mortality.respawn_delay(foe) == mortality._DEFAULT_RESPAWN


def test_a_foe_never_felled_is_alive():
    assert mortality.is_dead(_foe("normal"), beat=999) is False


def test_defeat_sheds_transient_statuses():
    foe = _foe("normal", burn={"damage": 3, "ticks": 2}, dazed=2)
    mortality.fell(foe, beat=100)
    assert "burn" not in foe
    assert "dazed" not in foe
