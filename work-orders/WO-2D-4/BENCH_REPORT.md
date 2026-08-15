# WO-2D-4 Bench Report

```yaml
packet_id: WO-2D-4
repository: codeforge
status: PARTIAL
base: origin/main at c67e1095
source_files_changed: none
verdict: PARTIAL
```

## Preconditions and proof

`git rev-parse HEAD` and `git rev-parse origin/main` both returned `c67e10950e4a19f4069530f3ef698928ec73a76c`.
`git rev-list --count HEAD..origin/main` returned `0`. The landed WO-2D-3 change is present on
`origin/main`.

The precondition proof was:

```text
CMD: export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH" && make proto && make check && python -c "from kernel import engine_seam as s; print(len(s.falsifiable_probes()), sorted(s.falsifiable_probes()))"
EXIT: 0
OUTPUT: 5308 passed, 54 skipped, 58 warnings in 167.92s (0:02:47)
OUTPUT: Required test coverage of 85% reached. Total coverage: 93.46%
OUTPUT: 7 ['coverage/all_overlay_rooms', 'inventory/carry_limit', 'movement/go_down', 'movement/go_east', 'movement/go_north', 'movement/go_south', 'persistence/save_restore_casefile']
```

The baseline recorded by the Build Sheet on `origin/main` at `96c6658b` was:

```text
3 ['coverage/all_overlay_rooms', 'inventory/carry_limit', 'persistence/save_restore_casefile']
```

## Measurement

The falsifiability count rose from `3 of 14` to `7 of 18`. The four probes that moved the
measurement are the new `movement` probes:

- `movement/go_north`
- `movement/go_south`
- `movement/go_east`
- `movement/go_down`

Each drives a real command through `handle_command(session, signal)` and returns the room before,
the room after, and `accepted` or `refused`. A legal wrong-room saboteur produces a movement
divergence, so these probes are genuinely sensitive to the engine inside the Session.

The three existing falsifiable probes remained falsifiable:

- `inventory/carry_limit`
- `persistence/save_restore_casefile`
- `coverage/all_overlay_rooms`

The remaining eleven probes did not become falsifiable:

- `inventory/purse_renders`, `inventory/module_is_position_free`: these answers do not consult the
  engine.
- `progression/xp_for_level`, `progression/jp_for_level`, `progression/calling_gate`: D1 places
  progression above the seam, so engine sensitivity here would indicate a leak rather than proof.
- `permission/rank_denies_admin`, `permission/player_denies_teleport`,
  `permission/wizard_denies_grant`, `permission/workshop_barrier_denies_wizard`: authorization is
  above the seam; the legal engine saboteurs do not create a meaningful permission divergence.
- `persistence/grant_key_shape`, `persistence/gameplay_save_preserves_auth`: these answers do not
  consult the engine.

The battery grew from 14 to 18. Therefore the absolute result and proportion disagree: `3/14` was
about `21%`, while `7/18` is about `39%`. This is the known authoring defect in the criterion: the
absolute RISEN bar is `8 or more`, while the denominator changed. It is named here and not
resolved by adding probes or changing the criterion.

Against the pre-authorised thresholds, this is **PARTIAL**, not RISEN and not DECORATIVE. The
count rose and movement became falsifiable, but the result is below eight. PARTIAL is a successful
measurement outcome and requires a Principal Engineer decision, not a Bench repair or a probe
expansion.

## Scope and extraction signals

```yaml
files_touched:
  - work-orders/WO-2D-4/BENCH_REPORT.md
  - reports/2026-08-16-d8-falsifiability-remeasure.md
reimplemented: none observed
recurrence: none observed as a second certified Part consumer
generalizable: the falsifiability measurement cleanly separates probe sensitivity from comparison count
friction: reports/ is git-ignored and requires an explicit force-add for the allowed evidence artifact
pattern_shapes: measurement-only report, probe-name delta, and absolute-versus-proportional verdict
lane_echo: none observed in Codex persistence, commands, events, transactions, world graph, or integration territory
catalogue_match: none observed in either Hardware Store tier
recurrence_check: none observed
verdict_note: first occurrence of this exact denominator disagreement is recorded; no Part was promoted
```

## IN PLAIN TERMS

The differential now has four real movement checks, and four deliberately different engines can be
made to disagree on them. The battery is stronger, but it has not crossed the agreed threshold.

This matters because the engine is now tested through the actual player command path, not merely
through helper functions that happened to receive an engine-derived room label.

The important concept is sensitivity: a test is sensitive only if a legal bad engine can make its
answer change.
