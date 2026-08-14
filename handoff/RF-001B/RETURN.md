# RETURN RF-001B

```yaml
packet_id: RF-001B
status: BLOCKED
branch: codex/rf-001b
pr_url: https://github.com/MatrymLabs/codeforge/pull/957

summary: >
  Added an iNES platform module with validated metadata, deterministic CHR ROM location, NES
  2bpp decoding, bounds propagation, CHR RAM warning behavior, extraction manifest offsets, and
  a protocol-conformance check. The RF-001B focused proof, formatting, lint, and type checks pass.
  The required repository Proof Run is blocked by a pre-existing native Go generated-code absence
  outside this Work Order's file allowlist.

files_touched:
  - kernel/retroforge/platforms/nes.py
  - kernel/retroforge/platforms/__init__.py
  - tests/test_retroforge_nes.py
  - handoff/RF-001B/RETURN.md

commands_run:
  - command: .venv/bin/python -m pytest tests/test_retroforge_nes.py -v
    result: PASS, 11 passed in 1.06s
  - command: .venv/bin/ruff check kernel/retroforge/platforms/nes.py kernel/retroforge/platforms/__init__.py tests/test_retroforge_nes.py
    result: PASS, All checks passed
  - command: .venv/bin/ruff format --check kernel/retroforge/platforms/nes.py kernel/retroforge/platforms/__init__.py tests/test_retroforge_nes.py
    result: PASS, 3 files already formatted
  - command: .venv/bin/mypy kernel/retroforge/platforms/nes.py kernel/retroforge/platforms/__init__.py tests/test_retroforge_nes.py
    result: PASS, Success: no issues found in 3 source files
  - command: make check
    result: >
      BLOCKED, exit 2. `make: ruff: No such file or directory`; the repository venv was absent
      from PATH.
  - command: PATH="$PWD/.venv/bin:$PATH" make check
    result: >
      BLOCKED, exit 2. `lint-go: native/edge UNVERIFIED - it does not build. Generated code
      absent? run make proto (ADR-0012: the bindings are git-ignored).`
  - command: post-rebase .venv/bin/python -m pytest tests/test_retroforge_nes.py -v
    result: PASS, 11 passed in 1.99s
  - command: post-rebase scoped ruff, format, and mypy checks
    result: PASS, All checks passed; 3 files already formatted; Success with no issues in 3 files
  - command: post-rebase PATH="$PWD/.venv/bin:$PATH" make check
    result: >
      BLOCKED, exit 2. Python format and lint plus the Rust lane pass; native/edge again stops at
      its absent, git-ignored generated bindings.

calibration:
  - test: test_low_plane_only_produces_pixel_value_one
    sabotage: force the low-plane result bit to 1
    red: 1 failed, index 1 became 1 instead of 0
    restored: 1 passed
  - test: test_high_plane_only_produces_pixel_value_two
    sabotage: shift the high plane by 2 instead of 1
    red: 1 failed, pixel value became 4 instead of 2
    restored: 1 passed
  - test: test_both_planes_set_produce_pixel_value_three
    sabotage: combine plane values with bitwise AND instead of OR
    red: 1 failed, pixel value became 0 instead of 3
    restored: 1 passed
  - test: test_neither_plane_set_produces_pixel_value_zero
    sabotage: force the low-plane result bit to 1
    red: 1 failed, the all-zero tile became all ones
    restored: 1 passed
  - test: test_a_known_tile_decodes_to_the_literal_expected_grid
    sabotage: flip the low-plane least-significant input bit
    red: 1 failed, the literal grid diverged at row 0 column 7
    restored: 1 passed
  - test: test_tile_bits_are_most_significant_bit_first
    sabotage: read each plane least-significant-bit first
    red: 1 failed, pixel x=0 became 0 instead of 1
    restored: 1 passed
  - test: test_a_tile_past_the_source_end_raises_out_of_range
    sabotage: pad a short read instead of demanding 16 source bytes
    red: 1 failed, DID NOT RAISE OutOfRange
    restored: 1 passed
  - test: test_chr_offset_and_extraction_manifest_are_derived_from_the_ines_header
    sabotage: add one byte to the derived CHR offset
    red: 1 failed, 16401 instead of 16400 (16 + 16 * 1024)
    restored: 1 passed
  - test: test_a_non_ines_header_is_refused
    sabotage: invert the iNES magic condition
    red: 1 failed, DID NOT RAISE InvalidINESHeader
    restored: 1 passed
  - test: test_chr_ram_returns_no_tiles_and_a_manifest_warning
    sabotage: omit the CHR RAM manifest warning
    red: 1 failed, warnings were []
    restored: 1 passed
  - test: test_platform_module_satisfies_the_locked_protocol
    sabotage: remove the public detect method from the platform module
    red: 1 failed, the runtime-checkable RomPlatformModule check returned false
    restored: 1 passed

blockers: >
  The required full Proof Run cannot progress beyond native/edge because its generated bindings
  are absent and git-ignored. Running `make proto` would create files outside RF-001B's allowlist,
  so no workaround was attempted.

reimplemented: none observed. Both Hardware Store tiers were searched before implementation; no
  binary reader or tile codec Part exists to consume.
recurrence: first occurrence in RetroForge. The decoder is intentionally local until a second real
  console module demonstrates a shared capability.
generalizable: NES planar tile decoding may later inform a cross-platform tile-codec Part, but one
  console module is not sufficient evidence for extraction.
friction: none observed.
pattern_shapes: validation boundary, bounds-checked binary decoder, extraction manifest.
```
