"""CARD: progression -- XP and JP level curves (locked design, July 2026).

Salvaged from codeforge_mk1. This is game DESIGN encoded as pure
functions -- the numbers are the product. Two independent axes:

1. XP -> PLvl (character level, global, capped at 255)
2. JP -> Job Lvl (per-job, capped at 30)

Cumulative totals are INCLUSIVE: cumulative_*_for_level(N) sums the
marginal cost of levels 1..N, matching the locked checkpoints
(PLvl 50 = 31,875 XP; Job Lvl 30 = 51,200 JP). The test twin pins
those checkpoints forever: if the numbers drift, the build goes red.
"""

# ---------------------------------------------------------------------------
# Per-PLvl gains (locked design July 2026):
# each level grants stat points (spent via `allocate`, max 3 into any single
# stat per level gained) and HP/MP growth driven by STA and MAG respectively.
# ---------------------------------------------------------------------------

STAT_POINTS_PER_LEVEL = 5
MAX_ALLOC_PER_STAT_PER_LEVEL = 3  # cumulative cap: 3 x (plvl - 1) per stat


def hp_gain_per_level(sta):
    """HP gained on a PLvl-up: base 4, +1 per 4 points of STA."""
    return 4 + sta // 4


def mp_gain_per_level(mag):
    """MP gained on a PLvl-up: base 1, +1 per 4 points of MAG."""
    return 1 + mag // 4


XP_BASE = 25

XP_TIERS = [
    (1, 50, 1),
    (51, 99, 2),
    (100, 150, 3),
    (151, 200, 6),
    (201, 255, 15),
]


def get_xp_tier_multiplier(level):
    """Return the tier multiplier (1, 2, 3, 6, or 15) for a given PLvl."""
    for start, end, mult in XP_TIERS:
        if start <= level <= end:
            return mult
    return 1


def marginal_xp_for_level(level):
    """XP cost of the single level `level` (0 if out of range 1-255)."""
    if level < 1 or level > 255:
        return 0
    return XP_BASE * level * get_xp_tier_multiplier(level)


def cumulative_xp_for_level(level):
    """Total XP to reach a given PLvl (inclusive sum of levels 1..level)."""
    if level < 1:
        return 0
    total = 0
    for lvl in range(1, level + 1):
        total += marginal_xp_for_level(lvl)
    return total


def get_next_level_threshold(current_level):
    """Total XP to reach the next PLvl, or None if at cap (255)."""
    if current_level >= 255:
        return None
    return cumulative_xp_for_level(current_level + 1)


JP_BASE = 20

JP_TIERS = [
    (1, 10, 1),
    (11, 20, 3),
    (21, 30, 8),
]


def get_jp_tier_multiplier(level):
    """Return the tier multiplier (1, 3, or 8) for a given Job Lvl."""
    for start, end, mult in JP_TIERS:
        if start <= level <= end:
            return mult
    return 1


def marginal_jp_for_level(level):
    """JP cost of the single Job Lvl `level` (0 if out of range 1-30)."""
    if level < 1 or level > 30:
        return 0
    return JP_BASE * level * get_jp_tier_multiplier(level)


def cumulative_jp_for_level(level):
    """Total JP to reach a given Job Lvl (inclusive sum of levels 1..level)."""
    if level < 1:
        return 0
    total = 0
    for lvl in range(1, level + 1):
        total += marginal_jp_for_level(lvl)
    return total


def get_next_job_level_threshold(current_job_level):
    """Total JP to reach the next Job Lvl, or None if at cap (30)."""
    if current_job_level >= 30:
        return None
    return cumulative_jp_for_level(current_job_level + 1)
