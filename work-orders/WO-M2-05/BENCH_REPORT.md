# WO-M2-05 Bench Report

```yaml
packet_id: WO-M2-05
status: COMPLETE
branch: codex/wo-m2-05-final
pr_url: pending founder review

result: >
  SeamVerdict now carries and renders a record for every battery aspect. Inventory, persistence,
  and coverage name their falsifiable probe(s); progression and permission remain structurally
  unfalsifiable under D1 and state the reason in the rendered output.

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
  measured export, make proto && make check exits 0.
current_verification_output: |
  export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  make proto && make check: exit 0
  1104 files already formatted
  All checks passed!
  lint-go: native/edge
  0 issues.
  lint-go: native/spine
  0 issues.
  tests/test_engine_seam_differential.py: 27 passed
  ruff check kernel/engine_seam.py tests/test_engine_seam_differential.py: All checks passed!
  ruff format --check kernel/engine_seam.py tests/test_engine_seam_differential.py: 2 files already formatted
  mypy kernel/engine_seam.py tests/test_engine_seam_differential.py: Success: no issues found
  render: 14 comparison(s) across 5 aspect(s), 3 of them falsifiable; progression and permission
  are rendered as structurally unfalsifiable with the D1 reason.

blockers: none; founder merge remains pending.

files_touched:
  - kernel/engine_seam.py
  - tests/test_engine_seam_differential.py
  - work-orders/WO-M2-05/BENCH_REPORT.md

implementation: per-aspect falsifiability data and rendered evidence; progression and permission were not made falsifiable.
reimplemented: none observed
recurrence: none observed
generalizable: the gate must diagnose missing toolchains at the source, not only report downstream generated-code absence
friction: the missing local .venv obscured the repository's documented command until symlink restoration
pattern_shapes: none observed

pattern_screen:
  lane_echo: none observed
  catalogue_match: none observed
  recurrence_check: none observed
  verdict_note: no extraction candidate; this is a gate/toolchain finding
```
