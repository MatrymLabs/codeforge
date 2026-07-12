"""Test twin for parts/relay.py -- the game adapter: a circuit-broken power relay."""

import pytest

from parts.relay import channel, reset_relay
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh():
    reset_relay()
    SESSIONS.clear()
    yield
    reset_relay()
    SESSIONS.clear()


def _player() -> Session:
    s = Session(player_id="matrym", location="courtyard")
    SESSIONS["matrym"] = s
    return s


def test_a_successful_channel_flows_power():
    reset_relay(rng=lambda: 0.9)  # >= 0.7: never surges
    assert "Power flows" in channel(_player())


def test_repeated_surges_trip_the_relay_shut():
    reset_relay(rng=lambda: 0.0)  # < 0.7: always surges
    s = _player()
    for _ in range(3):  # threshold is 3 consecutive failures
        assert "sparks and fails" in channel(s)
    assert "tripped shut" in channel(s).lower()  # now open: fail fast


def test_channel_flows_through_the_engine_tick():
    from forge import handle_command

    reset_relay(rng=lambda: 0.9)
    assert "Power flows" in handle_command(_player(), "channel")
