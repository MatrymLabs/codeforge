"""CARD: retroforge.binary -- a read-only window on ROM bytes that refuses to read past its end.

Every RetroForge codec reads through this and nothing else. The reason is the safety model: RF-001
is read-only, and the cheapest way to keep a promise about not writing is to hand the decoders a
type that cannot write. `ByteSource` exposes no mutation, so "no ROM bytes were modified" is a
property of the type rather than a habit of the caller.

The second job is bounds. A tile decoder computes an offset from a header field, and a header field
is attacker-controlled in the only sense that matters here: it comes from a file. An out-of-range
read must be a named refusal, never a short read that silently decodes garbage into a tile that
looks plausible.
"""

from __future__ import annotations

from dataclasses import dataclass


class OutOfRange(ValueError):  # noqa: N818
    """A read ran past the end of the source. Raised, never truncated.

    A short read is the dangerous failure: sixteen bytes requested, nine returned, and the decoder
    renders a tile that looks like data. This refuses instead.
    """


@dataclass(frozen=True)
class ByteSource:
    """An immutable view over ROM bytes, addressed from a fixed origin."""

    data: bytes
    name: str = "<memory>"

    def __len__(self) -> int:
        return len(self.data)

    def read(self, offset: int, count: int) -> bytes:
        """`count` bytes at `offset`, or OutOfRange. Never fewer than asked for."""
        if offset < 0 or count < 0:
            raise OutOfRange(f"{self.name}: negative read, offset={offset} count={count}")
        end = offset + count
        if end > len(self.data):
            raise OutOfRange(
                f"{self.name}: read of {count} byte(s) at offset {offset} ends at {end}, "
                f"past the {len(self.data)}-byte source"
            )
        return self.data[offset:end]

    def window(self, offset: int, count: int) -> ByteSource:
        """A narrowed source over the same bytes, bounds-checked at the moment it is taken."""
        return ByteSource(self.read(offset, count), name=f"{self.name}[{offset}:{offset + count}]")
