# WO-KT-01 Bench Report

```yaml
packet_id: WO-KT-01
status: BLOCKED
branch: codex/wo-kt-rerun
pr_url: none

summary: >
  The Kotlin toolchain resolves, but the corrected repository baseline remains blocked at
  native/edge generated bindings and the declared language-lane precondition target is absent.
  No Makefile, CI workflow, Kotlin build file, or linter configuration was changed.

files_touched:
  - work-orders/WO-KT-01/BENCH_REPORT.md

commands_run:
  - command: ./gradlew --version (from native/rider-retroforge)
    exit_code: 0
    output: |
      Gradle 9.1.0
      Kotlin: 2.2.0
      Launcher JVM: 21.0.12
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
  - command: make language-lanes
    exit_code: 2
    output: |
      make: *** No rule to make target 'language-lanes'. Stop.

blockers: >
  The corrected baseline cannot become green because make proto cannot run without protoc-gen-go
  and a Go toolchain. The language-lane target named by the order is also absent. No workaround
  was attempted and the Kotlin gate was not wired into make check.

reimplemented: none observed
recurrence: none observed; implementation did not start
generalizable: none observed
friction: the order's language-lanes precondition names a target not present in the repository
pattern_shapes: none observed

pattern_screen:
  lane_echo: none observed
  catalogue_match: none observed
  recurrence_check: none observed
  verdict_note: no extraction candidate; baseline and lane preconditions stopped the order
```
