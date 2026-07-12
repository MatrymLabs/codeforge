"""CARD: record_stream -- practical adapter for the stream framer: read records from a byte stream.

The reverse of parts/telegraph: the SAME `StreamFramer` core reads a stream of delimited records off
a socket or a pipe, feeding chunks as they arrive and collecting complete records. Its cousins are
log tailers, protocol clients, and any reader that must not split a record across two reads.
"""

from __future__ import annotations

from collections.abc import Iterable

from parts.stream_framer import StreamFramer


class RecordStream:
    """Collect complete, delimiter-terminated records from a byte stream fed chunk by chunk."""

    def __init__(self, delimiter: bytes = b"\n") -> None:
        self._framer = StreamFramer(delimiter=delimiter)
        self._records: list[str] = []

    def feed(self, chunk: bytes) -> list[str]:
        """Feed one chunk; return (and remember) the records it completed."""
        new = self._framer.feed(chunk)
        self._records.extend(new)
        return new

    def consume(self, chunks: Iterable[bytes]) -> list[str]:
        """Feed many chunks in order; return every record completed across them."""
        completed: list[str] = []
        for chunk in chunks:
            completed.extend(self.feed(chunk))
        return completed

    def close(self) -> str | None:
        """Flush any trailing partial record (a stream that ended without a final delimiter)."""
        tail = self._framer.flush()
        if tail is not None:
            self._records.append(tail)
        return tail

    @property
    def records(self) -> list[str]:
        """Every record collected so far."""
        return list(self._records)
