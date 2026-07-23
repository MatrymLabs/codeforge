"""Test twin for parts/calibrate.py -- the game adapter: auto-retried calibration."""

import pytest

from parts.calibrate import calibrate, set_calibration_rng
from parts.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh():
    set_calibration_rng(None)
    SESSIONS.clear()
    yield
    set_calibration_rng(None)
    SESSIONS.clear()


def _player() -> Session:
    s = Session(player_id="matrym", location="courtyard")
    SESSIONS["matrym"] = s
    return s


def _rng_sequence(values):
    """A deterministic 0..1 source that yields `values` in order (the last value then repeats)."""
    seq = list(values)
    idx = {"i": 0}

    def rng() -> float:
        i = min(idx["i"], len(seq) - 1)
        idx["i"] += 1
        return seq[i]

    return rng


def test_calibration_succeeds_on_the_attempt_that_clears_the_threshold():
    # fail (0.1 < 0.6), fail, then succeed (0.9 >= 0.6) on the third try
    set_calibration_rng(_rng_sequence([0.1, 0.1, 0.9]))
    out = calibrate(_player())
    assert "aligned on attempt 3" in out.lower()


def test_calibration_gives_up_after_the_attempt_budget():
    set_calibration_rng(_rng_sequence([0.0]))  # always fails
    out = calibrate(_player())
    assert "failed after 4 attempts" in out.lower()


def test_calibrate_flows_through_the_engine_tick():
    from forge import handle_command

    set_calibration_rng(_rng_sequence([0.9]))  # succeeds first try
    out = handle_command(_player(), "calibrate")
    assert "aligned on attempt 1" in out.lower()
