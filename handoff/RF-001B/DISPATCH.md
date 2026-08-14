# DISPATCH RF-001B

**Status:** READY

```yaml
packet_id:            RF-001B
title:                NES artifact parser and the 2bpp decoder proof
active_build:         RetroForge
stream:               retroforge core
owner:                Codex
reviewer:             Claude Code, who re-runs every command independently
merges:               founder
size:                 medium
taint_class:          SAFE. Published console formats only. No proprietary source is read, no ROM
                      is acquired, and no byte of any commercial ROM enters this repository.

goal: >
    Implement the NES platform module against the Protocols RF-001A already fixed: parse an iNES
    header, locate CHR ROM, decode 8x8 2bpp tiles, and prove the decode byte by byte.

    THE INVARIANT: given known NES 2bpp tile bytes, RetroForge produces the correct 8x8 pixel index
    values, and no source byte is modified.

why_now: >
    RF-001A landed the contracts and an empty `platforms/`. The Protocols are the agreement; this is
    the first module that has to satisfy one. Until a platform module exists, `RomPlatformModule` is
    a shape nobody has had to fit.

    This is also the first CODE consumer of the ROM Hacking Research Lane Charter. Thirteen cards
    were filed STUDIED from that charter and none has an implementation. RF-001B does not implement
    them, and should not; it is the order that proves the shelf was pointed at something real.

CALIBRATION BAR, STATED PER PROBE AND NOT PER ASPECT: >
    READ THIS BEFORE WRITING A TEST. It is the whole reason this section exists as its own field.

    WO-S4 raised a battery from 8 comparisons to 14 and satisfied its calibration requirement,
    which asked for one falsifiable probe per WIDENED ASPECT. Ten of the fourteen probes could not
    fail under any legal input. The count rose, the evidence did not, and the contract permitted it
    because the bar was written per aspect.

    So: EVERY TEST YOU ADD MUST BE SHOWN ABLE TO FAIL, individually, and not one per group.

    For each new test, break the specific thing that test watches, observe THAT test go red, restore,
    observe it go green. Paste each transition into the RETURN naming the test by function name. A
    test whose red you cannot produce is decoration, and it is worth less than the four lines it
    occupies, because it makes the suite look wider than it is.

    Where a test genuinely cannot be made to fail in isolation, say so and say why. That is an
    acceptable answer. Silence is not.

out_of_scope: >
    RIDER, AND ANY UI. This module is UI-independent and imports nothing from the projection.
    EDITING OR SAVING. RF-001 is read-only; the source ByteSource is never mutated.
    SNES AND GENESIS. Their decoder rules are written and they are later orders.
    MAPPER-SPECIFIC BANK SWITCHING, compression, tilemaps, disassembly, emulator integration.
    CHANGING THE PROTOCOLS in kernel/retroforge/codec.py. If NES cannot be expressed through them,
    that is a finding about the seam and a BLOCK, not a licence to widen the interface.

file_allowlist:
  - kernel/retroforge/platforms/nes.py          # NEW: the module
  - kernel/retroforge/platforms/__init__.py     # export the module; no logic
  - tests/test_retroforge_nes.py                # NEW: the proof
  - handoff/RF-001B/RETURN.md                   # NEW, explicitly authorised

boundary: >
    Four first-party modules this order READS and may NOT change:
      kernel/retroforge/binary.py    ByteSource and OutOfRange. The decoder consumes them; if a
                                     bounds check needs to move, that is a finding, not an edit.
      kernel/retroforge/codec.py     the Protocols. Fitting them is the point of the order.
      kernel/retroforge/artifact.py  RomArtifact and its checksum.
      kernel/retroforge/manifest.py  ExtractionManifest, if the order records anything.

preconditions: >
    CHECK: file kernel/retroforge/codec.py contains class TileCodec
    CHECK: file kernel/retroforge/binary.py contains class ByteSource
    CHECK: file kernel/retroforge/platforms/__init__.py exists

the_work: >
    1. iNES HEADER. 16 bytes. Magic `NES\x1a`. PRG size in 16KB units at byte 4, CHR size in 8KB
       units at byte 5. Refuse a buffer that is not iNES rather than guessing.

    2. CHR ROM OFFSET. header (16) + PRG size. When CHR size is zero the cartridge uses CHR RAM and
       there is nothing to extract: that is a WARNING on the manifest and an empty result, never an
       exception and never a silent empty that reads like success.

    3. NES 2bpp TILE CODEC, 16 bytes per 8x8 tile.
         bytes 0..7  low bitplane, one byte per row
         bytes 8..15 high bitplane, one byte per row
       For row y: low = tile[y], high = tile[y + 8].
       For pixel x: shift = 7 - x; pixel = ((low >> shift) & 1) | (((high >> shift) & 1) << 1).
       Pixel values are 0..3.

    4. BOUNDS. A decode whose tile runs past the end of the source raises OutOfRange. It does not
       return a short tile and it does not pad.

contract_tests: >
    In tests/test_retroforge_nes.py. Each of these is a SEPARATE test and each must be shown able
    to fail on its own, per the calibration bar above.

      low plane only produces pixel value 1
      high plane only produces pixel value 2
      both planes set produce pixel value 3
      neither plane set produces pixel value 0
      a known 16-byte tile decodes to an exact expected 8x8 grid, written out literally
      bit order is MSB-first: a single set bit in bit 7 lands in pixel x=0, not x=7
      a decode past the end of the buffer raises OutOfRange
      CHR offset equals 16 + PRG_size for a simple iNES ROM
      a header that is not iNES is refused
      CHR size zero yields a manifest WARNING and an empty extraction, not an exception

    THE BIT-ORDER TEST IS THE ONE THAT MATTERS MOST. A decoder with reversed bit order passes every
    all-zero and all-one case and produces mirrored tiles forever.

definition_of_done: >
    NES tiles decode correctly against literal expected grids; bounds are enforced; the module
    satisfies RomPlatformModule without the Protocol changing; every new test has a pasted red-then-
    green transition; `make check` green.

verification_command: |
    cd codeforge
    .venv/bin/python -m pytest tests/test_retroforge_nes.py -v
    make check

rollback: >
    Revert the commit. The module is additive and nothing imports it yet.

approval_gates: >
    TWO, both real, both stopping.
    ANY CHANGE TO THE PROTOCOLS in codec.py is a founder decision.
    ANY REAL ROM DATA entering the repository is refused outright. Fixtures are synthetic bytes
    constructed in the test file. codeforge is PUBLIC.

store_search_result: >
    Both tiers searched 2026-08-14; one tier logged is an incomplete search.
    Certified Tier (hardware-store/catalog/, 22 cards): thirteen STUDIED cards from the ROM Hacking
    Research Lane Charter are the design source, not consumable code. Nearest by shape are
    `bank-and-memory-map` PRT-0017 (address mapping), `palette-discipline` PRT-0013, and
    `tilemap-bit-packing` PRT-0009. All are maturity STUDIED: pattern, no implementation.
    Working Shelf (codeforge/catalog/parts.yaml, 104 entries): `atomic-write` for any output write,
    `content-address` for checksum traceability. No binary reader, no tile codec, no palette codec.

    Verdict: NO PART TO CONSUME for the decoder itself. Do not create one during RF-001B; a codec
    with one consumer is a watch-list entry, and the pull rule wants a second.

parts_to_consume: >
    None for the decode path. If the order writes output, use `atomic-write` rather than a bare
    open().

watch_for: >
    BIT ORDER. MSB-first. This is the defect that survives a green suite, because symmetric
    fixtures cannot see it. Write one asymmetric tile and assert the whole grid.

    A TEST THAT CANNOT FAIL. See the calibration bar. This order was written the day after a battery
    grew by six probes that could not produce a divergence between them.

    ENDIANNESS AND SIGNEDNESS when reading header bytes. Read them as unsigned.

    THE EMPTY-CHR CASE READING AS SUCCESS. Zero tiles extracted and zero warnings is
    indistinguishable from a working extraction of a cartridge with no CHR ROM. It must warn.

blast_radius: >
    Run before this allowlist was fixed.
      grep -rln 'retroforge' --include='*.py' kernel/ tests/ adapters/
      -> kernel/retroforge/* and tests/test_retroforge_*.py only. No adapter imports it.
      grep -rn 'from kernel.retroforge' --include='*.py'
      -> the four test twins only. Nothing in the engine consumes RetroForge yet, so the blast
         radius of a wrong decode is contained to this module and its tests.
      The Rider projection at native/rider-retroforge/ does not import Python and is unaffected.

reusable_part_signals_required: >
    reimplemented, recurrence, generalizable, friction. Never blank; "none observed" is valid.
