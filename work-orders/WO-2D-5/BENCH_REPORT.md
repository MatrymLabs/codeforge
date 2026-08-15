# WO-2D-5 Bench Report

```yaml
packet_id: WO-2D-5
status: BLOCKED
branch: codex/wo-2d-5
base: 3cb6b78a1faa03e1679f4138a8564568511bd643

result: >
  Movement probes now load rooms and exits from the Blueprint named by the existing
  _battery_for_seed(seed) parameter. Each probe still constructs a real Session with the
  supplied engine and drives handle_command; the command handler runs against the loaded
  room graph through a scoped probe harness. Blueprint-sensitivity rose from 1 of 18 to
  5 of 18, and engine-falsifiability stayed at 7 of 18. The implementation moves the
  measurement honestly, but the criterion requires at least 9 of 18, so this order is
  BLOCKED/PARTIAL rather than complete.

store_search: >
  Certified Tier (hardware-store/catalog/) was searched first for differential, metamorphic,
  golden-world, and differential-harness Parts; no matching card was found. Working Shelf
  (codeforge/catalog/parts.yaml) was searched second and contains Transform Verifier, a
  differential-testing shape already documented by the existing test. No new Part was
  imported; this order consumed the existing _battery_for_seed(seed) parameter and the real
  Blueprint loader as required by its sheet.

preconditions: |
  git rev-list --count HEAD..origin/main
  0

  PRE-FIX baseline measurement on 3cb6b78a:
  BASELINE BLUEPRINT-SENSITIVE: 1 of 18
  BASELINE SENSITIVE PROBES: coverage/all_overlay_rooms
  BASELINE ENGINE-FALSIFIABLE: 7 of 18
  BASELINE ENGINE-FALSIFIABLE PROBES: inventory/carry_limit, movement/go_north,
    movement/go_south, movement/go_east, movement/go_down,
    persistence/save_restore_casefile, coverage/all_overlay_rooms

  export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  make proto && make check
  make proto exit 0; make check exit 0
  5308 passed, 54 skipped, 74 warnings in 147.84s
  Coverage: 93.46% (required: 85%)

failure_before_repair: |
  The new deciding assertion was calibrated against the original behavior before restoring the
  patch:

  PRE-FIX MOVEMENT ANSWERS: ('forge', 'courtyard', 'accepted') ('forge', 'courtyard', 'accepted')
  Traceback (most recent call last):
    ...
  AssertionError: movement probe ignored the Blueprint under test

after_measurement: |
  0D BLUEPRINT-SENSITIVE: 5 of 18
  0D SENSITIVE PROBES: movement/go_north, movement/go_south, movement/go_east,
    movement/go_down, coverage/all_overlay_rooms
  2D BLUEPRINT-SENSITIVE: 5 of 18
  2D SENSITIVE PROBES: movement/go_north, movement/go_south, movement/go_east,
    movement/go_down, coverage/all_overlay_rooms

  first-forge ENGINE-FALSIFIABLE: 7 of 18
  first-forge ENGINE-FALSIFIABLE PROBES: inventory/carry_limit, movement/go_north,
    movement/go_south, movement/go_east, movement/go_down,
    persistence/save_restore_casefile, coverage/all_overlay_rooms
  seam-probe ENGINE-FALSIFIABLE: 7 of 18
  seam-probe ENGINE-FALSIFIABLE PROBES: inventory/carry_limit, movement/go_north,
    movement/go_south, movement/go_east, movement/go_down,
    persistence/save_restore_casefile, coverage/all_overlay_rooms
  first-forge COMPARISONS: 18
  seam-probe COMPARISONS: 18

verification: |
  .venv/bin/pytest -q tests/test_engine_seam_differential.py
  31 passed in 1.96s

  .venv/bin/ruff check kernel/engine_seam.py tests/test_engine_seam_differential.py
  All checks passed!

  .venv/bin/mypy kernel/engine_seam.py tests/test_engine_seam_differential.py
  Success: no issues found in 2 source files

  export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  make proto && make check
  make proto exit 0; make check exit 0
  5309 passed, 54 skipped, 74 warnings in 154.38s
  Coverage: 93.46% (required: 85%)

files_touched: |
  kernel/engine_seam.py
  tests/test_engine_seam_differential.py
  work-orders/WO-2D-5/BENCH_REPORT.md
  The CodeForge diff is confined to the Build Sheet allowlist. No core world or Session file
  was edited.

blockers: >
  BLOCKED/PARTIAL: 5 of 18 is below the required half-battery threshold of 9 of 18. The
  four movement probes plus the existing coverage probe are the only Blueprint-sensitive
  probes after consuming the existing seed parameter. Reaching 9 without buying the number
  would require a Principal Engineer ruling on additional world-dependent probes or a seam
  change; no such expansion was made.

reimplemented: none observed; the movement probe uses the existing battery parameter and loader
recurrence: differential probe batteries and falsifiability measurement recur from WO-2D-3 and WO-2D-4
generalizable: a probe that claims to vary by data must derive its setup from that data, not from a fixture label
friction: forge and kernel.world.world retain separate WORLD bindings, so the harness needed a scoped substitution for both while preserving the real command path

pattern_shapes: differential battery, loaded-world route selection, scoped harness substitution

pattern_screen:
  lane_echo: engine, commands, persistence, events, world graph, and integration were screened; no unrelated finding observed
  catalogue_match: Working Shelf Transform Verifier matched the differential-testing shape; no new Part was imported
  recurrence_check: the same battery-and-falsifiability shape is now present in three consecutive engine orders; extraction is a Principal Engineer decision
  verdict_note: BLOCKED/PARTIAL; all four movement probes now read Blueprint-defined rooms and exits, while the 7 of 18 engine-falsifiability floor holds, but the 9 of 18 Blueprint-sensitivity criterion is not reached
```

IN PLAIN TERMS: The movement checks now use the rooms and exits from whichever Blueprint is being tested, so swapping Blueprints changes five of the eighteen answers instead of only the room-coverage answer. That is honest progress, but it is below the required half-battery criterion and needs a Principal Engineer ruling before expanding the instrument. The key concept is data-driven probing: the test setup must come from the data it claims to measure.
