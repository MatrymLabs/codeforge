# WO-KT-01 BUILD SHEET

**Repo:** `codeforge`

## Scope

`codeforge` only. The Makefile, a new CI workflow file, `native/rider-retroforge/` build
configuration, and one linter config. No other repository is touched, and no Python source is
modified.

## Invariant

No language lane reports governed unless a machine other than the maker's Raspberry Pi has
inspected it. A linter that has only ever printed PASS, or a job that only runs on skynet, leaves
the lane exactly as ungoverned as it is today while looking governed.

```yaml
packet_id:            WO-KT-01
title:                Govern the Kotlin lane, which opened ungoverned
stream:               engine
repository:           codeforge
goal: >
  KF-RF-1 and KF-RF-2, both carried open since 2026-08-13. The Kotlin toolchain is live (JBR
  25.0.3 javac, Gradle 9.1.0, Kotlin 2.2.0 as measured on the bench 2026-08-14, all userspace,
  no sudo; the Workbench's 8.14/2.0.21 was stale) and NOTHING inspects Kotlin:
  no linter locally, no JVM job in CI. `make check` is green over Kotlin it has never read, and
  the language census reports the lane PRESENT. When done, Kotlin is linted by a pinned tool, a
  CI job builds the projection on a runner, and the lane's governance is a fact a machine checks
  rather than a claim about one Raspberry Pi.

out_of_scope: >
  Do NOT write Kotlin features. Do NOT restructure native/rider-retroforge/. Do NOT touch the
  Python core, the seam, the overlay or any content/ file. Do NOT add a JVM dependency to the
  Python packaging. This order installs governance over code that already exists; it adds no
  capability.

file_allowlist:
  - Makefile
  - .github/workflows/                   (the JVM job; a new file is preferred over editing ci.yml)
  - native/rider-retroforge/build.gradle.kts
  - native/rider-retroforge/gradle/       (only if pinning requires it)
  - .ktlint.editorconfig or detekt.yml    (whichever tool you choose; ONE of them)

blast_radius: |
  $ grep -rln "kotlin\|gradlew\|\.kt\b" Makefile .github/ | head
  (run before fixing the allowlist and paste the real output. The Makefile control panel is
   shared with every other lane, so a new target must not change the behaviour of an existing one)

  make check currently runs: lint, shell, typecheck, test, packets, vocab, staleness, research,
  claims, flight, languages. Adding a Kotlin gate to `check` changes what every commit must pass.
  Whether it joins `check` or stands beside it is an approval gate below, not your call.

preconditions: >
    CHECK: file Makefile exists
    CHECK: file Makefile lacks kotlin-lint
    CHECK: file native/rider-retroforge/build.gradle.kts exists

    Behavioural:
      cd native/rider-retroforge && ./gradlew --version                the toolchain resolves
      make proto                                                  FIRST, and every order below
        native/spine imports protobuf bindings that ADR-0012 git-ignores, so `make check` cannot
        pass on a bench that has never generated them. codeforge's own CI runs this as an explicit
        step before the gate; a bench is no different. protoc 27.3 and protoc-gen-go are on this
        host, verified 2026-08-14.
      cd codeforge && make check                                    green


contract_tests: >
  There is no test twin for a linter. The contract here is CALIBRATION, and it is mandatory:
  the Bench Report must show the tool RED on a deliberate violation and GREEN when removed.
  Canon section 13: a Gate is trusted only when it has been shown to fail for the bad state it
  claims to catch. A Kotlin linter that has only ever printed PASS is exactly the instrument this
  order was written to replace.

definition_of_done:
  - "One Kotlin linter installed and PINNED to an exact version. ktlint or detekt; pick one, say
     why in the Bench Report, do not install both."
  - "A Makefile target invokes it. Verb DOES, per the control-panel convention."
  - "CALIBRATION PASTED: introduce a Kotlin style violation, show the tool exits non-zero with its
     output, remove it, show it exits zero. Both outputs verbatim in the Bench Report."
  - "A CI job builds the Rider projection on a GitHub runner. SHA-pin every action with the
     version in a comment, matching this repository's existing convention."
  - "The CI job runs on a runner with no access to skynet's JBR. If the toolchain cannot be
     provisioned on a runner, that is a FINDING: file it BLOCKED with the failure output rather
     than pinning the job to a self-hosted machine, because a job that only runs on the maker's
     Pi reproduces KF-RF-2 in a new place."
  - "KF-RF-1 and KF-RF-2 are closable, with the evidence that closes each named."
  - "make check green."

verification_command: |
  cd codeforge && make proto && make check && make kotlin-lint && cd native/rider-retroforge && ./gradlew build

rollback: >
  git revert. The linter config and CI job are additive; reverting returns the lane to ungoverned,
  which is the state it is in today.

approval_gates: >
  DOES THE KOTLIN GATE JOIN `make check`? That changes what every commit in this repository must
  pass, on every lane, including Python-only changes. Principal Engineer decision. Build it as a
  standalone target, report the recommendation, and do NOT wire it into `check` without the stamp.

size:                 medium

taint_class:          SAFE
                      Toolchain governance only. Note that RetroForge's SUBJECT matter is
                      CAUTION under D-9 (no ROM bytes in git, synthetic fixtures only), but this
                      order touches no ROM, no fixture and no decoder. If a task in front of you
                      requires reading a commercial ROM, it is not this order.

# EXTRACTION CONTEXT - read before implementing
store_search_result: >
  Certified Tier (hardware-store/catalog/): searched for a language-lane governance or linter-
  wiring Part. Nothing catalogued. Working Shelf (codeforge/catalog/parts.yaml): the shell lane
  precedent exists (ship gate(shell), #257, shellcheck wired into a control-panel target) and is
  the pattern to follow, not a Part to import. BOTH tiers searched.

parts_to_consume:     none. Follow the shellcheck precedent's SHAPE.

watch_for: >
  This is the third language lane to be governed after Python and shell, and the second to be
  governed AFTER the code arrived rather than before. If wiring a lane is now the same four steps
  every time (pin a tool, add a target, calibrate red-then-green, add a CI job), say so. Four
  steps repeated three times with a named next consumer is a Part candidate: the next lane is
  already visible, and csharp and gdscript are DEFERRED in the census with "the toolchain arrives
  with its rung".
```

## Why this is safe to run beside the M2 orders

The allowlist is disjoint from WO-M2-05 and WO-M2-06: this order touches the Makefile, CI, and
`native/rider-retroforge/`; those two touch `kernel/engine_seam.py`, `tests/`, and
`content/seeds/seam-probe/`. No file appears in two allowlists. This is the fallback that keeps
the bench loaded if an M2 order blocks on a divergence, which is an outcome the Active Build
record explicitly expects.
