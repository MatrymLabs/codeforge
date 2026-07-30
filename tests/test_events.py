"""Test twin for parts/world/events.py -- broadcasts, presence, and say."""

import copy

import pytest

from forge import handle_command, render_scene
from parts.world import bus, doors, items, npcs
from parts.world.events import (
    _ECHO_SINKS,
    _ECHO_TOPIC,
    _GMCP_TOPIC,
    _ROOM_TOPIC,
    announce,
    announce_frame,
    announce_to,
    bind_echo,
    bind_gmcp,
    broadcast,
    push_channel,
    push_gmcp,
    rename_gmcp,
    unbind_echo,
    unbind_gmcp,
)
from parts.world.frames import SpeechFrame
from parts.world.session import SESSIONS, Session


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


# --- the GMCP push channel ----------------------------------------------------------------------
def test_push_gmcp_delivers_a_frame_to_a_bound_player():
    frames: list[tuple[str, object]] = []
    try:
        bind_gmcp("ada", lambda pkg, data: frames.append((pkg, data)))
        push_gmcp(["ada"], "Char.Party", {"size": 2})
        assert frames == [("Char.Party", {"size": 2})]
    finally:
        unbind_gmcp("ada")


def test_push_gmcp_skips_the_unbound_and_the_excluded():
    frames: list[tuple[str, object]] = []
    try:
        bind_gmcp("ada", lambda pkg, data: frames.append((pkg, data)))
        # bram has no sink (plain-text client / offline); ada is excluded
        push_gmcp(["ada", "bram"], "Char.Guild", {"name": "X"}, exclude="ada")
        assert frames == []  # ada excluded, bram unbound -> nobody delivered
    finally:
        unbind_gmcp("ada")


def test_rename_gmcp_moves_the_channel_to_the_new_name():
    frames: list[tuple[str, object]] = []
    try:
        bind_gmcp("player7", lambda pkg, data: frames.append((pkg, data)))
        rename_gmcp("player7", "ada")  # login rename
        push_gmcp(["player7"], "Char.Party", {})  # the old id no longer reaches them
        push_gmcp(["ada"], "Char.Party", {"size": 3})
        assert frames == [("Char.Party", {"size": 3})]
    finally:
        unbind_gmcp("ada")


def test_push_gmcp_prunes_a_sink_that_raises_oserror():
    def _dead(_pkg: str, _data: object) -> None:
        raise OSError("socket closed")

    bind_gmcp("ada", _dead)
    push_gmcp(["ada"], "Char.Party", {})  # must not raise; the dead sink is pruned
    from parts.world.events import _GMCP_SINKS

    assert "ada" not in _GMCP_SINKS  # pruned, so it is never tried again


def test_push_channel_builds_a_comm_channel_frame():
    frames: list[tuple[str, object]] = []
    try:
        bind_gmcp("ada", lambda pkg, data: frames.append((pkg, data)))
        push_channel(["ada"], "party", "Bram", "on my way")
        assert frames == [
            ("Comm.Channel", {"channel": "party", "from": "Bram", "text": "on my way"})
        ]
    finally:
        unbind_gmcp("ada")


# --- Phase 4: the membership channels ride the bus (cross-process routing) -----------------------
# announce_to / broadcast / push_gmcp publish onto the message bus instead of touching local sinks
# directly, so a cohort split across processes is reached everywhere. In one process the in-process
# bus delivers synchronously (the tests above already prove that path); these pin the SEAM.


def test_announce_to_publishes_onto_the_bus():
    # A spy bus standing in for a broker: it captures the publish instead of delivering. This is
    # what a second process would receive off the wire, proving the message left this process.
    published: list[tuple[str, dict[str, object]]] = []

    class SpyBus:
        def publish(self, topic: str, payload: dict[str, object]) -> None:
            published.append((topic, payload))

        def subscribe(self, topic: str, handler: object) -> None: ...
        def unsubscribe(self, topic: str, handler: object) -> None: ...

    bus.set_bus(SpyBus())
    try:
        announce_to(["ada", "bram"], "the horn sounds.", exclude="cara")
        assert published == [
            (
                _ECHO_TOPIC,
                {"targets": ["ada", "bram"], "text": "the horn sounds.", "exclude": "cara"},
            )
        ]
    finally:
        bus.reset_bus()


def test_broadcast_publishes_a_targets_none_frame():
    published: list[tuple[str, dict[str, object]]] = []

    class SpyBus:
        def publish(self, topic: str, payload: dict[str, object]) -> None:
            published.append((topic, payload))

        def subscribe(self, topic: str, handler: object) -> None: ...
        def unsubscribe(self, topic: str, handler: object) -> None: ...

    bus.set_bus(SpyBus())
    try:
        broadcast("the world shudders.")
        assert published == [
            (_ECHO_TOPIC, {"targets": None, "text": "the world shudders.", "exclude": ""})
        ]
    finally:
        bus.reset_bus()


def test_push_gmcp_publishes_onto_the_bus():
    published: list[tuple[str, dict[str, object]]] = []

    class SpyBus:
        def publish(self, topic: str, payload: dict[str, object]) -> None:
            published.append((topic, payload))

        def subscribe(self, topic: str, handler: object) -> None: ...
        def unsubscribe(self, topic: str, handler: object) -> None: ...

    bus.set_bus(SpyBus())
    try:
        push_gmcp(["ada"], "Char.Party", {"size": 2})
        assert published == [
            (
                _GMCP_TOPIC,
                {"targets": ["ada"], "package": "Char.Party", "data": {"size": 2}, "exclude": ""},
            )
        ]
    finally:
        bus.reset_bus()


def test_a_second_subscriber_sees_the_cohort_message():
    # The cross-process payoff in one process: another subscriber on the delivery topic (a second
    # gateway) receives the same echo frame and delivers to the members IT hosts.
    heard: list[dict[str, object]] = []
    bus.get_bus().subscribe(_ECHO_TOPIC, heard.append)
    try:
        announce_to(["ada"], "rally to me.")
        assert {"targets": ["ada"], "text": "rally to me.", "exclude": ""} in heard
    finally:
        bus.get_bus().unsubscribe(_ECHO_TOPIC, heard.append)


def test_delivery_survives_a_bus_swap():
    # Swap in a fresh bus (standing for a broker). The rewire hook must re-attach the delivery
    # handler, or a production broker injection would silently stop cohort delivery.
    heard: list[str] = []
    bind_echo("ada", heard.append)
    try:
        bus.reset_bus()  # fires the rewire hooks -> _on_echo re-subscribes to the new bus
        announce_to(["ada"], "still here.")
        assert heard == ["still here."]
    finally:
        unbind_echo("ada")
        bus.reset_bus()


# --- Phase 5: room-scoped delivery rides the bus (cross-process rooms) ---------------------------
# announce / announce_frame publish to a room topic; each process delivers to the sinks IT hosts in
# that room. In-process the tests above already prove delivery; these pin the SEAM + the frame wire.


def test_announce_publishes_a_room_frame_onto_the_bus():
    published: list[tuple[str, dict[str, object]]] = []

    class SpyBus:
        def publish(self, topic: str, payload: dict[str, object]) -> None:
            published.append((topic, payload))

        def subscribe(self, topic: str, handler: object) -> None: ...
        def unsubscribe(self, topic: str, handler: object) -> None: ...

    bus.set_bus(SpyBus())
    try:
        announce("forge", "the anvil rings.", exclude="a")
        assert published == [
            (
                "delivery:room",
                {"kind": "text", "room": "forge", "text": "the anvil rings.", "exclude": "a"},
            )
        ]
    finally:
        bus.reset_bus()


def test_announce_frame_publishes_the_frame_as_wire_json():
    published: list[tuple[str, dict[str, object]]] = []

    class SpyBus:
        def publish(self, topic: str, payload: dict[str, object]) -> None:
            published.append((topic, payload))

        def subscribe(self, topic: str, handler: object) -> None: ...
        def unsubscribe(self, topic: str, handler: object) -> None: ...

    bus.set_bus(SpyBus())
    try:
        announce_frame("library", SpeechFrame(speaker_id="a", words="hello"), exclude="a")
        topic, payload = published[0]
        assert topic == "delivery:room"
        assert payload["kind"] == "frame"
        assert payload["frame"] == {
            "type": "SpeechFrame",
            "fields": {"speaker_id": "a", "words": "hello"},
        }
    finally:
        bus.reset_bus()


def test_a_second_process_delivers_a_room_text_to_its_own_occupants():
    # The cross-process payoff: a subscriber standing in for another gateway receives the room frame
    # and delivers to the players IT hosts in that room -- exactly what a remote gateway would do.
    _, b_heard = _seat("b", "forge")  # b is "hosted here"
    _, c_heard = _seat("c", "library")  # different room
    try:
        # simulate a publish that originated on another process (actor 'a' is not local)
        bus.get_bus().publish(
            _ROOM_TOPIC,
            {"kind": "text", "room": "forge", "text": "a distant hammer falls.", "exclude": "a"},
        )
        assert b_heard == ["a distant hammer falls."]  # same room -> heard
        assert c_heard == []  # other room -> silent
    finally:
        unbind_echo("b")
        unbind_echo("c")


def test_a_room_frame_from_the_wire_renders_per_local_recipient():
    _, b_heard = _seat("b", "library")
    try:
        bus.get_bus().publish(
            _ROOM_TOPIC,
            {
                "kind": "frame",
                "room": "library",
                "frame": {
                    "type": "SpeechFrame",
                    "fields": {"speaker_id": "a", "words": "well met"},
                },
                "exclude": "a",
            },
        )
        assert b_heard == ['A says, "well met"']  # reconstructed + rendered locally
    finally:
        unbind_echo("b")
