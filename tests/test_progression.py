"""Test twin for parts/progression.py -- mk1 checkpoints plus Hypothesis laws."""

import pytest
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


def test_tier_multiplier_defaults_to_one_past_the_tiers():
    # A level below or above every tier falls through to the default multiplier of 1.
    assert get_xp_tier_multiplier(0) == 1
    assert get_jp_tier_multiplier(999) == 1


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


@pytest.mark.property
@given(st.integers(min_value=1, max_value=254))
def test_xp_curve_never_gets_cheaper(level):
    """The marginal cost of the next level is never below this one's."""
    assert marginal_xp_for_level(level + 1) >= marginal_xp_for_level(level)


@pytest.mark.property
@given(st.integers(min_value=1, max_value=255))
def test_cumulative_xp_is_strictly_increasing(level):
    assert cumulative_xp_for_level(level) > cumulative_xp_for_level(level - 1)


@pytest.mark.property
@given(st.integers(min_value=1, max_value=29))
def test_jp_thresholds_always_ahead_of_current_total(level):
    assert get_next_job_level_threshold(level) > cumulative_jp_for_level(level)


@pytest.mark.property
@given(st.integers(min_value=0, max_value=100))
def test_hp_and_mp_gains_are_always_positive(stat):
    assert hp_gain_per_level(stat) >= 4
    assert mp_gain_per_level(stat) >= 1


# --- configurable curve: a world can declare its own progression (config, not hardcode) -------
import parts.progression as prog  # noqa: E402
from parts.world_manifest import world_block  # noqa: E402

_A_PROGRESSION_BLOCK = """
progression:
  xp: {base: 10, cap: 10, tiers: [[1, 10, 1]]}
  jp: {base: 5, cap: 5, tiers: [[1, 5, 1]]}
"""


def test_the_default_tracks_are_the_locked_curve() -> None:
    assert prog.DEFAULT_TRACKS == (prog.XP_TRACK, prog.JP_TRACK)


def test_a_world_can_declare_its_own_progression(tmp_path) -> None:
    seed = tmp_path / "grindy"
    seed.mkdir()
    (seed / "world.yaml").write_text(
        "world_id: grindy\ntitle: G\nstart_room: r\n" + _A_PROGRESSION_BLOCK
    )
    xp_track, jp_track = prog.tracks_from_dict(world_block(seed, "progression"))
    # xp: base 10, single tier x1 -> cumulative to lvl 3 = 10*(1+2+3) = 60
    assert prog._cumulative(xp_track, 3) == 60
    assert jp_track[2] == 5  # cap


def test_get_next_level_threshold_uses_the_active_track(monkeypatch) -> None:
    # A world's declared curve reaches the public API: the functions read the active track.
    monkeypatch.setattr(prog, "_ACTIVE_XP_TRACK", (10, [(1, 10, 1)], 10))
    assert prog.get_next_level_threshold(2) == 60  # cumulative to lvl 3 under the declared curve


def test_a_seed_without_a_progression_block_uses_the_default(tmp_path) -> None:
    seed = tmp_path / "plain"
    seed.mkdir()
    (seed / "world.yaml").write_text("world_id: plain\ntitle: P\nstart_room: r\n")
    assert world_block(seed, "progression") is None  # -> _load_active_tracks falls back to default


@pytest.mark.parametrize(
    "block",
    [
        "not a mapping",
        {"xp": {"base": 10, "cap": 10, "tiers": [[1, 10, 1]]}},  # missing jp
        {
            "xp": {"base": 0, "cap": 10, "tiers": [[1, 10, 1]]},
            "jp": {"base": 5, "cap": 5, "tiers": [[1, 5, 1]]},
        },  # base <= 0
        {
            "xp": {"base": 10, "cap": 10, "tiers": []},
            "jp": {"base": 5, "cap": 5, "tiers": [[1, 5, 1]]},
        },  # empty tiers
        {
            "xp": {"base": 10, "cap": 10, "tiers": [[9, 1, 1]]},
            "jp": {"base": 5, "cap": 5, "tiers": [[1, 5, 1]]},
        },  # start > end
    ],
)
def test_a_malformed_progression_block_fails_loud(block) -> None:
    with pytest.raises(prog.ProgressionError):
        prog.tracks_from_dict(block)
