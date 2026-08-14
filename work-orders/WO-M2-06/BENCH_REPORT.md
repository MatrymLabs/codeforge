# WO-M2-06 Bench Report

```yaml
packet_id: WO-M2-06
status: BLOCKED
branch: codex/m2-blocked-reports
pr_url: pending

result: >
  No second Blueprint was created. WO-M2-06 remains gated on WO-M2-05 landing, and this report
  consolidates the same two baseline rounds that prevented the prerequisite order from landing.

rounds:
  - round: 1
    failure: make proto was never in the precondition; lint-go reported the downstream generated
      binding failure.
    unblocked_by: codeforge #962, which corrected the order preconditions to run make proto first.
  - round: 2
    failure: make proto exposed the real fault: no Go toolchain and no protoc-gen-go in userspace.
    unblocked_by: codeforge #963, which corrected the toolchain/gate diagnosis.
  - additional:
    failure: codeforge-codex had no .venv for the documented gate invocation.
    unblocked_by: the .venv symlink was restored on 2026-08-14.

finding: >
  lint-go TOLD you to run `make proto` when the real fault was a missing toolchain. You followed a
  correct instruction from a misleading instrument. That is the finding that produced #963.

current_verification: >
  With the userspace Go and protoc-gen-go paths restored, make proto passes. The full make check
  reaches both Go modules successfully, then stops at lint-imports because that executable is not
  installed. WO-M2-06 remains gated behind WO-M2-05 and was not started.
current_verification_output: |
  make proto: regenerated proto/telemetry_pb2.py + native/spine/telemetrypb/telemetry.pb.go
  make check: lint-go: native/edge; 0 issues.; lint-go: native/spine; 0 issues.;
  make: lint-imports: No such file or directory; make: *** [Makefile:99: imports] Error 127

blockers: WO-M2-06 remains sequenced behind WO-M2-05, whose current baseline is blocked by the missing lint-imports executable.

sequencing_gate: >
  WO-M2-05 has not landed, so the second Blueprint was correctly not started. No divergence was
  observed because the order never reached the differential run.

files_touched:
  - work-orders/WO-M2-06/BENCH_REPORT.md

implementation: none; no Blueprint, differential code, or test assertions touched.
reimplemented: none observed
recurrence: none observed
generalizable: sequence measurement orders behind a verified instrument baseline
friction: the missing local .venv obscured the documented gate invocation until symlink restoration
pattern_shapes: none observed

pattern_screen:
  lane_echo: none observed
  catalogue_match: none observed
  recurrence_check: none observed
  verdict_note: no extraction candidate; this is a sequencing and gate/toolchain finding
```
