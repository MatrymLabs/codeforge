"""Test twin for parts/session.py and the engine tick.

Note what is MISSING here: no monkeypatch, no capsys, no fake
keyboard. The engine tick is a plain function -- command in,
response out. This is the shape a gateway calls per line."""

import copy

import pytest

from forge import handle_command
from parts import doors, items, npcs
from parts.session import Session


@pytest.fixture(autouse=True)
def fresh_world():
    items_snap = copy.deepcopy(items.ITEMS)
    doors_snap = copy.deepcopy(doors.DOORS)
    npcs_snap = copy.deepcopy(npcs.NPCS)
    yield
    items.ITEMS = items_snap
    doors.DOORS = doors_snap
    npcs.NPCS = npcs_snap


def test_session_starts_at_the_forge_and_alive():
    session = Session(player_id="josh")
    assert session.location == "forge"
    assert session.alive is True


def test_tick_moves_the_session():
    session = Session(player_id="josh")
    response = handle_command(session, "n")
    assert session.location == "courtyard"
    assert "Broken Courtyard" in response


def test_tick_blocked_by_locked_door_returns_message():
    session = Session(player_id="josh", location="library")
    response = handle_command(session, "n")
    assert session.location == "library"
    assert "locked" in response


def test_tick_full_chain_take_unlock_enter():
    session = Session(player_id="josh", location="library")
    handle_command(session, "take key")
    handle_command(session, "unlock door with key")
    response = handle_command(session, "go north")
    assert session.location == "archive"
    assert "Sealed Archive" in response


def test_quit_kills_the_session():
    session = Session(player_id="josh")
    handle_command(session, "quit")
    assert session.alive is False


def test_two_sessions_share_one_world():
    """The MMO seed: player A takes the key; player B sees it gone."""
    a = Session(player_id="a", location="library")
    b = Session(player_id="b", location="library")
    handle_command(a, "take key")
    response = handle_command(b, "take key")
    assert response == "You don't see that here."
