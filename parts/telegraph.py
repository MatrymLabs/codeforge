"""CARD: telegraph -- the game adapter for the stream framer: a dispatch that arrives in pieces.

A courier delivers a telegraph one burst at a time; the `telegraph` verb frames those bursts into
whole lines with a `StreamFramer`, so a message split awkwardly across bursts still reads as clean
lines. The SAME framer core reads a byte-stream of records in a practical app (parts/record_stream).
"""

from __future__ import annotations

from parts.session import Session
from parts.shelf.stream_framer import StreamFramer

# A dispatch delivered in awkward bursts: line breaks fall mid-burst, and the last line arrives
# with no trailing newline, so the framer's partial tail must be flushed to read it.
_BURSTS = [
    b"THE FORGE IS LIT.\nA courier ri",
    b"des from the north.\nBring wo",
    b"rd to the Keep.",
]


def telegraph(session: Session, arg: str = "") -> str:
    """The `telegraph` verb: reassemble a bursty dispatch into clean lines."""
    framer = StreamFramer()
    lines: list[str] = ["A telegraph arrives, burst by burst:"]
    for burst in _BURSTS:
        lines.extend(f"  {line}" for line in framer.feed(burst))
    tail = framer.flush()
    if tail:
        lines.append(f"  {tail}")
    return "\n".join(lines)
