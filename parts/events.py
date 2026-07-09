"""CARD: events -- world happenings broadcast to bystanders.

When a player acts, everyone ELSE in the room should see it:
arrivals, departures, takes, drops, speech. Sessions bind an
ECHO SINK (a callable that delivers text to that player); announce()
fans an event out to every echo sink in a room, excluding the actor.

This is the embryo of the canonical event bus: today the payload
is rendered text; later it becomes validated event frames that
sinks render per-recipient.
"""

from collections.abc import Callable

from parts.session import SESSIONS

EchoSink = Callable[[str], None]

_ECHO_SINKS: dict[str, EchoSink] = {}

# The gateway registers its stop function here at boot; the @shutdown
# verb calls it. Dependency inversion: forge never imports the gateway.
SHUTDOWN: dict[str, Callable[[], None] | None] = {"hook": None}


def bind_echo(player_id: str, sink: EchoSink) -> None:
    """Attach a delivery channel for one player."""
    _ECHO_SINKS[player_id] = sink


def unbind_echo(player_id: str) -> None:
    _ECHO_SINKS.pop(player_id, None)


def rename_echo(old_id: str, new_id: str) -> None:
    """Move a player's delivery channel to their new name."""
    sink = _ECHO_SINKS.pop(old_id, None)
    if sink is not None:
        _ECHO_SINKS[new_id] = sink


def _deliver(player_id: str, sink: EchoSink, text: str) -> None:
    """Push text to one sink. A dead channel (dropped client, closed socket)
    must NEVER crash the acting player's command -- one bad client cannot take
    down another. A sink that raises is pruned so it isn't tried again."""
    try:
        sink(text)
    except OSError:
        unbind_echo(player_id)


def announce(room: str, text: str, exclude: str = "") -> None:
    """Deliver text to every seated player in a room, except the actor."""
    # Snapshot: _deliver may prune a dead sink mid-loop (mutates _ECHO_SINKS).
    for player_id, session in list(SESSIONS.items()):
        if player_id == exclude or session.location != room:
            continue
        sink = _ECHO_SINKS.get(player_id)
        if sink is not None:
            _deliver(player_id, sink, text)


def broadcast(text: str) -> None:
    """Deliver text to every sink in the world, no exclusions."""
    for player_id, sink in list(_ECHO_SINKS.items()):
        _deliver(player_id, sink, text)
