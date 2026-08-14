"""Test twin for kernel/retroforge/artifact.py.

Acceptance: an artifact reports its size, a stable sha256 of exactly its bytes, and never exposes
a write path.

Refusal: two different ROMs must not share a checksum, because every extracted asset cites it and
a colliding or careless checksum makes the whole manifest unfalsifiable.
"""

from __future__ import annotations

import hashlib

import pytest

from kernel.retroforge.artifact import RomArtifact


def test_an_artifact_reports_its_size_and_checksum() -> None:
    art = RomArtifact.from_bytes(b"NES\x1a" + bytes(28), source_path="fixture.nes")
    assert art.size == 32
    assert art.checksum == hashlib.sha256(b"NES\x1a" + bytes(28)).hexdigest()


def test_the_checksum_covers_exactly_the_source_bytes_and_nothing_else() -> None:
    """Cited by every asset. If it covered metadata too, re-deriving it would be guesswork."""
    data = bytes(range(64))
    assert RomArtifact.from_bytes(data).checksum == hashlib.sha256(data).hexdigest()


def test_two_different_roms_do_not_share_a_checksum() -> None:
    assert (
        RomArtifact.from_bytes(b"\x00" * 16).checksum
        != RomArtifact.from_bytes(b"\x01" * 16).checksum
    )


def test_platform_defaults_to_unknown_rather_than_a_guess() -> None:
    """A caller who can declare the platform can declare it wrong, and a wrong platform decodes
    with the wrong codec. Detection is a platform module's job, not a constructor argument's."""
    assert RomArtifact.from_bytes(b"\x00" * 16).platform == "unknown"


def test_an_artifact_is_frozen() -> None:
    art = RomArtifact.from_bytes(b"\x00" * 16)
    with pytest.raises((AttributeError, TypeError)):
        art.platform = "nes"  # type: ignore[misc]
