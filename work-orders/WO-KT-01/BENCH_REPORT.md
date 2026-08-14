# WO-KT-01 Bench Report

```yaml
packet_id: WO-KT-01
status: BLOCKED
branch: codex/m2-blocked-reports
pr_url: https://github.com/MatrymLabs/codeforge/pull/964

result: >
  No Kotlin governance implementation was attempted. The order remains blocked, and this report
  consolidates both baseline rounds into the single required record.

rounds:
  - round: 1
    failure: make proto was never in the precondition; lint-go reported the downstream generated
      binding failure before Kotlin governance could be measured.
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
  lint-imports was not on PATH; it is installed at .venv/bin/lint-imports. The documented export
  omitted $PWD/.venv/bin (and later $HOME/.cargo/bin). Corrected by codeforge #965. Under the
  measured env -i export, make proto && make check exits 0. Kotlin governance was not started.
current_verification_output: |
  export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  make proto && make check: exit 0
  1104 files already formatted
  All checks passed!
  lint-go: native/edge
  0 issues.
  lint-go: native/spine
  0 issues.

blockers: the historical rounds remain BLOCKED reports; the corrected measured baseline is green and Kotlin governance was not implemented.

files_touched:
  - work-orders/WO-KT-01/BENCH_REPORT.md

implementation: none; Makefile, CI workflow, Kotlin build files, and linter configuration untouched.
reimplemented: none observed
recurrence: none observed
generalizable: language governance cannot be certified while the repository-wide generation precondition is opaque
friction: the missing local .venv obscured the documented gate invocation until symlink restoration
pattern_shapes: none observed

pattern_screen:
  lane_echo: none observed
  catalogue_match: none observed
  recurrence_check: none observed
  verdict_note: no extraction candidate; this is a gate/toolchain finding
```
