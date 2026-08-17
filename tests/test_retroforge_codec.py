"""Test twin for kernel/retroforge/codec.py.

These are Protocols, so the twin's job is to pin the CONTRACT rather than an implementation: a
conforming stub satisfies it, a stub missing a member does not, and the shapes the charter's cards
describe are the shapes actually declared.

Acceptance: a minimal conforming codec is recognised, and a decoded tile is indices.
Refusal: a class missing a protocol member is not an instance of it, and detection returns a
confidence rather than a boolean.
"""

from __future__ import annotations

from kernel.retroforge.binary import ByteSource
from kernel.retroforge.codec import AddressMapper, PaletteCodec, TileCodec


class _Conforming:
    """The smallest thing that satisfies TileCodec. Deliberately not a real decoder."""

    codec_id = "test.1bpp"
    platform = "test"
    bits_per_pixel = 1
    tile_width = 2
    tile_height = 2
    bytes_per_tile = 1

    def decode_tile(self, source: ByteSource, offset: int) -> tuple[tuple[int, ...], ...]:
        byte = source.read(offset, 1)[0]
        return ((byte >> 3 & 1, byte >> 2 & 1), (byte >> 1 & 1, byte & 1))


class _MissingDecode:
    codec_id = "test.broken"
    platform = "test"
    bits_per_pixel = 1
    tile_width = 2
    tile_height = 2
    bytes_per_tile = 1


def test_a_conforming_codec_satisfies_the_protocol() -> None:
    assert isinstance(_Conforming(), TileCodec)


def test_a_codec_missing_decode_tile_does_not_satisfy_it() -> None:
    """The refusal. A protocol nothing can fail is a comment."""
    assert not isinstance(_MissingDecode(), TileCodec)


def test_a_decoded_tile_is_indices_not_colours() -> None:
    """Indexing is the retro graphics model: the tile says 'colour 3', the palette decides what
    colour 3 is. Collapsing them would make every palette swap a re-decode."""
    tile = _Conforming().decode_tile(ByteSource(bytes([0b1001])), 0)
    assert tile == ((1, 0), (0, 1))
    assert all(isinstance(px, int) for row in tile for px in row)


def test_a_tile_decode_past_the_end_propagates_the_refusal() -> None:
    """A codec must not swallow OutOfRange into a short tile."""
    import pytest

    from kernel.retroforge.binary import OutOfRange

    with pytest.raises(OutOfRange):
        _Conforming().decode_tile(ByteSource(b""), 0)


def test_the_address_mapper_contract_permits_an_unmappable_address() -> None:
    """`bank-and-memory-map` (PRT-0017) names the failure: a pointer crossing a bank boundary
    without a switch. Returning None beats inventing an offset."""

    class _Mapper:
        platform = "test"
        mapping_name = "flat"

        def address_to_offset(self, address: int) -> int | None:
            return address if address < 16 else None

        def offset_to_address(self, offset: int) -> int | None:
            return offset

    mapper = _Mapper()
    assert isinstance(mapper, AddressMapper)
    assert mapper.address_to_offset(4) == 4
    assert mapper.address_to_offset(999) is None


def test_the_palette_contract_is_declared_separately_from_tiles() -> None:
    assert TileCodec is not PaletteCodec
