# D8 falsifiability re-measurement, 2026-08-16

Base: `origin/main` at `c67e1095` after WO-2D-3 landed.

```text
Baseline at 96c6658b: 3 of 14
Current at c67e1095: 7 of 18
Verdict: PARTIAL
```

Newly falsifiable movement probes:

```text
movement/go_down
movement/go_east
movement/go_north
movement/go_south
```

Existing falsifiable probes retained:

```text
coverage/all_overlay_rooms
inventory/carry_limit
persistence/save_restore_casefile
```

The other eleven probes remain non-falsifiable for the reasons recorded in the Bench Report:
engine-independent answers, D1's structurally above-seam progression and permission aspects, or
state-shape persistence checks that do not consult the engine.

The battery denominator changed from 14 to 18, so the absolute bar and proportion disagree:
21 percent versus 39 percent. This known criterion-authoring defect is recorded, not repaired.
