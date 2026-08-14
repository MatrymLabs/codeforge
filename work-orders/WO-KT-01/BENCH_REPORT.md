# WO-KT-01 Bench Report

```yaml
packet_id: WO-KT-01
status: COMPLETE
branch: codex/wo-kt-01-final
pr_url: pending founder review

result: >
  Kotlin governance is implemented with the existing pinned ktlint 1.3.1 plugin, a standalone
  Makefile kotlin-lint target, and a SHA-pinned GitHub Actions JVM build for the Rider projection.
  The target is intentionally not wired into make check pending the approval gate.

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
  measured export, make proto && make check exits 0. Kotlin lint calibration and the Rider build
  both pass after the deliberate violation was removed.
current_verification_output: |
  export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  make proto && make check: exit 0
  1104 files already formatted
  All checks passed!
  lint-go: native/edge
  0 issues.
  lint-go: native/spine
  0 issues.
  calibration_red: |
    /home/josh/Projects/MatrymLabs/codeforge-codex/native/rider-retroforge/src/main/kotlin/Calibration.kt:1:11 Missing spacing around "{"
    FAILURE: Build failed with an exception.
    Execution failed for task ':ktlintMainSourceSetCheck'.
    KTLINT_RED_EXIT:1
  calibration_green: |
    ./gradlew clean ktlintCheck
    BUILD SUCCESSFUL in 10s
    8 actionable tasks: 8 executed
  rider_build: |
    ./gradlew build
    BUILD SUCCESSFUL in 28s
    11 actionable tasks: 4 executed, 7 up-to-date
  make_check: MAKE_CHECK_EXIT:0

blockers: none; approval remains required before wiring kotlin-lint into make check.

files_touched:
  - Makefile
  - .github/workflows/kotlin.yml
  - work-orders/WO-KT-01/BENCH_REPORT.md

implementation: existing native/rider-retroforge/build.gradle.kts already pins ktlint 1.3.1; added
  standalone Makefile target and CI workflow. No Kotlin source was changed.
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
