"""CARD: telnet_codec -- the Telnet byte codec: command bytes, IAC escaping, negotiation reading.

Pure and socket-free. The RFC 854/855 command bytes (IAC, SB, SE, WILL/WONT/DO/DONT) live here
ONCE so the two sides of the wire share one source of truth: the gateway decodes inbound bytes
(`strip_iac`) and reads a client's option replies (`read_negotiation`); the GMCP card encodes
outbound frames (`escape_iac`). Before this part, both re-declared the same constants and split the
codec by direction (the gmcp card even documented the duplication as deliberate). Neither side
imports the socket layer to speak Telnet.
"""

from __future__ import annotations

# RFC 854 command bytes: IAC introduces a command; SB..SE brackets a subnegotiation body.
IAC = 255
SE = 240
SB = 250
# RFC 855 option-negotiation verbs.
WILL = 251
WONT = 252
DO = 253
DONT = 254


def escape_iac(payload: bytes) -> bytes:
    """Double every IAC (255) byte in a subnegotiation body.

    Inside `IAC SB ... IAC SE`, a literal 255 must be sent as 255 255 or the client reads it as
    the start of a command and the frame desyncs. ASCII is safe, but a UTF-8 payload can carry a
    0xFF byte, so escape unconditionally rather than assume.
    """
    return payload.replace(bytes([IAC]), bytes([IAC, IAC]))


def strip_iac(data: bytes) -> bytes:
    """Remove IAC command sequences from raw input. Clients answer our
    negotiation with their own IAC bytes -- those must never end up
    inside a password."""
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == IAC and i + 1 < len(data):
            command = data[i + 1]
            if command == IAC:  # escaped literal 255
                out.append(IAC)
                i += 2
            elif command == SB:
                # Subnegotiation is variable length: skip the whole IAC SB ...body... IAC SE
                # frame, or the body bytes (window size, terminal type, GMCP...) leak into the
                # command line -- and, mid-password, corrupt the secret. A client sending it glued
                # to input (Mudlet et al.) once broke logins. Unterminated frame: drop to the end.
                j = i + 2
                while j + 1 < len(data) and not (data[j] == IAC and data[j + 1] == SE):
                    j += 1
                i = j + 2 if j + 1 < len(data) else len(data)
            elif command in (WILL, WONT, DO, DONT):
                i += 3  # three-byte sequence: IAC <verb> <option>
            else:
                i += 2
        else:
            out.append(data[i])
            i += 1
    return bytes(out)


def read_negotiation(data: bytes, option: int) -> bool | None:
    """Read a client's WILL/DO (enable) or WONT/DONT (disable) reply for one Telnet `option`.

    True  -> the client enabled the option (`IAC DO <opt>` or `IAC WILL <opt>`).
    False -> the client refused it (`IAC DONT <opt>` or `IAC WONT <opt>`).
    None  -> no negotiation for `option` in this chunk: leave the current decision unchanged.

    The last matching verb in the chunk wins. A truncated sequence (the option byte never arrived)
    reads as None rather than raising, so a split-across-reads negotiation is safe.
    """
    verdict: bool | None = None
    for i in range(len(data) - 2):
        if data[i] == IAC and data[i + 2] == option:
            verb = data[i + 1]
            if verb in (DO, WILL):
                verdict = True  # a later WONT/DONT in the same chunk can still override
            elif verb in (DONT, WONT):
                verdict = False
    return verdict
