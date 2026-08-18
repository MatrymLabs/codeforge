"""RF-001 is a parser that eats untrusted binary. These are its hostile-input fixtures.

The engineering standard mandates fuzzing on parser and binary-decoder boundaries. RF-001
qualifies twice over: an iNES header parser and a CHR tile decoder, both reading bytes supplied
by whoever hands the tool a file. A cartridge image is not a trusted input just because the
person running the tool owns the cartridge.

A full fuzz harness is deferred until the slice ships. This is the minimum viable version the
Master Checklist names, and it is three fixtures rather than a rig:

    truncated        a file that stops in the middle of a structure it promised
    garbage bytes    a file that was never a cartridge at all
    oversized header a header that CLAIMS more ROM than the file contains

The bar is the same for all three: FAIL CLEANLY. A named exception or a refusing verdict is a
pass. A traceback from an unexpected exception type, a silent truncation, a hang, or a read past
the end of the buffer is a failure. Refusing is a feature; guessing is the defect.

Every fixture is synthetic and built in memory. No cartridge image is read from disk or committed,
which the RetroForge legal block treats as a never-automate item.
"""

from __future__ import annotations

import pytest

from kernel.retroforge.artifact import RomArtifact
from kernel.retroforge.binary import ByteSource
from kernel.retroforge.platforms.planar_2bpp import (
    CHR_ROM_UNIT_BYTES,
    HEADER_SIZE,
    PRG_ROM_UNIT_BYTES,
    HeaderedCartridgeModule,
    InvalidCartridgeHeader,
    Planar2BppTileCodec,
)

MAGIC = b"NES\x1a"


def _header(prg_units: int, chr_units: int) -> bytes:
    return MAGIC + bytes([prg_units, chr_units]) + bytes(10)


def _honest_rom(prg_units: int = 1, chr_units: int = 1) -> bytes:
    """A cartridge whose header tells the truth about its own size."""
    return (
        _header(prg_units, chr_units)
        + bytes(prg_units * PRG_ROM_UNIT_BYTES)
        + bytes(chr_units * CHR_ROM_UNIT_BYTES)
    )


# --- fixture 1: truncated ---------------------------------------------------------------------


@pytest.mark.parametrize("keep", [0, 1, 4, HEADER_SIZE - 1])
def test_a_file_truncated_inside_its_header_is_refused(keep: int) -> None:
    """A header is 16 bytes. Anything shorter cannot be parsed, and must say so."""
    source = ByteSource(_honest_rom()[:keep])
    with pytest.raises(InvalidCartridgeHeader):
        HeaderedCartridgeModule().parse_metadata(source)


def test_a_file_truncated_inside_its_chr_data_refuses_rather_than_truncating() -> None:
    """The header promises a full CHR bank; the file ends early.

    The refusal must come from the read, not from a short tile quietly decoded as if the missing
    bytes were zeroes. A decoder that pads is a decoder that invents pixels.
    """
    full = _honest_rom()
    source = ByteSource(full[: len(full) - 8])  # half a tile short
    module = HeaderedCartridgeModule()
    offset = module.chr_rom_offset(source)

    last_tile = len(full) - HEADER_SIZE - PRG_ROM_UNIT_BYTES - 16
    with pytest.raises((IndexError, ValueError)):
        Planar2BppTileCodec().decode_tile(source, offset + last_tile)


# --- fixture 2: garbage bytes -----------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        b"\x00" * 64,
        b"\xff" * 64,
        b"SEGA" + bytes(60),
        bytes(range(256)),
        b"%PDF-1.7\n" + bytes(55),
    ],
    ids=["zeroes", "ones", "wrong-magic", "counting-bytes", "a-pdf"],
)
def test_bytes_that_were_never_a_cartridge_are_refused(payload: bytes) -> None:
    """Anything without the format signature is refused, whatever else it happens to be."""
    source = ByteSource(payload)
    module = HeaderedCartridgeModule()

    assert module.detect(source) <= 0
    with pytest.raises(InvalidCartridgeHeader):
        module.parse_metadata(source)


def test_a_garbage_file_never_reports_a_confident_detection() -> None:
    """detect() is the first gate the viewer consults; a false positive there defeats the rest."""
    module = HeaderedCartridgeModule()
    assert module.detect(ByteSource(bytes(range(256)) * 4)) <= 0
    assert module.detect(ByteSource(_honest_rom())) > 0


# --- fixture 3: oversized header --------------------------------------------------------------


def test_a_header_claiming_more_prg_than_the_file_holds_does_not_read_out_of_bounds() -> None:
    """The header is attacker-controlled arithmetic, and this is the case that matters.

    `chr_rom_offset` is computed as HEADER_SIZE + prg_units * 16KB, straight from a byte in the
    header. A file can claim 255 PRG banks (about 4 MB) while being 64 bytes long. The offset that
    produces points far past the end of the buffer.

    Nothing here requires the parser to guess the real size. It requires that reading at the
    resulting offset REFUSES instead of wandering off the end of the buffer.
    """
    liar = _header(255, 255) + bytes(48)
    source = ByteSource(liar)
    module = HeaderedCartridgeModule()

    offset = module.chr_rom_offset(source)
    assert offset > len(source), "the fixture failed to produce an out-of-range offset"

    with pytest.raises((IndexError, ValueError)):
        Planar2BppTileCodec().decode_tile(source, offset)


def test_an_oversized_header_is_still_described_without_crashing() -> None:
    """Metadata may report what the header CLAIMS, but it must not crash producing it."""
    metadata = HeaderedCartridgeModule().parse_metadata(ByteSource(_header(255, 255) + bytes(48)))

    assert metadata["prg_rom_size"] == 255 * PRG_ROM_UNIT_BYTES
    assert metadata["chr_rom_size"] == 255 * CHR_ROM_UNIT_BYTES


def test_extracting_tiles_from_a_lying_header_fails_cleanly() -> None:
    """The full extraction path, not just one tile: the loop must not run off the end either."""
    data = _header(0, 255) + bytes(32)
    artifact = RomArtifact.from_bytes(data, source_path="<hostile>")
    module = HeaderedCartridgeModule()

    try:
        tiles, _manifest = module.extract_chr_tiles(artifact)
    except (IndexError, ValueError):
        return  # refusing is a pass
    assert len(tiles) * 16 <= len(data), (
        "extraction reported tiles that cannot fit in the file; the header was believed over "
        f"the bytes ({len(tiles)} tiles from {len(data)} bytes)"
    )


def test_a_chr_unit_count_of_zero_is_not_confused_with_a_lie() -> None:
    """CHR RAM is a legitimate cartridge shape, not hostile input, and must stay distinguishable."""
    source = ByteSource(_honest_rom(prg_units=1, chr_units=0))
    metadata = HeaderedCartridgeModule().parse_metadata(source)
    assert metadata["chr_rom_size"] == 0
    assert CHR_ROM_UNIT_BYTES > 0
