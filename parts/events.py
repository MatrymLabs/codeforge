"""CARD: events -- world happenings broadcast to bystanders.

When a player acts, everyone ELSE in the room should see it:
arrivals, departures, takes, drops, speech. Sessions register a
SINK (a callable that delivers text to that player); announce()
fans an event out to every sink in a room, excluding the actor.

This is the embryo of the canonical event bus: today the payload
is rendered text; later it becomes validated event frames that
sinks render per-recipient.
"""

from collections.abc import Callable

from parts.session import SESSIONS

Sink = Callable[[str], None]

_SINKS: dict[str, Sink] = {}


def register(player_id: str, sink: Sink) -> None:
    """Attach a delivery channel for one player."""
    _SINKS[player_id] = sink


def unregister(player_id: str) -> None:
    _SINKS.pop(player_id, None)


def rename(old_id: str, new_id: str) -> None:
    """Move a player's delivery channel to their new name."""
    sink = _SINKS.pop(old_id, None)
    if sink is not None:
        _SINKS[new_id] = sink


def announce(room: str, text: str, exclude: str = "") -> None:
    """Deliver text to every seated player in a room, except the actor."""
    for player_id, session in SESSIONS.items():
        if player_id == exclude or session.location != room:
            continue
        sink = _SINKS.get(player_id)
        if sink is not None:
            sink(text)
