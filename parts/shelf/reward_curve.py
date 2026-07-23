"""CARD: reward_curve -- challenge-scaled kill rewards: the gap-band curve + tiers (harvested).

Harvested from Haven's locked reward design (July 2026): the engine that makes a 1-300 climb work.
A reward scales with the GAP between a foe's level and the earner's -- full value within a band, a
capped bonus for fighting UP, a linear taper to ZERO for foes far below -- so grinding trivial
mobs pays nothing and fighting harder foes pays more. Three tiers multiply the base (normal x1,
elite x3, boss x10). JP measures the gap on the 10:1 job schema (job level N expects enemy N*10), so
mastering a job demands appropriately hard fights, not farming easy mobs.

Pure functions over ints; engine-agnostic (stdlib only); the game supplies the levels and tiers. All
pacing knobs are module constants -- rebalance here, nowhere else.
"""

from __future__ import annotations

# The three enemy tiers and what they multiply the base reward by.
TIER_MULTIPLIERS: dict[str, float] = {"normal": 1.0, "elite": 3.0, "boss": 10.0}

LEVEL_MIN, LEVEL_MAX = 1, 300  # the legal enemy level range
XP_PER_LEVEL = 10  # base XP per enemy level, before tier + gap scaling
JP_PER_LEVEL = 2  # base JP per enemy level

# The level-gap curve.
FULL_BAND = 5  # +/- this many levels around the reference -> full value
ZERO_AT = 15  # this many levels BELOW the reference -> zero reward (no gray farming)
BONUS_PER_LEVEL = 0.05  # extra reward per level fought ABOVE the band
BONUS_CAP = 1.5  # the most fighting up can multiply the reward (+50%)

ENEMY_LEVELS_PER_JOB_LEVEL = 10  # a job at level N "expects" enemy level N*10


class RewardError(ValueError):
    """A reward was requested with an unknown tier. Fail loud, never pay the wrong amount."""


def _tier_multiplier(tier: str) -> float:
    if tier not in TIER_MULTIPLIERS:
        raise RewardError(f"unknown tier {tier!r}; known: {tuple(TIER_MULTIPLIERS)}")
    return TIER_MULTIPLIERS[tier]


def clamp_level(level: int) -> int:
    """Clamp a level into the legal enemy range [LEVEL_MIN, LEVEL_MAX]."""
    return max(LEVEL_MIN, min(LEVEL_MAX, int(level)))


def gap_multiplier(gap: float) -> float:
    """The gap-scaling factor (0.0 - 1.5). `gap` = enemy_level - reference_level (positive = up).

    Full (1.0) within +/- FULL_BAND; above that a capped bonus (+BONUS_PER_LEVEL/level, up to
    BONUS_CAP); below the band a linear taper reaching 0.0 at ZERO_AT levels down."""
    if gap > FULL_BAND:
        return min(1.0 + BONUS_PER_LEVEL * (gap - FULL_BAND), BONUS_CAP)
    if gap >= -FULL_BAND:
        return 1.0
    past_band = -gap - FULL_BAND
    return max(0.0, 1.0 - past_band / (ZERO_AT - FULL_BAND))


def xp_for_kill(player_level: int, enemy_level: int, tier: str = "normal") -> int:
    """XP for one kill: enemy_level * XP_PER_LEVEL, scaled by tier and the PLvl gap (0 if gray)."""
    enemy_level = clamp_level(enemy_level)
    base = enemy_level * XP_PER_LEVEL
    return int(round(base * _tier_multiplier(tier) * gap_multiplier(enemy_level - player_level)))


def jp_for_kill(job_level: int, enemy_level: int, tier: str = "normal") -> int:
    """JP for one job: same curve, gap measured on the 10:1 job schema (job N -> enemy N*10)."""
    enemy_level = clamp_level(enemy_level)
    base = enemy_level * JP_PER_LEVEL
    scaled_gap = (enemy_level - job_level * ENEMY_LEVELS_PER_JOB_LEVEL) / ENEMY_LEVELS_PER_JOB_LEVEL
    return int(round(base * _tier_multiplier(tier) * gap_multiplier(scaled_gap)))
