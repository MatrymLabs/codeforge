"""Test twin for parts/vitals.py -- the game adapter: a world-vitals health panel."""

from parts.session import SESSIONS, Session
from parts.vitals import vitals


def _player() -> Session:
    s = Session(player_id="matrym", location="courtyard")
    SESSIONS["matrym"] = s
    return s


def test_the_panel_reports_overall_health_and_subsystems():
    out = vitals(_player())
    assert "HEALTH:" in out
    assert "engine" in out
    assert "npcs" in out
    assert "callings" in out


def test_a_seeded_world_is_healthy():
    # NPCs and callings load from the seed, so the panel is green in a normal world.
    assert "HEALTH: healthy" in vitals(_player())


def test_vitals_flows_through_the_engine_tick():
    from forge import handle_command

    assert "HEALTH:" in handle_command(_player(), "vitals")
