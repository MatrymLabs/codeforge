"""Test twin for parts/telegraph.py -- the game adapter for the stream framer."""

from forge import handle_command
from parts.telegraph import telegraph
from parts.world.session import Session


def _player() -> Session:
    return Session(player_id="matrym", location="courtyard")


def test_bursty_dispatch_reassembles_into_clean_lines():
    out = telegraph(_player())
    # Lines split mid-burst upstream must reappear whole.
    assert "THE FORGE IS LIT." in out
    assert "A courier rides from the north." in out
    assert "Bring word to the Keep." in out


def test_telegraph_is_reachable_through_the_engine_tick():
    assert "A telegraph arrives" in handle_command(_player(), "telegraph")
