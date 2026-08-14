# WO-M2-06 Bench Report

```yaml
packet_id: WO-M2-06
status: BLOCKED
branch: codex/wo-m2-06-final
pr_url: pending founder re-scope

result: >
  No second Blueprint was created. WO-M2-05 has landed, but this order is blocked by an allowlist
  contradiction: definition_of_done requires run_differential to boot a selected Blueprint, while
  kernel/engine_seam.py is explicitly outside this order's allowlist and owned by WO-M2-05.

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
  lint-imports was not on PATH; it is installed at .venv/bin/lint-imports. The documented export
  omitted $PWD/.venv/bin (and later $HOME/.cargo/bin). Corrected by codeforge #965. Under the
  measured export, make proto && make check exits 0. The first-Blueprint differential remains AGREED.
current_verification_output: |
  export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  make proto && make check: exit 0
  1104 files already formatted
  All checks passed!
  lint-go: native/edge
  0 issues.
  lint-go: native/spine
  0 issues.

blockers: |
  The live signature is (seed: str = 'first-forge', zero_d: Engine | None = None, two_d: Engine | None = None).
  run_differential(seed='seam-probe') returns the same first-forge battery because seed is only
  recorded in the docstring and is not used to select data. Repairing that requires editing
  kernel/engine_seam.py, forbidden by file_allowlist. No workaround or allowlist widening attempted.

sequencing_gate: >
  WO-M2-05 has landed. No divergence was observed because the second-Blueprint boot path is not
  reachable under the current allowlist.

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
