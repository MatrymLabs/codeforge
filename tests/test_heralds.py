"""Test twin for parts/heralds.py -- the game adapter: pluggable in-world heralds."""

import pytest

from parts.heralds import _REGISTRY, heralds, reset_heralds
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh():
    reset_heralds()
    SESSIONS.clear()
    yield
    reset_heralds()
    SESSIONS.clear()


def _player() -> Session:
    s = Session(player_id="matrym", location="courtyard")
    SESSIONS["matrym"] = s
    return s


def test_active_heralds_proclaim():
    out = heralds(_player())
    assert "The forge is lit" in out
    assert "song drifts" in out


def test_a_disabled_herald_falls_silent():
    _REGISTRY.disable("bard")
    out = heralds(_player())
    assert "song drifts" not in out
    assert "The forge is lit" in out  # the crier still speaks


def test_heralds_flows_through_the_engine_tick():
    from forge import handle_command

    assert "Hear ye" in handle_command(_player(), "heralds")
