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
from parts.world import WORLD

# GMCP is Telnet option 201 (0xC9). IAC/SB/SE mirror the gateway's negotiation constants; they
# live here too so this card frames a subnegotiation without importing the socket layer.
GMCP_OPT = 201
_IAC, _SB, _SE = 255, 250, 240


def escape_iac(payload: bytes) -> bytes:
    """Double every IAC (255) byte in a subnegotiation body.

    Inside `IAC SB ... IAC SE`, a literal 255 must be sent as 255 255 or the client reads it as
    the start of a command and the frame desyncs. JSON is ASCII-safe, but a UTF-8 payload can
    carry a 0xFF byte, so escape unconditionally rather than assume.
    """
    return payload.replace(bytes([_IAC]), bytes([_IAC, _IAC]))


def gmcp_frame(package: str, data: object) -> bytes:
    """Frame one GMCP message as raw bytes ready to write to a socket.

    `IAC SB GMCP <package> <compact-json> IAC SE`. `data` is JSON-encoded; pass `None` for a
    body-less package (the space and payload are omitted).
    """
    if not package:
        raise ValueError("GMCP package name must not be empty")
    body = package if data is None else f"{package} {json.dumps(data, separators=(',', ':'))}"
    return bytes([_IAC, _SB, GMCP_OPT]) + escape_iac(body.encode("utf-8")) + bytes([_IAC, _SE])


def enables_gmcp(data: bytes) -> bool | None:
    """Read a client's negotiation reply for GMCP support.

    True  -> the client enabled GMCP (`IAC DO GMCP` or `IAC WILL GMCP`): safe to push frames.
    False -> the client refused (`IAC DONT GMCP` or `IAC WONT GMCP`): stop pushing.
    None  -> no GMCP negotiation in this chunk: leave the current decision unchanged.

    A raw `nc` never sends any of these, so it never flips to True: it stays a plain-text client
    and receives no binary GMCP noise. The last GMCP verb in the chunk wins.
    """
    _WILL, _WONT, _DO, _DONT = 251, 252, 253, 254
    verdict: bool | None = None
    for i in range(len(data) - 2):
        if data[i] == _IAC and data[i + 2] == GMCP_OPT:
            verb = data[i + 1]
            if verb in (_DO, _WILL):
                verdict = True  # a later WONT/DONT in the same chunk can still override
            elif verb in (_DONT, _WONT):
                verdict = False
    return verdict


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
