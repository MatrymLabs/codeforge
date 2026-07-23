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

from dataclasses import dataclass

from parts.world.seed import SEED_DIR
from parts.world.world_manifest import world_block

# ---------------------------------------------------------------------------
# Per-PLvl gains (locked design July 2026):
# each level grants stat points (spent via `allocate`, max 3 into any single
# stat per level gained) and HP/MP growth driven by STA and MAG respectively.
# ---------------------------------------------------------------------------

STAT_POINTS_PER_LEVEL = 5
MAX_ALLOC_PER_STAT_PER_LEVEL = 3  # cumulative cap: 3 x (plvl - 1) per stat


def hp_gain_per_level(sta):
    """HP gained on a PLvl-up: base + 1 per `per` points of STA (default base 4, per 4)."""
    return _ACTIVE_GAINS.hp_base + sta // _ACTIVE_GAINS.hp_per


def mp_gain_per_level(mag):
    """MP gained on a PLvl-up: base + 1 per `per` points of MAG (default base 1, per 4)."""
    return _ACTIVE_GAINS.mp_base + mag // _ACTIVE_GAINS.mp_per


XP_BASE = 25

XP_TIERS = [
    (1, 50, 1),
    (51, 99, 2),
    (100, 150, 3),
    (151, 200, 6),
    (201, 255, 15),
]


# XP and JP progression are the same algorithm; a "track" is (base, tiers, cap) and is all they
# differ by. Parameterizing here removed four duplicate-logic pairs the clone scan flagged.
XP_TRACK = (XP_BASE, XP_TIERS, 255)


def _tier_multiplier(track, level):
    """The tier multiplier for `level` on a track, or 1 past the last tier."""
    _base, tiers, _cap = track
    for start, end, mult in tiers:
        if start <= level <= end:
            return mult
    return 1


def _marginal(track, level):
    """The cost of the single level `level` on a track (0 if out of range 1..cap)."""
    base, _tiers, cap = track
    if level < 1 or level > cap:
        return 0
    return base * level * _tier_multiplier(track, level)


def _cumulative(track, level):
    """Total cost to reach `level` on a track (inclusive sum of levels 1..level)."""
    if level < 1:
        return 0
    return sum(_marginal(track, lvl) for lvl in range(1, level + 1))


def _next_threshold(track, current):
    """Total cost to reach the next level on a track, or None at the cap."""
    _base, _tiers, cap = track
    if current >= cap:
        return None
    return _cumulative(track, current + 1)


def get_xp_tier_multiplier(level):
    """Return the tier multiplier (1, 2, 3, 6, or 15) for a given PLvl."""
    return _tier_multiplier(_ACTIVE_XP_TRACK, level)


def marginal_xp_for_level(level):
    """XP cost of the single level `level` (0 if out of range 1-255)."""
    return _marginal(_ACTIVE_XP_TRACK, level)


def cumulative_xp_for_level(level):
    """Total XP to reach a given PLvl (inclusive sum of levels 1..level)."""
    return _cumulative(_ACTIVE_XP_TRACK, level)


def get_next_level_threshold(current_level):
    """Total XP to reach the next PLvl, or None if at cap (255)."""
    return _next_threshold(_ACTIVE_XP_TRACK, current_level)


JP_BASE = 20

JP_TIERS = [
    (1, 10, 1),
    (11, 20, 3),
    (21, 30, 8),
]


JP_TRACK = (JP_BASE, JP_TIERS, 30)


def get_jp_tier_multiplier(level):
    """Return the tier multiplier (1, 3, or 8) for a given Job Lvl."""
    return _tier_multiplier(_ACTIVE_JP_TRACK, level)


def marginal_jp_for_level(level):
    """JP cost of the single Job Lvl `level` (0 if out of range 1-30)."""
    return _marginal(_ACTIVE_JP_TRACK, level)


def cumulative_jp_for_level(level):
    """Total JP to reach a given Job Lvl (inclusive sum of levels 1..level)."""
    return _cumulative(_ACTIVE_JP_TRACK, level)


def get_next_job_level_threshold(current_job_level):
    """Total JP to reach the next Job Lvl, or None if at cap (30)."""
    return _next_threshold(_ACTIVE_JP_TRACK, current_job_level)


class ProgressionError(ValueError):
    """A progression config was declared with an invalid field. Fails loud at construction."""


def _track_from_dict(name, raw):
    """Validate + build one (base, tiers, cap) track from a mapping. Fails loud by field."""
    if not isinstance(raw, dict):
        raise ProgressionError(f"the {name!r} track must be a mapping")
    base, cap, tiers_raw = raw.get("base"), raw.get("cap"), raw.get("tiers")
    if not isinstance(base, int) or isinstance(base, bool) or base <= 0:
        raise ProgressionError(f"{name!r} track: 'base' must be a positive int")
    if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
        raise ProgressionError(f"{name!r} track: 'cap' must be a positive int")
    if not isinstance(tiers_raw, list) or not tiers_raw:
        raise ProgressionError(f"{name!r} track: 'tiers' must be a non-empty list")
    tiers = []
    for tier in tiers_raw:
        if not isinstance(tier, (list, tuple)) or len(tier) != 3:
            raise ProgressionError(f"{name!r} track: each tier must be [start, end, multiplier]")
        start, end, mult = tier
        if not all(isinstance(x, int) and not isinstance(x, bool) for x in (start, end, mult)):
            raise ProgressionError(f"{name!r} track: tier values must be ints")
        if start > end:
            raise ProgressionError(f"{name!r} track: tier start {start} > end {end}")
        tiers.append((start, end, mult))
    return (base, tiers, cap)


def tracks_from_dict(raw):
    """Build + validate the (xp, jp) tracks from a world's `progression:` block. Fails loud."""
    if not isinstance(raw, dict):
        raise ProgressionError("a progression block must be a mapping")
    for axis in ("xp", "jp"):
        if axis not in raw:
            raise ProgressionError(f"progression block is missing the {axis!r} track")
    return (_track_from_dict("xp", raw["xp"]), _track_from_dict("jp", raw["jp"]))


# The default curves, captured before the active binding below (the checkpoint test pins these).
DEFAULT_TRACKS = (XP_TRACK, JP_TRACK)


def _load_active_tracks():
    """The (xp, jp) tracks the world declares in world.yaml `progression:`, else the default."""
    block = world_block(SEED_DIR, "progression")
    return tracks_from_dict(block) if block is not None else DEFAULT_TRACKS


# Bound at import from the booted world -- same seed-defined-at-import pattern as the stat ruleset.
_active = _load_active_tracks()
_ACTIVE_XP_TRACK = _active[0]
_ACTIVE_JP_TRACK = _active[1]


@dataclass(frozen=True)
class Gains:
    """The per-level HP/MP growth: hp = hp_base + STA // hp_per; mp = mp_base + MAG // mp_per."""

    hp_base: int
    hp_per: int
    mp_base: int
    mp_per: int


DEFAULT_GAINS = Gains(hp_base=4, hp_per=4, mp_base=1, mp_per=4)  # the locked design (July 2026)


def gains_from_dict(raw):
    """Build + validate the per-level gains from a world's `gains:` block. Fails loud; the two
    `*_per` divisors must be positive (a zero would divide by zero on a level-up)."""
    if not isinstance(raw, dict):
        raise ProgressionError("a gains block must be a mapping")
    values = {}
    for field, default, positive in (
        ("hp_base", 4, False),
        ("hp_per", 4, True),
        ("mp_base", 1, False),
        ("mp_per", 4, True),
    ):
        value = raw.get(field, default)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ProgressionError(f"gains: {field!r} must be an int")
        if positive and value <= 0:
            raise ProgressionError(f"gains: {field!r} must be positive (it is a divisor)")
        if not positive and value < 0:
            raise ProgressionError(f"gains: {field!r} must be non-negative")
        values[field] = value
    return Gains(**values)


def _load_active_gains():
    """The per-level gains the booted world declares in world.yaml `gains:`, else the default."""
    block = world_block(SEED_DIR, "gains")
    return gains_from_dict(block) if block is not None else DEFAULT_GAINS


_ACTIVE_GAINS = _load_active_gains()
