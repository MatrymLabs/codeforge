# WO-KT-01 Bench Report

```yaml
packet_id: WO-KT-01
status: BLOCKED
branch: codex/wo-kt-01
pr_url: none

summary: >
  The Kotlin governance implementation did not begin because the required repository baseline is
  not green and the declared language-lane precondition target is absent. The Gradle wrapper does
  resolve successfully at Gradle 9.1.0 with Kotlin 2.2.0 after a reversible cache-permission retry.
  No Makefile, CI workflow, Kotlin build file, or linter configuration was changed.

files_touched:
  - work-orders/WO-KT-01/BENCH_REPORT.md

preconditions:
  structural: PASS, Makefile exists, no kotlin-lint target exists, and native/rider-retroforge/build.gradle.kts exists.
  gradle: PASS after elevated cache access, Gradle 9.1.0 and Kotlin 2.2.0.
  repository_gate: BLOCKED at native/edge generated bindings.
  language_lane_gate: BLOCKED, make language-lanes target is absent.

commands_run:
  - command: ./gradlew --version
    exit_code: 1
    output: |
      Exception in thread "main" java.io.FileNotFoundException: /home/josh/.gradle/wrapper/dists/gradle-9.1.0-bin/9agqghryom9wkf8r80qlhnts3/gradle-9.1.0-bin.zip.lck (Read-only file system)
      at java.base/java.io.RandomAccessFile.open(RandomAccessFile.java:67)
      at org.gradle.wrapper.GradleWrapperMain.main(SourceFile:67)
  - command: ./gradlew --version (elevated cache access)
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
          Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.08s
      make: *** [Makefile:72: lint-go] Error 1
      lint-go: native/edge UNVERIFIED - it does not build. Generated code absent?
                run `make proto` (ADR-0012: the bindings are git-ignored).
  - command: PATH="/home/josh/Projects/MatrymLabs/.venv/bin:$PATH" make language-lanes
    exit_code: 2
    output: |
      make: *** No rule to make target 'language-lanes'. Stop.

blockers: >
  The Build Sheet requires make check green and make language-lanes to confirm the Kotlin lane.
  The repository gate is red at native/edge because generated bindings are absent, and the
  language-lane target named by the order does not exist in this checkout. No workaround was
  attempted and no Kotlin gate was wired into make check.

reimplemented: none observed
recurrence: none observed; implementation did not start
generalizable: none observed
friction: the Gradle wrapper cache required elevated filesystem access; the language-lane command
  named by the Build Sheet is absent.
pattern_shapes: none observed; no implementation diff exists

pattern_screen:
  lane_echo: none observed; no implementation diff exists
  catalogue_match: none observed
  recurrence_check: none observed
  verdict_note: no extraction candidate; the order stopped at its preconditions
```
