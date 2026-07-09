"""Test twin for parts/events.py -- broadcasts, presence, and say."""

import copy

import pytest

from forge import handle_command, render_scene
from parts import doors, items, npcs
from parts.events import _ECHO_SINKS, announce, bind_echo, broadcast, unbind_echo
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    items_snap = copy.deepcopy(items.ITEMS)
    doors_snap = copy.deepcopy(doors.DOORS)
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    yield
    items.ITEMS = items_snap
    doors.DOORS = doors_snap
    npcs.NPCS = npcs_snap
    SESSIONS.clear()


def _seat(player_id: str, location: str) -> tuple[Session, list[str]]:
    """Seat a player with a list-capturing sink; returns (session, heard)."""
    s = Session(player_id=player_id, location=location)
    SESSIONS[player_id] = s
    heard: list[str] = []
    bind_echo(player_id, heard.append)
    return s, heard


def test_announce_reaches_room_but_not_actor():
    _, a_heard = _seat("a", "library")
    _, b_heard = _seat("b", "library")
    _, c_heard = _seat("c", "forge")
    announce("library", "something happens.", exclude="a")
    assert b_heard == ["something happens."]
    assert a_heard == []
    assert c_heard == []
    for pid in ("a", "b", "c"):
        unbind_echo(pid)


def test_movement_announces_departure_and_arrival():
    a, _ = _seat("a", "forge")
    _, b_heard = _seat("b", "forge")
    _, c_heard = _seat("c", "courtyard")
    handle_command(a, "n")
    assert "A leaves north." in b_heard
    assert "A arrives." in c_heard
    for pid in ("a", "b", "c"):
        unbind_echo(pid)


def test_say_is_heard_by_the_room():
    a, _ = _seat("a", "library")
    _, b_heard = _seat("b", "library")
    response = handle_command(a, "say hello there")
    assert response == 'You say, "hello there"'
    assert 'A says, "hello there"' in b_heard
    unbind_echo("a")
    unbind_echo("b")


def test_take_is_seen_by_bystanders():
    a, _ = _seat("a", "library")
    _, b_heard = _seat("b", "library")
    handle_command(a, "take key")
    assert "A takes a copper key." in b_heard
    unbind_echo("a")
    unbind_echo("b")


def _dead_sink(_text: str) -> None:
    """A client whose socket is gone -- writing to it raises, like a real
    BrokenPipeError / Bad file descriptor."""
    raise OSError(9, "Bad file descriptor")


def test_dead_sink_does_not_crash_a_broadcast_and_is_pruned():
    # A dropped client (dead socket) shares the room with a live listener.
    _seat("ghost", "library")
    bind_echo("ghost", _dead_sink)  # overwrite ghost's sink with a dead one
    _, live_heard = _seat("live", "library")
    # The acting player's broadcast must NOT raise, and the live player still hears it.
    announce("library", "the anvil rings.", exclude="actor")
    assert live_heard == ["the anvil rings."]
    # The dead channel is pruned so it is never tried again.
    assert "ghost" not in _ECHO_SINKS
    unbind_echo("live")


def test_broadcast_survives_a_dead_sink():
    _seat("ghost", "forge")
    bind_echo("ghost", _dead_sink)
    _, live_heard = _seat("live", "forge")
    broadcast("the world shudders.")  # must not raise
    assert live_heard == ["the world shudders."]
    assert "ghost" not in _ECHO_SINKS
    unbind_echo("live")


def test_scene_shows_other_players_but_not_yourself():
    _seat("a", "library")
    _seat("b", "library")
    scene = render_scene("library", viewer="a")
    assert "B is here." in scene
    assert "A is here." not in scene
    unbind_echo("a")
    unbind_echo("b")
