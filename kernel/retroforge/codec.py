"""CARD: retroforge.codec -- the contracts a platform must satisfy to be understood.

These are Protocols, not base classes, and deliberately so: a platform module is a description of a
console's published format, and inheritance would invite shared behaviour to leak between consoles
that have nothing in common but a decade.

The four contracts are the ones the ROM Hacking Research Lane Charter's STUDIED cards describe:
`bank-and-memory-map` (PRT-0017) is AddressMapper, `palette-discipline` (PRT-0013) is
PaletteCodec, and `tilemap-bit-packing` (PRT-0009) plus `offset-per-tile` (PRT-0019) sit behind
TileCodec. This module is where those cards stop being patterns and start being interfaces.

A decoded tile is INDICES, never colours. Indexing is the whole retro graphics model: the tile says
"colour 3" and the palette decides what colour 3 is. Collapsing the two here would make every
palette swap a re-decode.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from kernel.retroforge.binary import ByteSource

#: One decoded tile: rows of palette INDICES, not colours.
Tile = tuple[tuple[int, ...], ...]

#: One decoded colour, 8 bits per channel, whatever the console's native depth was.
Rgb = tuple[int, int, int]


@runtime_checkable
class TileCodec(Protocol):
    """Raw bytes to indexed pixels, for one console's tile format."""

    codec_id: str
    platform: str
    bits_per_pixel: int
    tile_width: int
    tile_height: int
    bytes_per_tile: int

    def decode_tile(self, source: ByteSource, offset: int) -> Tile:
        """The tile at `offset`. Raises OutOfRange rather than decoding a short read."""
        ...


@runtime_checkable
class PaletteCodec(Protocol):
    """Raw bytes to colours, for one console's palette format."""

    codec_id: str
    platform: str
    color_format: str

    def decode_palette(self, source: ByteSource, offset: int, count: int) -> tuple[Rgb, ...]: ...


@runtime_checkable
class AddressMapper(Protocol):
    """Console-visible addresses to file offsets, where the mapping is knowable.

    Returns None rather than guessing. A mapper that invents an offset for an address its mapping
    does not cover produces a confident wrong answer, and `bank-and-memory-map` names that exact
    failure: a pointer crossing a bank boundary without a switch.
    """

    platform: str
    mapping_name: str

    def address_to_offset(self, address: int) -> int | None: ...

    def offset_to_address(self, offset: int) -> int | None: ...


@runtime_checkable
class RomPlatformModule(Protocol):
    """One console. Detects its own ROMs, parses their metadata, and exposes its codecs."""

    platform_id: str
    display_name: str

    def detect(self, source: ByteSource) -> float:
        """Confidence in 0.0..1.0 that this source is one of ours.

        Confidence, never a boolean, because the risk the charter names is auto-detection that
        overpromises. A .bin with no header is a plausible Genesis ROM and a plausible anything
        else; 0.4 says that honestly and True does not.
        """
        ...

    def parse_metadata(self, source: ByteSource) -> dict[str, object]: ...

    def tile_codecs(self) -> tuple[TileCodec, ...]: ...

    def palette_codecs(self) -> tuple[PaletteCodec, ...]: ...
