"""Test twin for parts/maintenance.py -- the game adapter for the change ledger."""

from forge import handle_command
from parts.maintenance import maintenance
from parts.session import Session


def _player() -> Session:
    return Session(player_id="matrym", location="courtyard")


def test_the_log_renders_entries_with_their_lifecycle_state():
    out = maintenance(_player())
    assert "World maintenance log:" in out
    assert "WM-001" in out and "triaged" in out  # WM-001 sits at triaged
    assert "WM-002" in out and "approved" in out  # WM-002 was approved


def test_the_verb_is_reachable_through_the_engine_tick():
    out = handle_command(_player(), "maintenance")
    assert "World maintenance log:" in out
