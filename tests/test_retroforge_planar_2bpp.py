"""Proofs for cartridge-header metadata and the cartridge's planar CHR tile format."""

from __future__ import annotations

import pytest

from kernel.retroforge.artifact import RomArtifact
from kernel.retroforge.binary import ByteSource, OutOfRange
from kernel.retroforge.codec import RomPlatformModule
from kernel.retroforge.platforms.planar_2bpp import (
    HeaderedCartridgeModule,
    InvalidCartridgeHeader,
    Planar2BppTileCodec,
)


def _ines_rom(prg_pages: int = 0, chr_pages: int = 0, chr_data: bytes = b"") -> bytes:
    header = b"NES\x1a" + bytes([prg_pages, chr_pages]) + bytes(10)
    return header + bytes(prg_pages * 16 * 1024) + chr_data


def test_low_plane_only_produces_pixel_value_one() -> None:
    tile = Planar2BppTileCodec().decode_tile(ByteSource(b"\x80" + bytes(15)), 0)
    assert tile[0] == (1, 0, 0, 0, 0, 0, 0, 0)


def test_high_plane_only_produces_pixel_value_two() -> None:
    tile = Planar2BppTileCodec().decode_tile(ByteSource(bytes(8) + b"\x80" + bytes(7)), 0)
    assert tile[0] == (2, 0, 0, 0, 0, 0, 0, 0)


def test_both_planes_set_produce_pixel_value_three() -> None:
    tile = Planar2BppTileCodec().decode_tile(ByteSource(b"\x80" + bytes(7) + b"\x80" + bytes(7)), 0)
    assert tile[0] == (3, 0, 0, 0, 0, 0, 0, 0)


def test_neither_plane_set_produces_pixel_value_zero() -> None:
    tile = Planar2BppTileCodec().decode_tile(ByteSource(bytes(16)), 0)
    assert tile == ((0, 0, 0, 0, 0, 0, 0, 0),) * 8


def test_a_known_tile_decodes_to_the_literal_expected_grid() -> None:
    tile = Planar2BppTileCodec().decode_tile(
        ByteSource(
            bytes(
                [
                    0x80,
                    0x40,
                    0x20,
                    0x10,
                    0x08,
                    0x04,
                    0x02,
                    0x01,
                    0x01,
                    0x02,
                    0x04,
                    0x08,
                    0x10,
                    0x20,
                    0x40,
                    0x80,
                ]
            )
        ),
        0,
    )
    assert tile == (
        (1, 0, 0, 0, 0, 0, 0, 2),
        (0, 1, 0, 0, 0, 0, 2, 0),
        (0, 0, 1, 0, 0, 2, 0, 0),
        (0, 0, 0, 1, 2, 0, 0, 0),
        (0, 0, 0, 2, 1, 0, 0, 0),
        (0, 0, 2, 0, 0, 1, 0, 0),
        (0, 2, 0, 0, 0, 0, 1, 0),
        (2, 0, 0, 0, 0, 0, 0, 1),
    )


def test_tile_bits_are_most_significant_bit_first() -> None:
    tile = Planar2BppTileCodec().decode_tile(ByteSource(b"\x80" + bytes(15)), 0)
    assert tile[0][0] == 1
    assert tile[0][7] == 0


def test_a_tile_past_the_source_end_raises_out_of_range() -> None:
    with pytest.raises(OutOfRange):
        Planar2BppTileCodec().decode_tile(ByteSource(bytes(15)), 0)


def test_chr_offset_and_extraction_manifest_are_derived_from_the_cartridge_header() -> None:
    chr_data = b"\x80" + bytes(15) + bytes(8 * 1024 - 16)
    source = ByteSource(_ines_rom(prg_pages=1, chr_pages=1, chr_data=chr_data))
    assert HeaderedCartridgeModule().chr_rom_offset(source) == 16 + 16 * 1024

    artifact = RomArtifact.from_bytes(source.data, source_path="fixture.nes")
    tiles, manifest = HeaderedCartridgeModule().extract_chr_tiles(artifact)
    assert tiles[0][0] == (1, 0, 0, 0, 0, 0, 0, 0)
    assert manifest.assets[0].offset == 16 + 16 * 1024
    assert manifest.assets[0].source_checksum == artifact.checksum


def test_a_non_cartridge_header_is_refused() -> None:
    with pytest.raises(InvalidCartridgeHeader, match="cartridge format signature"):
        HeaderedCartridgeModule().parse_metadata(ByteSource(b"NOPE" + bytes(12)))


def test_chr_ram_returns_no_tiles_and_a_manifest_warning() -> None:
    artifact = RomArtifact.from_bytes(_ines_rom(), source_path="chr-ram.nes")
    tiles, manifest = HeaderedCartridgeModule().extract_chr_tiles(artifact)
    assert tiles == ()
    assert manifest.assets == []
    assert manifest.warnings == [
        "the header declares character RAM, so there are no ROM tiles to extract"
    ]


def test_platform_module_satisfies_the_locked_protocol() -> None:
    assert isinstance(HeaderedCartridgeModule(), RomPlatformModule)
