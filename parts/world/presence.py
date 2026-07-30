"""CARD: presence -- who is online, kept across the bus so any process reads the roster (Phase 4).

The first real rider on the message bus. When a hero enters or leaves, the gateway announces it onto
the bus; every subscribing process folds that into a shared online set. In one process this simply
mirrors the live sessions, but it is fed THROUGH the bus, so the day a network adapter is injected
the same set becomes cross-process: the admin surface and a second gateway read one true roster
without owning each other's connections. That is the concurrent-player count the metrics panel could
not name before the bus existed.

The roster also carries WHERE each hero stands (Phase 5): the announcement includes the player's
room, so `in_room` gives every process a view of who occupies a room. That is how a player on one
gateway appears in the room scene of a player on another - one shared roster of presence AND place.

The bus is a seam: presence subscribes to whatever get_bus() returns, so a fake bus in tests drives
it with no network. reconnect() re-subscribes after a bus swap (a broker replacing the default).
"""

from __future__ import annotations

from typing import Any

from parts.world import bus

_TOPIC = "presence"
_ONLINE: set[str] = set()
_LOCATION: dict[str, str] = {}  # player -> room, fed by the same announcements (Phase 5)


def _on_event(payload: dict[str, Any]) -> None:
    """Fold one presence announcement into the shared roster (who is online, and where they are)."""
    who = payload.get("player")
    event = payload.get("event")
    if not isinstance(who, str):
        return  # a malformed frame never corrupts the roster
    if event == "online":
        _ONLINE.add(who)
        room = payload.get("room")
        if isinstance(room, str):
            _LOCATION[who] = room
    elif event == "offline":
        _ONLINE.discard(who)
        _LOCATION.pop(who, None)
    elif event == "moved":
        room = payload.get("room")
        if isinstance(room, str) and who in _ONLINE:
            _LOCATION[who] = room


def reconnect() -> None:
    """(Re)subscribe the roster handler to the bus in force.

    Called at import and after any set_bus swap."""
    active = bus.get_bus()
    active.unsubscribe(_TOPIC, _on_event)  # idempotent: no-op if not already subscribed
    active.subscribe(_TOPIC, _on_event)


def mark_online(player: str, room: str = "") -> None:
    """Announce a hero has entered, optionally with the room they spawned into. Named players only:
    the roster is of real characters."""
    frame: dict[str, Any] = {"event": "online", "player": player}
    if room:
        frame["room"] = room
    bus.get_bus().publish(_TOPIC, frame)


def mark_offline(player: str) -> None:
    """Announce a hero has left."""
    bus.get_bus().publish(_TOPIC, {"event": "offline", "player": player})


def mark_at(player: str, room: str) -> None:
    """Announce a hero has moved to a room, so every process's room view stays current (Phase 5)."""
    bus.get_bus().publish(_TOPIC, {"event": "moved", "player": player, "room": room})


def online() -> set[str]:
    """A snapshot of who is online across every process feeding the bus."""
    return set(_ONLINE)


def in_room(room: str) -> set[str]:
    """Who the shared roster places in a room, across every process (Phase 5). Empty until the
    gateway feeds locations, so single-process callers that read live SESSIONS are unaffected."""
    return {player for player, where in _LOCATION.items() if where == room}


def count() -> int:
    """How many heroes are online -- the concurrent-player metric the bus makes possible."""
    return len(_ONLINE)


def _reset() -> None:
    """Clear the roster and re-subscribe to the default bus (tests, so a run never leaks onward)."""
    _ONLINE.clear()
    _LOCATION.clear()
    reconnect()


bus.on_rewire(reconnect)  # a bus swap re-attaches the roster handler
reconnect()  # subscribe to the default in-process bus at import
