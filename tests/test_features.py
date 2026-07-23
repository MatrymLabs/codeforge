"""Test twin for parts/features.py -- the game adapter: an in-world feature panel."""

import pytest

from parts.features import _REGISTRY, feature_on, features, reset_features
from parts.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh():
    reset_features()
    SESSIONS.clear()
    yield
    reset_features()
    SESSIONS.clear()


def _player() -> Session:
    s = Session(player_id="matrym", location="courtyard")
    SESSIONS["matrym"] = s
    return s


def test_the_panel_lists_flags_and_their_state():
    out = features(_player())
    assert "beta_quests" in out
    assert "[off]" in out  # beta content is off by default


def test_feature_on_reflects_a_runtime_toggle():
    assert feature_on("beta_quests") is False
    _REGISTRY.enable("beta_quests")
    assert feature_on("beta_quests") is True
    assert "[on ]" in features(_player())


def test_features_flows_through_the_engine_tick():
    from forge import handle_command

    assert "feature flags" in handle_command(_player(), "features")
