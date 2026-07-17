"""Test twin for parts/events.py -- broadcasts, presence, and say."""

import copy

import pytest

from forge import handle_command, render_scene
from parts import doors, items, npcs
from parts.events import _ECHO_SINKS, announce, announce_frame, bind_echo, broadcast, unbind_echo
from parts.frames import SpeechFrame
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    items_snap = copy.deepcopy(items.ITEMS)
    doors_snap = copy.deepcopy(doors.DOORS)
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    yield
    items.ITEMS.clear()
    items.ITEMS.update(items_snap)
    doors.DOORS.clear()
    doors.DOORS.update(doors_snap)
    npcs.NPCS.clear()
    npcs.NPCS.update(npcs_snap)
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


def test_announce_frame_renders_per_recipient_and_excludes_actor():
    # The typed successor to announce(): a SpeechFrame is delivered, and each sink
    # receives text the frame renders for its own viewer (same room only, not the actor).
    _, a_heard = _seat("a", "library")
    _, b_heard = _seat("b", "library")
    _, c_heard = _seat("c", "forge")
    announce_frame("library", SpeechFrame(speaker_id="a", words="hello there"), exclude="a")
    assert b_heard == ['A says, "hello there"']  # rendered per-recipient
    assert a_heard == []  # the actor is excluded (they get the tick return instead)
    assert c_heard == []  # another room hears nothing
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


def test_say_preserves_the_case_of_the_message():
    """Hostile case: the tick lowercases to ROUTE, but a said line is prose, not a label.
    'say' once pulled its message from the lowercased text and flattened 'Hello, Wren!' to
    'hello, wren!' -- the same lower() trap that once ate passwords. Mixed case must survive."""
    a, _ = _seat("a", "library")
    _, b_heard = _seat("b", "library")
    response = handle_command(a, "say Hello, Wren! Meet me at the Old Reach Bridge.")
    assert response == 'You say, "Hello, Wren! Meet me at the Old Reach Bridge."'
    assert 'A says, "Hello, Wren! Meet me at the Old Reach Bridge."' in b_heard
    unbind_echo("a")
    unbind_echo("b")


def test_say_with_no_message_prompts():
    a, _ = _seat("a", "library")
    assert handle_command(a, "say") == "Say what?"  # bare say, no broadcast
    unbind_echo("a")
    unbind_echo("a")
    unbind_echo("b")


def test_take_is_seen_by_bystanders():
    a, _ = _seat("a", "library")
    _, b_heard = _seat("b", "library")
    handle_command(a, "take key")
    assert "A takes a copper key." in b_heard
    unbind_echo("a")
    unbind_echo("b")


def test_get_is_an_alias_for_take_through_the_spine():
    # get shares take's designation on the command spine (stage 2 slice G).
    a, _ = _seat("a", "library")
    out = handle_command(a, "get key")
    assert "You take" in out
    unbind_echo("a")


def test_drop_is_seen_by_bystanders():
    a, _ = _seat("a", "library")
    _, b_heard = _seat("b", "library")
    handle_command(a, "take key")  # pick it up first
    handle_command(a, "drop key")
    assert "A drops a copper key." in b_heard
    unbind_echo("a")
    unbind_echo("b")


def test_talk_reaches_a_generic_npc_through_the_spine():
    # The non-codex path of _talk_cmd: a plain NPC dialogue line (stage 2 slice G).
    a, _ = _seat("a", "library")
    out = handle_command(a, "talk librarian")
    assert "The librarian says" in out
    unbind_echo("a")


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
