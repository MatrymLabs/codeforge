# WO-M2-06 Bench Report

```yaml
packet_id: WO-M2-06
status: BLOCKED
branch: codex/wo-m2-06-rerun
pr_url: none

summary: >
  The second Blueprint was not created. The order requires WO-M2-05 to land first and requires
  make proto before make check. WO-M2-05 is blocked because protoc-gen-go and Go are absent, so
  the differential cannot be measured against a second Blueprint yet.

files_touched:
  - work-orders/WO-M2-06/BENCH_REPORT.md

commands_run:
  - command: git show origin/main:work-orders/WO-M2-06/BUILD_SHEET.md | grep -A5 'WO-M2-05 has LANDED'
    exit_code: 0
    output: |
      WO-M2-05 has LANDED: the rendered verdict names a reason per aspect. If it does not, this
      order is not ready and the correct action is to say so, not to start.
      make proto                                                  FIRST, and every order below
        native/spine imports protobuf bindings that ADR-0012 git-ignores, so `make check` cannot
        pass on a bench that has never generated them.

blockers: >
  WO-M2-05 has not landed, and the shared make proto precondition fails because protoc-gen-go is
  absent and no Go toolchain is installed. No Blueprint, differential change, or test was
  attempted. No divergence was observed because the order was not allowed to start.

reimplemented: none observed
recurrence: none observed; implementation did not start
generalizable: none observed
friction: the sequencing gate correctly prevents measuring a second Blueprint with an
  unstrengthened instrument
pattern_shapes: none observed

pattern_screen:
  lane_echo: none observed
  catalogue_match: none observed
  recurrence_check: none observed
  verdict_note: no extraction candidate; the order stopped at its explicit sequencing gate
```
