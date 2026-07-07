"""Test twin for parts/stats.py -- ported from mk1 test_kernel."""

from dataclasses import FrozenInstanceError

import pytest

from parts.stats import Stat, StatBlock, StatModifier


def test_valid_stat_constructs():
    s = Stat(name="strength", base=50)
    assert s.base == 50
    assert s.min_value == 0
    assert s.max_value == 100


def test_base_outside_bounds_rejected():
    with pytest.raises(ValueError):
        Stat(name="strength", base=150)


def test_empty_name_rejected():
    with pytest.raises(ValueError):
        Stat(name="   ", base=10)


def test_inverted_bounds_rejected():
    with pytest.raises(ValueError):
        Stat(name="agility", base=5, min_value=10, max_value=1)


def test_stat_is_immutable():
    s = Stat(name="wisdom", base=30)
    with pytest.raises(FrozenInstanceError):
        s.base = 99


def test_float_base_rejected():
    with pytest.raises(ValueError):
        Stat(name="HP", base=50.5)


def test_valid_block_constructs_and_gets():
    block = StatBlock(stats=(Stat(name="strength", base=50),))
    assert block.get("strength").base == 50


def test_duplicate_names_rejected():
    with pytest.raises(ValueError):
        StatBlock(
            stats=(
                Stat(name="strength", base=50),
                Stat(name="strength", base=10),
            )
        )


def test_non_stat_member_rejected():
    with pytest.raises(ValueError):
        StatBlock(stats=(Stat(name="strength", base=50), "not a stat"))


def test_missing_name_raises_keyerror():
    block = StatBlock(stats=(Stat(name="strength", base=50),))
    with pytest.raises(KeyError):
        block.get("wisdom")


def test_block_is_immutable():
    block = StatBlock(stats=(Stat(name="strength", base=50),))
    with pytest.raises(FrozenInstanceError):
        block.stats = ()


def test_empty_block_constructs():
    block = StatBlock(stats=())
    with pytest.raises(KeyError):
        block.get("anything")


def test_flat_and_percent_apply_to_base():
    stat = Stat(name="strength", base=50)
    mod = StatModifier(source="sword", flat=10, percent=0.5)
    assert mod.apply(stat) == 85  # 50 + 10 + (50 * 0.5), NOT (50+10) * 1.5


def test_result_clamped_to_max():
    stat = Stat(name="strength", base=90)
    mod = StatModifier(source="giant strength", flat=50)
    assert mod.apply(stat) == 100  # stat's own max_value


def test_negative_modifier_clamped_to_min():
    stat = Stat(name="strength", base=10)
    mod = StatModifier(source="curse", flat=-50)
    assert mod.apply(stat) == 0  # stat's own min_value


def test_empty_source_rejected():
    with pytest.raises(ValueError):
        StatModifier(source="  ")


def test_zero_modifier_is_identity():
    stat = Stat(name="strength", base=50)
    mod = StatModifier(source="nothing")
    assert mod.apply(stat) == stat.base


def test_bool_flat_rejected():
    with pytest.raises(ValueError):
        StatModifier(source="bug", flat=True)
