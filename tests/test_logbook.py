"""Test twin for parts/logbook.py -- the game adapter: a repository-backed logbook."""

import pytest

from parts.logbook import journal, reset_logbooks
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh():
    reset_logbooks()
    SESSIONS.clear()
    yield
    reset_logbooks()
    SESSIONS.clear()


def _player(pid: str = "matrym") -> Session:
    s = Session(player_id=pid, location="courtyard")
    SESSIONS[pid] = s
    return s


def test_an_empty_logbook_prompts_for_a_line():
    assert "empty" in journal(_player())


def test_entries_are_numbered_and_listed():
    s = _player()
    assert "#1" in journal(s, "found a copper key")
    assert "#2" in journal(s, "the oak door is sealed")
    listing = journal(s)
    assert "1. found a copper key" in listing
    assert "2. the oak door is sealed" in listing


def test_logbooks_are_isolated_per_player():
    journal(_player("alice"), "alice's secret")
    assert "empty" in journal(_player("bob"))  # bob sees nothing of alice's


def test_journal_flows_through_the_engine_tick():
    from forge import handle_command

    s = _player()
    assert "#1" in handle_command(s, "journal A Note With Case")
    assert "A Note With Case" in handle_command(s, "journal")  # original case preserved
