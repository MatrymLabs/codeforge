"""Test twin for parts/shelf/reward_curve.py -- the challenge-scaled reward engine.

The curve IS the contract (a locked design), so the boundaries are pinned exactly: the full band,
the capped bonus for fighting up, the linear taper to zero for grays, the three tiers, and the 10:1
job schema for JP. Refusal: an unknown tier fails loud rather than silently paying wrong.
"""

from __future__ import annotations

import pytest

from parts.shelf.reward_curve import (
    BONUS_CAP,
    RewardError,
    clamp_level,
    gap_multiplier,
    jp_for_kill,
    xp_for_kill,
)


@pytest.mark.parametrize(
    "gap, expected",
    [
        (0, 1.0),  # dead even
        (5, 1.0),  # top edge of the full band
        (-5, 1.0),  # bottom edge of the full band
        (6, 1.05),  # one level above the band: +5%
        (10, 1.25),  # five above the band: +25%
        (100, BONUS_CAP),  # far above: capped at +50%
        (-6, 0.9),  # one past the band down: linear taper
        (-10, 0.5),  # halfway down the taper
        (-15, 0.0),  # a gray: zero reward
        (-40, 0.0),  # far below: still zero, never negative
    ],
)
def test_gap_multiplier_curve(gap: float, expected: float) -> None:
    assert gap_multiplier(gap) == pytest.approx(expected)


def test_clamp_level_bounds_the_enemy_range() -> None:
    assert clamp_level(0) == 1 and clamp_level(-99) == 1
    assert clamp_level(301) == 300 and clamp_level(9999) == 300
    assert clamp_level(150) == 150


def test_xp_scales_with_enemy_level_tier_and_gap() -> None:
    assert xp_for_kill(10, 10, "normal") == 100  # base = enemy_level * 10, even fight
    assert xp_for_kill(10, 10, "elite") == 300  # elite x3
    assert xp_for_kill(10, 10, "boss") == 1000  # boss x10
    assert xp_for_kill(10, 20, "normal") == 250  # fighting up +25% (base 200 * 1.25)
    assert xp_for_kill(30, 10, "normal") == 0  # a gray: nothing


def test_jp_uses_the_ten_to_one_job_schema() -> None:
    assert jp_for_kill(1, 10, "normal") == 20  # job 1 "expects" enemy 10: full JP
    assert jp_for_kill(1, 20, "normal") == 40  # enemy 20 is +1 job-level: still in band
    assert jp_for_kill(30, 10, "normal") == 0  # a level-30 job farming enemy 10: nothing
    assert jp_for_kill(1, 200, "boss") > jp_for_kill(1, 200, "normal")  # tier multiplies


def test_an_unknown_tier_fails_loud() -> None:
    with pytest.raises(RewardError, match="unknown tier"):
        xp_for_kill(10, 10, "legendary")
    with pytest.raises(RewardError, match="unknown tier"):
        jp_for_kill(1, 10, "mythic")


def test_the_clamp_applies_inside_the_reward() -> None:
    # an over-cap enemy level is clamped before scaling (never rewards beyond level 300)
    assert xp_for_kill(300, 9999, "normal") == xp_for_kill(300, 300, "normal")
