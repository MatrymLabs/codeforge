"""CARD: presence -- who is online, kept across the bus so any process reads the roster (Phase 4).

The first real rider on the message bus. When a hero enters or leaves, the gateway announces it onto
the bus; every subscribing process folds that into a shared online set. In one process this simply
mirrors the live sessions, but it is fed THROUGH the bus, so the day a network adapter is injected
the same set becomes cross-process: the admin surface and a second gateway read one true roster
without owning each other's connections. That is the concurrent-player count the metrics panel could
not name before the bus existed.

The bus is a seam: presence subscribes to whatever get_bus() returns, so a fake bus in tests drives
it with no network. reconnect() re-subscribes after a bus swap (a broker replacing the default).
"""

from __future__ import annotations

from typing import Any

from parts.world import bus

_TOPIC = "presence"
_ONLINE: set[str] = set()


def _on_event(payload: dict[str, Any]) -> None:
    """Fold one presence announcement into the shared roster."""
    who = payload.get("player")
    event = payload.get("event")
    if not isinstance(who, str):
        return  # a malformed frame never corrupts the roster
    if event == "online":
        _ONLINE.add(who)
    elif event == "offline":
        _ONLINE.discard(who)


def reconnect() -> None:
    """(Re)subscribe the roster handler to the bus in force.

    Called at import and after any set_bus swap."""
    active = bus.get_bus()
    active.unsubscribe(_TOPIC, _on_event)  # idempotent: no-op if not already subscribed
    active.subscribe(_TOPIC, _on_event)


def mark_online(player: str) -> None:
    """Announce a hero has entered. Named players only -- the roster is of real characters."""
    bus.get_bus().publish(_TOPIC, {"event": "online", "player": player})


def mark_offline(player: str) -> None:
    """Announce a hero has left."""
    bus.get_bus().publish(_TOPIC, {"event": "offline", "player": player})


def online() -> set[str]:
    """A snapshot of who is online across every process feeding the bus."""
    return set(_ONLINE)


def count() -> int:
    """How many heroes are online -- the concurrent-player metric the bus makes possible."""
    return len(_ONLINE)


def _reset() -> None:
    """Clear the roster and re-subscribe to the default bus (tests, so a run never leaks onward)."""
    _ONLINE.clear()
    reconnect()


reconnect()  # subscribe to the default in-process bus at import
