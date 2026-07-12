"""Test twin for parts/chime.py -- the game adapter for the signal bus."""

from forge import handle_command
from parts.chime import chime
from parts.session import Session


def _player() -> Session:
    return Session(player_id="matrym", location="courtyard")


def test_chime_rings_for_each_announced_traveller():
    out = chime(_player())
    assert "The gate-chime rings for a merchant." in out
    assert "The gate-chime rings for a pilgrim." in out


def test_chime_is_reachable_through_the_engine_tick():
    assert "gate-chime rings" in handle_command(_player(), "chime")
