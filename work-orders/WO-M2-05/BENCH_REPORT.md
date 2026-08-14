# WO-M2-05 Bench Report

```yaml
packet_id: WO-M2-05
status: BLOCKED
branch: codex/wo-m2-05
pr_url: none

summary: >
  The order did not begin implementation because its required green baseline is unavailable on
  this checkout. Structural preconditions passed. The repository gate reaches Python formatting,
  Python lint, and Rust, then stops at native/edge because generated Go bindings are absent and
  git-ignored. No seam code or assertion-locked test was changed.

files_touched:
  - work-orders/WO-M2-05/BENCH_REPORT.md

preconditions:
  structural: PASS, kernel/engine_seam.py exists and contains falsifiable_probes; the differential
    test file exists.
  behavioral: BLOCKED before implementation.

commands_run:
  - command: make check
    exit_code: 2
    output: |
      ruff format --check .
      make: ruff: No such file or directory
      make: *** [Makefile:46: lint-python] Error 127
  - command: PATH="$PWD/.venv/bin:$PATH" make check
    exit_code: 2
    output: |
      ruff format --check .
      make: ruff: No such file or directory
      make: *** [Makefile:46: lint-python] Error 127
  - command: PATH="/home/josh/Projects/MatrymLabs/.venv/bin:$PATH" make check
    exit_code: 2
    output: |
      ruff format --check .
      1101 files already formatted
      ruff check .
      All checks passed!
      lint-rust: native/codeforge_nav
          Compiling pyo3-ffi v0.29.0
          Compiling pyo3 v0.29.0
          Checking codeforge_nav v0.1.0 (/home/josh/Projects/MatrymLabs/codeforge-codex/native/codeforge_nav)
          Finished `dev` profile [unoptimized + debuginfo] target(s) in 5.04s
      lint-go: native/edge UNVERIFIED - it does not build. Generated code absent?
                run `make proto` (ADR-0012: the bindings are git-ignored).
      make: *** [Makefile:72: lint-go] Error 1

blockers: >
  The Build Sheet requires a green make check before implementation. The current origin/main
  baseline is red at native/edge because generated bindings are absent. Running make proto would
  create generated files outside this order's allowlist, so no workaround was attempted.

reimplemented: none observed
recurrence: none observed; implementation did not start
generalizable: none observed
friction: the codeforge-codex checkout has no local .venv, so the repository root venv was needed
  to reach the actual gate failure.
pattern_shapes: none observed; no implementation diff exists

pattern_screen:
  lane_echo: none observed; no implementation diff exists
  catalogue_match: none observed
  recurrence_check: none observed
  verdict_note: no extraction candidate; the order stopped at its baseline precondition
```
