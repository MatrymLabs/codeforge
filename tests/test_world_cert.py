"""Test twin for parts/world_cert.py -- the game adapter: a world-readiness certificate."""

from parts.world.session import SESSIONS, Session
from parts.world_cert import certify


def _player() -> Session:
    s = Session(player_id="matrym", location="courtyard")
    SESSIONS["matrym"] = s
    return s


def test_a_seeded_world_certifies_as_pass():
    out = certify(_player())
    assert "EVIDENCE: PASS" in out
    assert "npcs_loaded" in out
    assert "callings_loaded" in out


def test_certify_flows_through_the_engine_tick():
    from forge import handle_command

    assert "EVIDENCE:" in handle_command(_player(), "certify")
