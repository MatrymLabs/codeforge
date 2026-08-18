"""A 16-byte-headered cartridge image, and its planar two-bit-per-pixel tile codec.

Named by TECHNIQUE, not by console. Principal Engineer ruling 2026-08-14.

The console name is a brand; `planar 2bpp` is what the format actually IS, and the distinction is
not cosmetic. An era name would have been worse than either: three different 8-bit machines store
tiles three incompatible ways, so a module called `eightbit` holding this one layout would claim a
generality it does not have, and the name would already be taken when the second arrives.

THE FOUR SIGNATURE BYTES BELOW ARE DATA, NOT A NAME. A file either begins with them or it does not;
that is a fact about bytes on disk and renaming it would simply break detection. It lives in a
constant, out of the module name and out of the prose.

Decoded tiles carry palette indices, not colours. This module stays at that binary boundary so a
projection can choose a palette without changing the source interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from kernel.retroforge.artifact import RomArtifact
from kernel.retroforge.binary import ByteSource
from kernel.retroforge.codec import PaletteCodec, Tile
from kernel.retroforge.manifest import ExtractionManifest

HEADER_SIZE = 16

#: The four bytes this container format begins with. DATA the format defines, never a name we
#: chose: a file either starts with them or it is not this format.
FORMAT_SIGNATURE = b"NES\x1a"
PRG_ROM_UNIT_BYTES = 16 * 1024
CHR_ROM_UNIT_BYTES = 8 * 1024
TILE_BYTES = 16
TILE_WIDTH = 8
TILE_HEIGHT = 8


class InvalidCartridgeHeader(ValueError):  # noqa: N818
    """The source does not carry a valid 16-byte cartridge header."""


def _cartridge_header(source: ByteSource) -> bytes:
    """Return a validated header without guessing at arbitrary binary data."""
    if len(source) < HEADER_SIZE:
        raise InvalidCartridgeHeader("a cartridge header must contain 16 bytes")
    header = source.read(0, HEADER_SIZE)
    if header[:4] != FORMAT_SIGNATURE:
        raise InvalidCartridgeHeader("source does not begin with the cartridge format signature")
    return header


@dataclass(frozen=True)
class Planar2BppTileCodec:
    """Decode a planar 8 by 8, two-bit-per-pixel tile: 8 low-plane rows, then 8 high-plane rows."""

    codec_id: str = "planar.2bpp"
    platform: str = "headered-cartridge"
    bits_per_pixel: int = 2
    tile_width: int = TILE_WIDTH
    tile_height: int = TILE_HEIGHT
    bytes_per_tile: int = TILE_BYTES

    def decode_tile(self, source: ByteSource, offset: int) -> Tile:
        """Decode one complete tile at ``offset`` or propagate ``OutOfRange``."""
        tile = source.read(offset, self.bytes_per_tile)
        return tuple(
            tuple(
                ((tile[row] >> (7 - column)) & 1)
                | (((tile[row + TILE_HEIGHT] >> (7 - column)) & 1) << 1)
                for column in range(self.tile_width)
            )
            for row in range(self.tile_height)
        )


@dataclass(frozen=True)
class HeaderedCartridgeModule:
    """Describe the published 16-byte-header cartridge layout and its character tile codec."""

    platform_id: str = "headered-cartridge"
    display_name: str = "8-bit headered cartridge image"

    def detect(self, source: ByteSource) -> float:
        """Return full confidence only for data carrying the format signature."""
        if len(source) < 4:  # noqa: PLR2004
            return 0.0
        return 1.0 if source.read(0, 4) == FORMAT_SIGNATURE else 0.0

    def parse_metadata(self, source: ByteSource) -> dict[str, object]:
        """Parse the region sizes and the deterministic start of character ROM."""
        header = _cartridge_header(source)
        prg_rom_size = header[4] * PRG_ROM_UNIT_BYTES
        chr_rom_size = header[5] * CHR_ROM_UNIT_BYTES
        return {
            "format": "headered-cartridge",
            "prg_rom_size": prg_rom_size,
            "chr_rom_size": chr_rom_size,
            "chr_rom_offset": HEADER_SIZE + prg_rom_size,
        }

    def chr_rom_offset(self, source: ByteSource) -> int:
        """Return the byte offset immediately after the header and PRG ROM."""
        return cast(int, self.parse_metadata(source)["chr_rom_offset"])

    def tile_codecs(self) -> tuple[Planar2BppTileCodec, ...]:
        """Expose the one tile layout this container defines."""
        return (Planar2BppTileCodec(),)

    def palette_codecs(self) -> tuple[PaletteCodec, ...]:
        """Expose no palette codec because RF-001B is limited to pixel indices."""
        return ()

    def extract_chr_tiles(
        self, artifact: RomArtifact
    ) -> tuple[tuple[Tile, ...], ExtractionManifest]:
        """Decode every CHR ROM tile and record its immutable source offsets.

        A zero-sized character region denotes cartridge-provided RAM, not a successful empty ROM
        extraction. The manifest makes that distinction visible to every caller.
        """
        metadata = self.parse_metadata(artifact.source)
        manifest = ExtractionManifest(
            source_path=artifact.source_path,
            source_checksum=artifact.checksum,
            platform=self.platform_id,
        )
        chr_rom_size = cast(int, metadata["chr_rom_size"])
        if chr_rom_size == 0:
            manifest.warn("the header declares character RAM, so there are no ROM tiles to extract")
            return (), manifest

        chr_rom_offset = cast(int, metadata["chr_rom_offset"])
        codec = self.tile_codecs()[0]
        tiles: list[Tile] = []
        for index in range(chr_rom_size // codec.bytes_per_tile):
            offset = chr_rom_offset + index * codec.bytes_per_tile
            tiles.append(codec.decode_tile(artifact.source, offset))
            manifest.record(
                asset_id=f"chr-tile-{index:04d}",
                kind="tile",
                offset=offset,
                byte_length=codec.bytes_per_tile,
                codec_id=codec.codec_id,
            )
        return tuple(tiles), manifest
