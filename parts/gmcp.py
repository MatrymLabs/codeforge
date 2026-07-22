"""CARD: gmcp -- structured out-of-band state frames for GMCP-aware clients.

GMCP (Generic MUD Communication Protocol) rides Telnet subnegotiation: `IAC SB GMCP
<package> <json> IAC SE`. It lets a capable client read state as data (a health bar, a
minimap) instead of scraping the text projection. This card is PURE: it builds frames and
reports and reads negotiation replies; the gateway owns the socket and decides when to send.

Two laws hold here. State is canonical and text is a projection (architecture law 1), so a
GMCP report is just another read-only projection of the same `Session` the renderer reads --
never a second source of truth. And derive-don't-store (law 3): vitals come through
`sheet_from_session`, the same aggregator the score sheet uses, so a client never sees a
number the game itself would not compute.
"""

from __future__ import annotations

import json

from parts.character_view import sheet_from_session
from parts.session import Session
from parts.shelf.telnet_codec import IAC, SB, SE, escape_iac, read_negotiation
from parts.world import WORLD

# GMCP is Telnet option 201 (0xC9). The IAC/SB/SE bytes and the escape/negotiation codec come from
# parts.shelf.telnet_codec, the one home for the Telnet wire; this card only knows the GMCP option
# and how to shape a GMCP payload. `escape_iac` is re-exported so consumers keep importing it here.
GMCP_OPT = 201

__all__ = ["GMCP_OPT", "enables_gmcp", "escape_iac", "gmcp_frame", "room_report", "vitals_report"]


def gmcp_frame(package: str, data: object) -> bytes:
    """Frame one GMCP message as raw bytes ready to write to a socket.

    `IAC SB GMCP <package> <compact-json> IAC SE`. `data` is JSON-encoded; pass `None` for a
    body-less package (the space and payload are omitted).
    """
    if not package:
        raise ValueError("GMCP package name must not be empty")
    body = package if data is None else f"{package} {json.dumps(data, separators=(',', ':'))}"
    return bytes([IAC, SB, GMCP_OPT]) + escape_iac(body.encode("utf-8")) + bytes([IAC, SE])


def enables_gmcp(data: bytes) -> bool | None:
    """Read a client's negotiation reply for GMCP support (the GMCP-specific read_negotiation).

    True  -> the client enabled GMCP (`IAC DO GMCP` or `IAC WILL GMCP`): safe to push frames.
    False -> the client refused (`IAC DONT GMCP` or `IAC WONT GMCP`): stop pushing.
    None  -> no GMCP negotiation in this chunk: leave the current decision unchanged.

    A raw `nc` never sends any of these, so it never flips to True: it stays a plain-text client
    and receives no binary GMCP noise.
    """
    return read_negotiation(data, GMCP_OPT)


def vitals_report(session: Session) -> dict[str, int] | None:
    """A Char.Vitals payload from live state, or None before the player has a calling.

    Derived through `sheet_from_session` (the score sheet's own aggregator), so these numbers
    always match what the game would render. `nextlevel` is -1 at the level cap (no next
    threshold), which a client reads as "maxed" without a null.
    """
    sheet = sheet_from_session(session)
    if sheet is None:
        return None
    hp_cur, hp_max = sheet.hp
    mp_cur, mp_max = sheet.mp if sheet.mp is not None else (0, 0)  # a job with no MP reads as 0/0
    return {
        "hp": hp_cur,
        "maxhp": hp_max,
        "mp": mp_cur,
        "maxmp": mp_max,
        "level": sheet.player_level,
        "xp": sheet.current_xp,
        "nextlevel": sheet.next_level_xp if sheet.next_level_xp is not None else -1,
    }


def room_report(session: Session) -> dict[str, object]:
    """A Room.Info payload for the session's current location, from world data.

    `num` is the room's frozen label (the dict key); `name` and `exits` come straight from the
    seeded room. An unknown location renders honestly rather than raising: the player is
    somewhere the world does not describe, and the client should see that, not a crash.
    """
    room = WORLD.get(session.location)
    if room is None:
        return {"num": session.location, "name": "(nowhere)", "exits": {}}
    return {
        "num": session.location,
        "name": room["name"],
        "exits": dict(room["exits"]),
    }
