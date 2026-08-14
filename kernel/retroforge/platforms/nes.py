"""iNES metadata and NES CHR tile decoding.

NES tiles carry palette indices, not colours. This module stays at that binary boundary so a
projection can choose a palette without changing the source interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from kernel.retroforge.artifact import RomArtifact
from kernel.retroforge.binary import ByteSource
from kernel.retroforge.codec import PaletteCodec, Tile
from kernel.retroforge.manifest import ExtractionManifest

INES_HEADER_SIZE = 16
PRG_ROM_UNIT_BYTES = 16 * 1024
CHR_ROM_UNIT_BYTES = 8 * 1024
NES_TILE_BYTES = 16
NES_TILE_WIDTH = 8
NES_TILE_HEIGHT = 8


class InvalidINESHeader(ValueError):
    """The source cannot be interpreted as an iNES ROM."""


def _ines_header(source: ByteSource) -> bytes:
    """Return a validated iNES header without guessing at arbitrary binary data."""
    if len(source) < INES_HEADER_SIZE:
        raise InvalidINESHeader("iNES header must contain 16 bytes")
    header = source.read(0, INES_HEADER_SIZE)
    if header[:4] != b"NES\x1a":
        raise InvalidINESHeader("source does not begin with the iNES magic NES\\x1a")
    return header


@dataclass(frozen=True)
class Nes2BppTileCodec:
    """Decode the NES's planar 8 by 8, two-bit-per-pixel tile format."""

    codec_id: str = "nes.2bpp"
    platform: str = "nes"
    bits_per_pixel: int = 2
    tile_width: int = NES_TILE_WIDTH
    tile_height: int = NES_TILE_HEIGHT
    bytes_per_tile: int = NES_TILE_BYTES

    def decode_tile(self, source: ByteSource, offset: int) -> Tile:
        """Decode one complete tile at ``offset`` or propagate ``OutOfRange``."""
        tile = source.read(offset, self.bytes_per_tile)
        return tuple(
            tuple(
                ((tile[row] >> (7 - column)) & 1)
                | (((tile[row + NES_TILE_HEIGHT] >> (7 - column)) & 1) << 1)
                for column in range(self.tile_width)
            )
            for row in range(self.tile_height)
        )


@dataclass(frozen=True)
class NesPlatformModule:
    """Describe the published iNES layout and its CHR tile codec."""

    platform_id: str = "nes"
    display_name: str = "Nintendo Entertainment System"

    def detect(self, source: ByteSource) -> float:
        """Return full confidence only for data carrying the iNES magic."""
        if len(source) < 4:
            return 0.0
        return 1.0 if source.read(0, 4) == b"NES\x1a" else 0.0

    def parse_metadata(self, source: ByteSource) -> dict[str, object]:
        """Parse iNES ROM sizes and the deterministic start of CHR ROM."""
        header = _ines_header(source)
        prg_rom_size = header[4] * PRG_ROM_UNIT_BYTES
        chr_rom_size = header[5] * CHR_ROM_UNIT_BYTES
        return {
            "format": "iNES",
            "prg_rom_size": prg_rom_size,
            "chr_rom_size": chr_rom_size,
            "chr_rom_offset": INES_HEADER_SIZE + prg_rom_size,
        }

    def chr_rom_offset(self, source: ByteSource) -> int:
        """Return the byte offset immediately after the header and PRG ROM."""
        return cast(int, self.parse_metadata(source)["chr_rom_offset"])

    def tile_codecs(self) -> tuple[Nes2BppTileCodec, ...]:
        """Expose the one tile layout defined by the NES PPU."""
        return (Nes2BppTileCodec(),)

    def palette_codecs(self) -> tuple[PaletteCodec, ...]:
        """Expose no palette codec because RF-001B is limited to pixel indices."""
        return ()

    def extract_chr_tiles(
        self, artifact: RomArtifact
    ) -> tuple[tuple[Tile, ...], ExtractionManifest]:
        """Decode every CHR ROM tile and record its immutable source offsets.

        A zero-sized CHR region denotes cartridge-provided CHR RAM, not a successful empty ROM
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
            manifest.warn("iNES ROM declares CHR RAM, so it has no CHR ROM tiles to extract")
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
