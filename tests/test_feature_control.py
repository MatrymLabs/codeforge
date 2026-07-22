"""Test twin for parts/feature_control.py -- the practical adapter + the one-core proof."""

import pytest

from parts.feature_control import FeatureControl
from parts.shelf.feature_flags import FeatureFlagError, FlagRegistry


def test_the_registered_default_governs_without_an_env_override():
    fc = FeatureControl(env={})
    fc.register("kill_switch", default=False)
    assert fc.is_on("kill_switch") is False


def test_an_env_variable_overrides_the_default():
    fc = FeatureControl(env={"FEATURE_KILL_SWITCH": "true"})
    fc.register("kill_switch", default=False)
    assert fc.is_on("kill_switch") is True


def test_an_env_variable_can_also_force_off():
    fc = FeatureControl(env={"FEATURE_CANARY": "false"})
    fc.register("canary", default=True)
    assert fc.is_on("canary") is False


def test_an_unknown_flag_is_an_error():
    with pytest.raises(FeatureFlagError):
        FeatureControl(env={}).is_on("nope")


def test_one_core_powers_both_the_game_panel_and_the_practical_control():
    import parts.features as game

    fc = FeatureControl(env={})
    assert isinstance(fc._registry, FlagRegistry)  # the practical control uses the core
    assert isinstance(game._REGISTRY, FlagRegistry)  # the game panel, same core
