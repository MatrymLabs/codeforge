"""CARD: retroforge.view -- render a ROM's tiles where a human can look at them.

RetroForge could load, decode and manifest a cartridge and there was no way to SEE the result
without writing a script. The Rider ladder calls that rung L1: external tools and run
configurations invoking retroforge commands. L4, a native IDE projection with a real tile grid
and click-to-offset, needs the IntelliJ Platform SDK and does not exist; `native/rider-retroforge`
is a plain Kotlin library with no plugin and no entry point.

So this is the honest surface: a command that prints the grid, and a committed run configuration
that makes Rider invoke it. The tiles appear inside the IDE, in its console. That is L1 and it is
labelled L1, because calling a console render "the Rider tile grid" would be the kind of claim
this Workshop spends its time catching.

EVERY TILE CARRIES ITS OFFSET. That is the half of click-to-offset a console can honestly do: the
mapping from tile index to ROM address is printed beside each tile, so the number a human needs is
on screen even though nothing is clickable. The clicking waits for L4.

Usage:
    python -m kernel.retroforge.view <rom.nes> [--tiles 16] [--columns 4]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from kernel.retroforge.artifact import RomArtifact
from kernel.retroforge.binary import ByteSource
from kernel.retroforge.codec import Tile
from kernel.retroforge.platforms.planar_2bpp import (
    HeaderedCartridgeModule,
    InvalidCartridgeHeader,
    Planar2BppTileCodec,
)

#: Palette index 0..3 as ink. Deliberately ASCII: a console is the surface, and box-drawing or
#: colour escapes would render differently in Rider's console than in a terminal.
SHADES = " .+#"

TILE_SIDE = 8


def render_tile(tile: Tile) -> list[str]:
    """One tile as rows of ink."""
    return ["".join(SHADES[min(px, 3)] for px in row) for row in tile]


def render_sheet(tiles: list[Tile], offsets: list[int], columns: int = 4) -> list[str]:
    """Tiles laid out in a grid, each labelled with the ROM offset it came from.

    The offset label is the point. A tile you cannot locate in the file is a picture; a tile with
    its address is a finding you can act on.
    """
    lines: list[str] = []
    for start in range(0, len(tiles), columns):
        row_tiles = tiles[start : start + columns]
        row_offsets = offsets[start : start + columns]
        lines.append("  ".join(f"@{off:<#8x}" for off in row_offsets))
        rendered = [render_tile(t) for t in row_tiles]
        for line_no in range(TILE_SIDE):
            lines.append("  ".join(f"|{tile[line_no]}|" for tile in rendered))
        lines.append("")
    return lines


def view(rom_path: Path, tile_count: int = 16, columns: int = 4) -> int:
    """Load, decode and print. Returns a process exit code."""
    try:
        data = rom_path.read_bytes()
    except OSError as exc:
        print(f"retroforge: cannot read {rom_path}: {exc}", file=sys.stderr)
        return 2

    before = hashlib.sha256(data).hexdigest()
    source = ByteSource(data)
    module = HeaderedCartridgeModule()

    if module.detect(source) <= 0:
        print(f"retroforge: {rom_path.name} is not a headered cartridge image", file=sys.stderr)
        return 1

    try:
        chr_offset = module.chr_rom_offset(source)
    except InvalidCartridgeHeader as exc:
        print(f"retroforge: {exc}", file=sys.stderr)
        return 1

    artifact = RomArtifact.from_bytes(data, source_path=str(rom_path))
    codec = Planar2BppTileCodec()
    offsets = [chr_offset + i * codec.bytes_per_tile for i in range(tile_count)]
    tiles = [codec.decode_tile(source, off) for off in offsets]

    print(f"{rom_path.name}  {len(data)} bytes  sha256 {before[:16]}")
    print(f"platform {module.platform_id}  CHR at {chr_offset:#x}  showing {len(tiles)} tile(s)")
    print()
    for line in render_sheet(tiles, offsets, columns):
        print(line)

    # The source is read, never written. Re-hashing is cheap and it is the one property the whole
    # RetroForge legal block rests on, so it is checked rather than assumed.
    after = hashlib.sha256(rom_path.read_bytes()).hexdigest()
    if after != before:
        print("retroforge: SOURCE BYTES CHANGED -- refusing to report success", file=sys.stderr)
        return 1
    print(f"source unchanged ({after[:16]}), checksum {artifact.checksum[:16]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("rom", type=Path, help="path to a cartridge image you legally own")
    parser.add_argument("--tiles", type=int, default=16, help="how many tiles to render")
    parser.add_argument("--columns", type=int, default=4, help="tiles per row")
    args = parser.parse_args(argv)
    return view(args.rom, tile_count=max(1, args.tiles), columns=max(1, args.columns))


if __name__ == "__main__":
    raise SystemExit(main())
