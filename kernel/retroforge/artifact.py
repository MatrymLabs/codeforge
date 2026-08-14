"""CARD: retroforge.artifact -- a loaded ROM as immutable bytes plus derived, traceable metadata.

An artifact is the unit every RetroForge answer is traceable back to. The checksum is not a
nicety: an extraction manifest that cannot name the exact bytes it came from is a pile of tiles
with a story attached, and the whole point of the manifest is that the story is checkable.

Platform is DERIVED, never asserted by the caller. A caller who can declare the platform can
declare it wrong, and a wrong platform silently decodes with the wrong codec.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from kernel.retroforge.binary import ByteSource


@dataclass(frozen=True)
class RomArtifact:
    """One loaded ROM. Immutable, checksummed, and never written back."""

    source_path: str
    source: ByteSource
    platform: str = "unknown"
    fmt: str = "unknown"
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.source)

    @property
    def checksum(self) -> str:
        """sha256 of the source bytes. Every extracted asset cites this."""
        return hashlib.sha256(self.source.data).hexdigest()

    @classmethod
    def from_bytes(cls, data: bytes, source_path: str = "<memory>") -> RomArtifact:
        return cls(source_path=source_path, source=ByteSource(data, name=source_path))
