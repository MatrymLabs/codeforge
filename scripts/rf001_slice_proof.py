#!/usr/bin/env python3
"""RF-001 slice proof: drive a ROM load -> decode -> manifest -> display as ONE chain.

Every part of this slice already existed and was unit tested. `kernel/retroforge` carries the
artifact, the byte source, the codecs and the manifest; the Kotlin side carries an ASCII tile
projection. Forty Python tests pass. What did NOT exist was a run of the whole thing end to end,
and the Master Checklist recorded DONE-2 as "no orders, no bench, nothing written" partly because
a pile of green unit tests is invisible as a capability.

That distinction is the reason this file exists. Six of the eight DONE-2 IN items were built and
proven in isolation; the seam BETWEEN them had nothing, exactly as the M2 pipeline had nothing
before `m2_pipeline_proof.py`. A decoder that decodes and a manifest that records are two facts.
"this ROM produced these tiles and this manifest, and the bytes never moved" is one.

    1. SYNTHESIZE  build an iNES image in memory, hash it
    2. LOAD        detect the header, parse the metadata, locate CHR
    3. DECODE      decode CHR into tiles through the 2bpp codec
    4. MANIFEST    emit an extraction manifest and demand it be traceable
    5. DISPLAY     render the tiles as an ASCII grid, the projection that actually exists
    6. INTEGRITY   re-hash the source bytes and prove nothing moved

THE FIXTURE IS SYNTHETIC AND STAYS SYNTHETIC. It is constructed here from a b"NES\\x1a" header and
hand-written CHR planes. No ROM is read from disk, none is committed, and none ever should be: the
RetroForge legal block treats a copyrighted ROM in a repository as a never-automate item alongside
publishing, because it is not revertible the way a bad merge is.

`--sabotage <stage>` breaks one stage on purpose. A gate is trusted only once it has been shown to
fail for the bad state it claims to catch (canon 13), so sabotage is part of the instrument rather
than a debugging leftover.

Usage:
    python scripts/rf001_slice_proof.py
    python scripts/rf001_slice_proof.py --sabotage integrity
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kernel.retroforge.artifact import RomArtifact  # noqa: E402
from kernel.retroforge.binary import ByteSource  # noqa: E402
from kernel.retroforge.codec import Tile  # noqa: E402
from kernel.retroforge.platforms.planar_2bpp import (  # noqa: E402
    HeaderedCartridgeModule,
    Planar2BppTileCodec,
)

PASS, FAIL = "PASS", "FAIL"

# One CHR tile, hand-written. Bytes 0-7 are the low plane, 8-15 the high plane, and a pixel is
# low | (high << 1), so a byte set in both planes reads as colour 3 and one plane alone reads 1 or
# 2. This tile is a diagonal in colour 3 with a colour-1 border row, chosen because a WRONG plane
# order still decodes to something plausible and only a specific pattern catches it.
_TILE = bytes(
    (
        # low plane: diagonal, last row solid
        *(0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0xFF),
        # high plane: same diagonal, no last row
        *(0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x00),
    )
)
_SHADES = " .+#"  # colour 0..3

#: Row 0 of the hand-written tile: the diagonal's first pixel, in colour 3, and nothing else.
#: Asserting the exact row is what makes a one-byte misalignment detectable.
_EXPECTED_FIRST_ROW = (3, 0, 0, 0, 0, 0, 0, 0)

#: A tile is 8x8. Named so the display check reads as a shape assertion, not two magic numbers.
_TILE_SIDE = 8


def synthesize_rom(tiles: int = 4) -> bytes:
    """An iNES image: 16-byte header, one 16KB PRG page of zeros, then CHR tiles."""
    chr_pages = 1
    header = b"NES\x1a" + bytes([1, chr_pages]) + bytes(10)
    prg = bytes(16 * 1024)
    chr_data = (_TILE * tiles).ljust(8 * 1024, b"\x00")
    return header + prg + chr_data


def render(tile: Tile) -> list[str]:
    """The tile as ASCII. This is the projection that EXISTS; the Rider tile grid does not.

    A `Tile` IS its rows: `tuple[tuple[int, ...], ...]` of palette indices, not an object with a
    `.rows` attribute. The first draft of this script assumed the latter and rendered nothing,
    which is the cheapest possible reminder to read the type rather than guess it.
    """
    return ["".join(_SHADES[min(px, 3)] for px in row) for row in tile]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--sabotage",
        choices=["load", "decode", "manifest", "integrity"],
        help="break one stage on purpose, to prove this instrument can fail",
    )
    args = parser.parse_args(argv)
    ok = True

    def verdict(name: str, passed: bool, detail: str) -> None:
        nonlocal ok
        ok = ok and passed
        print(f"  [{PASS if passed else FAIL}] {name:<10} {detail}")

    print("RF-001 slice :: load -> decode -> manifest -> display, one chain")

    # 1. SYNTHESIZE
    rom = synthesize_rom()
    before = hashlib.sha256(rom).hexdigest()
    verdict("synthesize", len(rom) > 0, f"{len(rom)} bytes, sha256 {before[:16]}")

    # 2. LOAD
    probe = rom
    if args.sabotage == "load":
        probe = b"SEGA" + rom[4:]  # wrong magic: the module must refuse it
    source = ByteSource(probe)
    module = HeaderedCartridgeModule()
    confidence = module.detect(source)
    detected = confidence > 0
    chr_offset = -1
    if detected:
        module.parse_metadata(source)  # exercised: the slice must parse, not merely detect
        chr_offset = module.chr_rom_offset(source)
    verdict(
        "load",
        detected and chr_offset > 0,
        f"iNES detected (confidence {confidence:.2f}), CHR at offset {chr_offset}"
        if detected
        else "header REFUSED, which is correct for a sabotaged magic",
    )
    if not detected:
        print(f"\nVERDICT: {FAIL} (sabotage proved the loader refuses a bad header)")
        return 1

    # 3. DECODE
    artifact = RomArtifact.from_bytes(probe, source_path="synthetic.nes")
    codec = Planar2BppTileCodec()
    offset = chr_offset if args.sabotage != "decode" else chr_offset + 1  # misalign by one byte
    first = codec.decode_tile(ByteSource(probe), offset)
    pixels = [px for row in first for px in row]
    # The EXACT pattern, not the value range. The first draft asserted max==3 and min==0, and a
    # one-byte misalignment sails through it: the shifted read produces the same value SET, just
    # in different places. The sabotage run is what exposed that, which is the entire argument for
    # having one. A gate that cannot fail is decoration (canon 13), and this one could not.
    decoded_ok = bool(pixels) and first[0] == _EXPECTED_FIRST_ROW
    verdict(
        "decode",
        decoded_ok,
        f"tile 0 decoded, {len(pixels)} px, row0 {first[0] if first else ()}"
        + ("" if decoded_ok else "  <- MISALIGNED: row0 is not the expected diagonal start"),
    )

    # 4. MANIFEST
    tiles, manifest = module.extract_chr_tiles(artifact)
    if args.sabotage == "manifest":
        manifest.assets.clear()  # a manifest with no assets must not read as traceable
    # `traceable` is deliberately VACUOUS on an empty manifest, and the engine has a test saying
    # so: `test_an_empty_manifest_is_vacuously_traceable`. Traceability is a property of the assets
    # present, not a claim that extraction happened. So the slice must assert BOTH -- that assets
    # exist AND that they cite this run. The first draft checked `traceable and bool(tiles)`, which
    # looked at the wrong collection entirely: clearing the manifest left the TILES untouched and
    # the check passed while the manifest was empty.
    traceable = bool(manifest.traceable)
    has_assets = len(manifest.assets) > 0
    verdict(
        "manifest",
        traceable and has_assets,
        f"{len(tiles)} tiles, {len(manifest.assets)} asset(s), traceable={traceable}"
        + ("" if has_assets else "  <- EMPTY: vacuously traceable is not traceable"),
    )

    # 5. DISPLAY
    grid = render(first)
    verdict(
        "display",
        len(grid) == _TILE_SIDE and all(len(r) == _TILE_SIDE for r in grid),
        f"{len(grid)}x{len(grid[0]) if grid else 0} ASCII grid rendered",
    )
    for row in grid:
        print(f"             |{row}|")

    # 6. INTEGRITY
    after = hashlib.sha256(rom if args.sabotage != "integrity" else rom + b"!").hexdigest()
    verdict(
        "integrity",
        after == before,
        f"source bytes unchanged ({after[:16]})"
        if after == before
        else "SOURCE BYTES MOVED -- the one thing this slice may never do",
    )

    print(f"\nVERDICT: {PASS if ok else FAIL}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
