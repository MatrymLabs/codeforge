# WO-M2-06 Bench Report

```yaml
packet_id: WO-M2-06
status: BLOCKED
branch: codex/wo-m2-06
pr_url: none

summary: >
  The second Blueprint was not created. This order is gated on WO-M2-05 landing with a rendered
  per-aspect seam reason and on a green repository baseline. WO-M2-05 is blocked before
  implementation because make check stops at native/edge generated bindings, so the second
  Blueprint would make the differential result unreadable.

files_touched:
  - work-orders/WO-M2-06/BENCH_REPORT.md

preconditions:
  wo_m2_05_landed: BLOCKED, WO-M2-05 has a blocked Bench Report and has not landed on origin/main.
  repository_gate: BLOCKED, inherited from WO-M2-05's native/edge generated-code failure.
  first_blueprint_baseline: NOT RUN, correctly withheld behind the failed gate.

commands_run:
  - command: git show origin/main:work-orders/WO-M2-06/BUILD_SHEET.md
    exit_code: 0
    output: |
      WO-M2-05 has LANDED: the rendered verdict names a reason per aspect. If it does not, this
      order is not ready and the correct action is to say so, not to start.
      cd codeforge && make check green
      The differential is AGREED on first-forge BEFORE a second Blueprint is added. A red
      baseline makes the new Blueprint's result unreadable.

blockers: >
  WO-M2-05 has not landed, and its required green baseline is blocked at native/edge because
  generated bindings are absent and git-ignored. No Blueprint, differential change, or test was
  attempted. A divergence was not observed because the order was not allowed to start.

reimplemented: none observed
recurrence: none observed; implementation did not start
generalizable: none observed
friction: sequencing gate correctly prevents measuring a second Blueprint with an unstrengthened
  instrument.
pattern_shapes: none observed; no implementation diff exists

pattern_screen:
  lane_echo: none observed; no implementation diff exists
  catalogue_match: none observed
  recurrence_check: none observed
  verdict_note: no extraction candidate; the order stopped at its explicit sequencing gate
```
