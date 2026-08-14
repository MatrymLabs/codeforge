# WO-M2-05 Bench Report

```yaml
packet_id: WO-M2-05
status: BLOCKED
branch: codex/wo-m2-rerun
pr_url: none

summary: >
  The corrected baseline precondition now includes make proto. It fails before implementation
  because protoc-gen-go is absent and the host has no go executable. The subsequent make check
  also stops at native/edge. No seam code or assertion-locked test was changed.

files_touched:
  - work-orders/WO-M2-05/BENCH_REPORT.md

commands_run:
  - command: make proto
    exit_code: 1
    output: |
      protoc --proto_path=proto --python_out=proto proto/telemetry.proto
      protoc --proto_path=proto --go_out=native/spine --go_opt=module=codeforge/spine proto/telemetry.proto
      protoc-gen-go: program not found or is not executable
      Please specify a program using an absolute path or make sure the program is available in your PATH system variable
      --go_out: protoc-gen-go: Plugin failed with status code 1.
      make: *** [Makefile:344: proto] Error 1
  - command: PATH="/home/josh/Projects/MatrymLabs/.venv/bin:$PATH" make check
    exit_code: 2
    output: |
      ruff format --check .
      1101 files already formatted
      ruff check .
      All checks passed!
      lint-rust: native/codeforge_nav
          Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.03s
      lint-go: native/edge UNVERIFIED - it does not build. Generated code absent?
                run `make proto` (ADR-0012: the bindings are git-ignored).
      make: *** [Makefile:72: lint-go] Error 1

blockers: >
  The required make proto precondition cannot complete without protoc-gen-go, and go is absent on
  this host. make check consequently remains red at native/edge. No workaround or seam repair was
  attempted.

reimplemented: none observed
recurrence: none observed; implementation did not start
generalizable: none observed
friction: generated bindings require a Go toolchain not present on this host
pattern_shapes: none observed

pattern_screen:
  lane_echo: none observed
  catalogue_match: none observed
  recurrence_check: none observed
  verdict_note: no extraction candidate; baseline stopped the order
```
