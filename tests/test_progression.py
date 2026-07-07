"""Test twin for parts/progression.py -- mk1 checkpoints plus Hypothesis laws."""

from hypothesis import given
from hypothesis import strategies as st

from parts.progression import (
    cumulative_jp_for_level,
    cumulative_xp_for_level,
    get_jp_tier_multiplier,
    get_next_job_level_threshold,
    get_next_level_threshold,
    get_xp_tier_multiplier,
    hp_gain_per_level,
    marginal_jp_for_level,
    marginal_xp_for_level,
    mp_gain_per_level,
)

# --- locked design checkpoints (must never drift) ---


def test_cumulative_xp_checkpoint_plvl_50():
    assert cumulative_xp_for_level(50) == 31875


def test_cumulative_jp_checkpoint_job_level_30():
    assert cumulative_jp_for_level(30) == 51200


# --- tier multipliers inside each band ---


def test_xp_tier_multipliers_inside_each_band():
    assert get_xp_tier_multiplier(25) == 1
    assert get_xp_tier_multiplier(75) == 2
    assert get_xp_tier_multiplier(125) == 3
    assert get_xp_tier_multiplier(175) == 6
    assert get_xp_tier_multiplier(230) == 15


def test_jp_tier_multipliers_inside_each_band():
    assert get_jp_tier_multiplier(5) == 1
    assert get_jp_tier_multiplier(15) == 3
    assert get_jp_tier_multiplier(25) == 8


# --- marginal costs are zero outside legal ranges (refusal cases) ---


def test_marginal_xp_zero_below_range():
    assert marginal_xp_for_level(0) == 0


def test_marginal_xp_zero_above_cap():
    assert marginal_xp_for_level(256) == 0


def test_marginal_jp_zero_above_cap():
    assert marginal_jp_for_level(31) == 0


# --- next-threshold helpers return None at the caps ---


def test_next_level_threshold_none_at_plvl_cap():
    assert get_next_level_threshold(255) is None


def test_next_job_level_threshold_none_at_job_cap():
    assert get_next_job_level_threshold(30) is None


# --- and still advance correctly just below the caps (acceptance cases) ---


def test_next_level_threshold_below_cap_matches_cumulative():
    assert get_next_level_threshold(49) == cumulative_xp_for_level(50) == 31875


def test_next_job_level_threshold_below_cap_matches_cumulative():
    assert get_next_job_level_threshold(29) == cumulative_jp_for_level(30) == 51200


# --- Hypothesis property tests: laws across the whole curve ---


@given(st.integers(min_value=1, max_value=254))
def test_xp_curve_never_gets_cheaper(level):
    """The marginal cost of the next level is never below this one's."""
    assert marginal_xp_for_level(level + 1) >= marginal_xp_for_level(level)


@given(st.integers(min_value=1, max_value=255))
def test_cumulative_xp_is_strictly_increasing(level):
    assert cumulative_xp_for_level(level) > cumulative_xp_for_level(level - 1)


@given(st.integers(min_value=1, max_value=29))
def test_jp_thresholds_always_ahead_of_current_total(level):
    assert get_next_job_level_threshold(level) > cumulative_jp_for_level(level)


@given(st.integers(min_value=0, max_value=100))
def test_hp_and_mp_gains_are_always_positive(stat):
    assert hp_gain_per_level(stat) >= 4
    assert mp_gain_per_level(stat) >= 1
