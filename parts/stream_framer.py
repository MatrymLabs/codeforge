"""CARD: stream_framer -- frame a byte stream into complete messages, buffering partials.

Bytes arrive from a socket or a pipe in arbitrary chunks: a message can span two reads, and the
last chunk often ends mid-message. This part accumulates bytes and emits only COMPLETE messages,
holding a partial until the rest arrives. It exists because the naive `chunk.endswith(delimiter)`
(and its cousin `endswith(b"")`, always True) silently drops or splits messages: framing needs its
own buffer.

Harvested from codeforge-client's line framer (proven there first), reimplemented here as a general,
delimiter-configurable part. One core, two adapters: an in-world `telegraph` that arrives in pieces
(parts/telegraph) and a byte-stream record reader for a practical app (parts/record_stream).

Provenance: original implementation of a standard framing pattern. No code copied.
"""

from __future__ import annotations


class StreamFramer:
    """Accumulate bytes and emit complete, delimiter-terminated messages; hold a partial tail."""

    def __init__(self, delimiter: bytes = b"\n", *, encoding: str = "utf-8", strip: bytes = b"\r"):
        if not delimiter:
            raise ValueError("delimiter must be a non-empty byte string")
        self._delimiter = delimiter
        self._encoding = encoding
        self._strip = strip
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> list[str]:
        """Add `chunk`; return every complete message it finished (delimiter removed, decoded)."""
        self._buffer.extend(chunk)
        messages: list[str] = []
        while True:
            index = self._buffer.find(self._delimiter)
            if index == -1:
                break
            raw = bytes(self._buffer[:index])
            del self._buffer[: index + len(self._delimiter)]
            messages.append(raw.rstrip(self._strip).decode(self._encoding, errors="replace"))
        return messages

    def flush(self) -> str | None:
        """Return any buffered partial message (e.g. a prompt with no delimiter), then clear it."""
        if not self._buffer:
            return None
        raw = bytes(self._buffer)
        self._buffer.clear()
        return raw.rstrip(self._strip).decode(self._encoding, errors="replace")
