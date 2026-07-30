"""CARD: events -- world happenings broadcast to bystanders.

When a player acts, everyone ELSE in the room should see it:
arrivals, departures, takes, drops, speech. Sessions bind an
ECHO SINK (a callable that delivers text to that player); announce()
fans an event out to every echo sink in a room, excluding the actor.

This is the embryo of the canonical event bus: today the payload
is rendered text; later it becomes validated event frames that
sinks render per-recipient.

Two delivery scopes, two homes (Phase 4). ROOM-scoped delivery (announce,
announce_frame) reads the local SESSIONS map -- room occupancy is this
process's world state, so it stays local until shared world state exists
(Phase 5). MEMBERSHIP-scoped delivery (announce_to a cohort, broadcast to
everyone, push_gmcp to a set) is process-agnostic -- a party or guild can
span gateways -- so it PUBLISHES onto the message bus. In one process the
in-process bus delivers synchronously to this process's own subscriber, so
behaviour is identical; once a broker is injected the same publish fans out
to every process, and each delivers to the members it hosts.
"""

from collections.abc import Callable, Iterable
from typing import Any

from parts.world import bus
from parts.world.frames import Frame
from parts.world.session import SESSIONS

EchoSink = Callable[[str], None]

_ECHO_SINKS: dict[str, EchoSink] = {}

# The bus topics the membership-scoped channels ride. One subscriber per process per topic (wired
# below) delivers a published message to the sinks THIS process hosts.
_ECHO_TOPIC = "delivery:echo"
_GMCP_TOPIC = "delivery:gmcp"

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


def announce_frame(room: str, frame: Frame, exclude: str = "") -> None:
    """Deliver a typed Frame to every seated player in a room except the actor,
    rendering it PER RECIPIENT. The typed successor to announce(): the payload is a
    structured Frame, and each sink receives text the frame projects for its own
    viewer, instead of one line pre-rendered for the whole room."""
    # Snapshot: _deliver may prune a dead sink mid-loop (mutates _ECHO_SINKS).
    for player_id, session in list(SESSIONS.items()):
        if player_id == exclude or session.location != room:
            continue
        sink = _ECHO_SINKS.get(player_id)
        if sink is not None:
            _deliver(player_id, sink, frame.render_for(player_id))


def announce_to(player_ids: Iterable[str], text: str, exclude: str = "") -> None:
    """Deliver text to a specific SET of players (a party, a guild, any cohort), not a room.

    The complement to announce(): where announce() is scoped by location, this is scoped by an
    explicit membership, so it rides the bus and reaches members on any process. An id with no bound
    sink (an offline member, or one hosted elsewhere with no broker yet) is simply skipped, so a
    cohort message never fails because someone logged out."""
    bus.get_bus().publish(
        _ECHO_TOPIC, {"targets": list(player_ids), "text": text, "exclude": exclude}
    )


def broadcast(text: str) -> None:
    """Deliver text to every sink in the world, no exclusions -- across every process on the bus."""
    bus.get_bus().publish(_ECHO_TOPIC, {"targets": None, "text": text, "exclude": ""})


def _on_echo(payload: dict[str, Any]) -> None:
    """Deliver a published echo message to the sinks THIS process hosts. targets=None means broadcast
    to every local sink; a list means only those ids. The one place membership echo actually lands."""
    text = payload.get("text")
    if not isinstance(text, str):
        return
    targets = payload.get("targets")
    exclude = payload.get("exclude", "")
    if targets is None:  # broadcast: every sink this process holds
        for held_id, held_sink in list(_ECHO_SINKS.items()):
            _deliver(held_id, held_sink, text)
        return
    for player_id in targets:
        if player_id == exclude:
            continue
        sink = _ECHO_SINKS.get(player_id)
        if sink is not None:
            _deliver(player_id, sink, text)


# --- the GMCP push channel: structured frames to a set of players -----------------------------
# The typed sibling of the echo channel. Where an EchoSink carries a line of text, a GmcpSink takes
# a (package, data) frame, so a social event (a party changing, a guild message) can PUSH structured
# state to the affected players the instant it happens, instead of waiting for each one's next tick.
# The gateway binds a connection's _send_gmcp here; a plain-text client's sink is a harmless no-op.
GmcpSink = Callable[[str, object], None]

_GMCP_SINKS: dict[str, GmcpSink] = {}


def bind_gmcp(player_id: str, sink: GmcpSink) -> None:
    """Attach a GMCP frame channel for one player (alongside their echo channel)."""
    _GMCP_SINKS[player_id] = sink


def unbind_gmcp(player_id: str) -> None:
    _GMCP_SINKS.pop(player_id, None)


def rename_gmcp(old_id: str, new_id: str) -> None:
    """Move a player's GMCP channel to their new name (login rename), mirroring rename_echo."""
    sink = _GMCP_SINKS.pop(old_id, None)
    if sink is not None:
        _GMCP_SINKS[new_id] = sink


def push_gmcp(player_ids: Iterable[str], package: str, data: object, exclude: str = "") -> None:
    """Push a GMCP frame to a specific SET of players (a party, a guild) -- the typed complement to
    announce_to. Rides the bus like announce_to, so members on any process receive it. A player with
    no GMCP sink (plain-text client, or offline) is simply skipped, and a sink that raises is pruned,
    so one dead client never crashes another's command. (A broker requires JSON-serialisable data,
    which GMCP frames already are.)"""
    bus.get_bus().publish(
        _GMCP_TOPIC,
        {"targets": list(player_ids), "package": package, "data": data, "exclude": exclude},
    )


def _on_gmcp(payload: dict[str, Any]) -> None:
    """Deliver a published GMCP frame to the sinks THIS process hosts."""
    package = payload.get("package")
    if not isinstance(package, str):
        return
    data = payload.get("data")
    exclude = payload.get("exclude", "")
    for player_id in payload.get("targets") or []:
        if player_id == exclude:
            continue
        sink = _GMCP_SINKS.get(player_id)
        if sink is not None:
            try:
                sink(package, data)
            except OSError:
                unbind_gmcp(player_id)


def rewire_delivery() -> None:
    """(Re)subscribe this process's echo + GMCP delivery handlers to the bus in force. Registered as
    a bus rewire hook and run at import, so a bus swap (a broker replacing the default) never leaves
    delivery attached to a dead bus."""
    active = bus.get_bus()
    for topic, handler in ((_ECHO_TOPIC, _on_echo), (_GMCP_TOPIC, _on_gmcp)):
        active.unsubscribe(topic, handler)  # idempotent
        active.subscribe(topic, handler)


bus.on_rewire(rewire_delivery)
rewire_delivery()  # attach to the default in-process bus at import


def push_channel(
    player_ids: Iterable[str], channel: str, sender: str, text: str, exclude: str = ""
) -> None:
    """Push a Comm.Channel frame -- one chat line on a named channel (party/guild/world) -- to a set
    of players. The structured twin of the chat text, so a client can route chat into per-channel
    panes instead of one scrolling buffer. The one place the frame's shape is built, so it never
    drifts between the three channels."""
    push_gmcp(
        player_ids,
        "Comm.Channel",
        {"channel": channel, "from": sender, "text": text},
        exclude=exclude,
    )
