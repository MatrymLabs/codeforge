# WO-2D-6: Blueprint-sensitivity, re-measured

**Date:** 2026-08-16
**Bench:** Claude Code
**Commit measured:** `a620f36d` (codeforge origin/main)
**Supersedes:** the board's `BLUEPRINT-SENSITIVITY IS 1 OF 18 AND HAS NEVER MOVED`,
measured at `3cb6b78a`

---

## The headline

**The number moved. 1 of 18 to 5 of 18.** The board's figure predates the repair aimed at the
cause the board itself named.

`3cb6b78a` is codeforge #991. Then #992, `test(seam): drive movement probes from the Blueprint
under test`, landed and was never re-measured. The board named the cause precisely: *"the
movement probes hardcode `forge` and `courtyard`, first-forge labels."* #992 is exactly that
repair, and it worked.

## The method, written so the next session can repeat it

A probe is **Blueprint-sensitive** when its answer against a HEALTHY engine differs between two
Blueprints. That is the only property that makes it a world test rather than a fixture test.
This is deliberately NOT the same question as `falsifiable_probes()`, which sabotages the ENGINE
and asks whether the probe notices. Engine-sensitivity and Blueprint-sensitivity are different
claims, and conflating them is what let the earlier number sit unexamined.

```python
from kernel import engine_seam as seam

def observations(bp: str) -> dict[str, str]:
    good = seam.Engine2D(seam._overlay_for_seed(bp))
    out = {}
    for aspect, name, probe in seam._selected_battery(bp):
        try:
            out[f"{aspect}/{name}"] = repr(probe(good))
        except Exception as exc:          # the exception IS the observation
            out[f"{aspect}/{name}"] = f"raised:{type(exc).__name__}"
    return out

a, b = observations("first-forge"), observations("seam-probe")
sensitive = [k for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
```

Diff at PROBE granularity. An earlier pass in this session compared the aggregate `SeamVerdict`
instead and found 0 differing fields, which is true and useless: the verdict aggregates to AGREED
in both worlds by design. It was reported at the time as a signal to measure properly, not as the
measurement.

## Result

```
battery size: first-forge=18  seam-probe=18
BLUEPRINT-SENSITIVE: 5 of 18

   + coverage/all_overlay_rooms
        first-forge: (('arc_chamber','arc_chamber'), ('archive','archive'), ...)
        seam-probe : (('relay_garden','relay_garden'), ('signal_bay','signal_bay'))
   + movement/go_down    first-forge ('arc_chamber','diagnostic_console','accepted')
                         seam-probe  ('relay_garden','signal_bay','accepted')
   + movement/go_east    first-forge ('component_vault','workshop','accepted')
                         seam-probe  ('signal_bay','relay_garden','accepted')
   + movement/go_north   first-forge ('diagnostic_console','workshop','accepted')
                         seam-probe  ('relay_garden','signal_bay','accepted')
   + movement/go_south   first-forge ('archive','library','accepted')
                         seam-probe  ('relay_garden','signal_bay','accepted')

INSENSITIVE (13), identical answer in both worlds:
   inventory/carry_limit, inventory/module_is_position_free, inventory/purse_renders,
   permission/player_denies_teleport, permission/rank_denies_admin,
   permission/wizard_denies_grant, permission/workshop_barrier_denies_wizard,
   persistence/gameplay_save_preserves_auth, persistence/grant_key_shape,
   persistence/save_restore_casefile,
   progression/calling_gate, progression/jp_for_level, progression/xp_for_level

falsifiable_probes() for comparison (engine sabotage, a DIFFERENT question):
   first-forge: 7 of 18    seam-probe: 7 of 18
```

## The denominator, per D10

D10 requires a criterion be measured against **what the architecture PERMITS to vary.** 18 is the
wrong denominator, and reporting `5/18 = 27.8%` understates the instrument.

The 13 insensitive probes are `inventory` (3), `permission` (4), `persistence` (3),
`progression` (3). **Under D1 those sit ABOVE the seam.** A permission or progression probe whose
answer changed between Blueprints would itself be the leak the differential exists to catch.
They are structurally incapable of Blueprint-sensitivity, correctly, by design. `engine_seam.py`
already says so for progression and permission in `_STRUCTURAL_UNFALSIFIABLE_REASONS`.

The world-facing probes are `coverage` (1) and `movement` (4).

> **Every probe that CAN be Blueprint-sensitive IS Blueprint-sensitive. 5 of 5.**

That is the honest figure. Stated the other way: after #992 there is no world-facing probe left
that reads a fixed fixture.

## What this does NOT establish

The battery is now correct at what it measures, and it measures a narrow thing. Five probes,
four of which are movement in cardinal directions plus one room-coverage check. Reporting 5 of 5
is not the same as reporting that the seam is thoroughly exercised across Blueprints, and this
report is not making that second claim.

**The open question is therefore no longer "why will the number not move."** It moved. The
question is now a judgment: **is a five-probe world-facing battery sufficient evidence to close
M2, or does the battery want widening first?** That is a Principal Engineer decision, not a
measurement, and this report does not pre-empt it.

## Two stale artifacts this exposed

1. **The board headline** `BLUEPRINT-SENSITIVITY IS 1 OF 18 AND HAS NEVER MOVED` is false at
   `a620f36d` and should carry the new figure with its denominator.

2. **`kernel/engine_seam.py:427`**, a comment that no longer describes the code:

   ```python
   # Blueprint sensitivity is intentionally limited to the coverage probe; the other
   # thirteen probes remain on the fixed synthetic fixture and are not world tests.
   ```

   Sensitivity is no longer limited to coverage; the four movement probes joined it in #992. The
   arithmetic is also from the 14-probe era: 1 + 13 = 14, and the battery is 18. Left as-is, the
   next session greps this and believes the design is narrower than it is. Same trap D9 names
   about headings that survive a reversal.

## Proof run, this session

```
pytest -q -n auto tests/test_engine_seam_differential.py   31 passed in 2.89s
pytest -q -n auto (full suite)                             5306 passed, 58 skipped
```
