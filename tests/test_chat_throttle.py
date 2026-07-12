"""Test twin for parts/chat_throttle.py -- the game adapter: a rate-limited shout."""

import pytest

from parts.chat_throttle import reset_throttles, shout
from parts.session import SESSIONS, Session


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


@pytest.fixture(autouse=True)
def fresh():
    reset_throttles()
    SESSIONS.clear()
    yield
    reset_throttles()
    SESSIONS.clear()


def _player() -> Session:
    s = Session(player_id="matrym", location="courtyard")
    SESSIONS["matrym"] = s
    return s


def test_a_shout_broadcasts_and_costs_a_token():
    out = shout(_player(), "Hello there")
    assert out == 'You shout, "Hello there"'


def test_empty_shout_is_refused_gently():
    assert shout(_player(), "  ") == "Shout what?"


def test_over_shouting_is_throttled_with_the_wait():
    clk = FakeClock()
    reset_throttles(clock=clk)
    s = _player()
    assert shout(s, "one").startswith("You shout")  # burst of 3
    assert shout(s, "two").startswith("You shout")
    assert shout(s, "three").startswith("You shout")
    hoarse = shout(s, "four")  # bucket empty
    assert "hoarse" in hoarse and "20s" in hoarse
    clk.advance(20)  # one token refills
    assert shout(s, "five").startswith("You shout")


def test_shout_flows_through_the_engine_tick():
    from forge import handle_command

    out = handle_command(_player(), "shout Hello There")
    assert out == 'You shout, "Hello There"'  # original case preserved
