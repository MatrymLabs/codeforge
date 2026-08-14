# WO-M2-06 Bench Report

```yaml
packet_id: WO-M2-06
status: PARTIAL
branch: codex/wo-m2-06-part1
commit: a4ce86fb
pr_url: pending founder review

result: >
  Part 1 parameterised coverage. Part 2 authored the seam-probe Blueprint. Coverage now reads the
  Blueprint under test instead of a hardcoded first-forge overlay.

calibration: >
  _room_coverage differs: 12 rooms for first-forge versus 2 rooms for seam-probe.

failure_before_repair: |
  export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  make proto && make check && .venv/bin/python -m pytest tests/test_engine_seam_differential.py -q
  All checks passed!
  lint-go: native/edge UNVERIFIED - it does not build. Generated code absent?
            run `make proto` (ADR-0012: the bindings are git-ignored).
  make: *** [Makefile:90: lint-go] Error 1

  Isolation showed the actual failure was the read-only default Go build cache:
  open /home/josh/.cache/go-build/...: read-only file system

repair_and_rerun: |
  mkdir -p /tmp/matrymlabs-codeforge-gocache
  GOCACHE=/tmp/matrymlabs-codeforge-gocache make proto && GOCACHE=/tmp/matrymlabs-codeforge-gocache make check
  ...
  lint-go: native/edge
  0 issues.
  lint-go: native/spine
  0 issues.
  Exception in thread "main" java.io.FileNotFoundException:
  /home/josh/.gradle/wrapper/dists/gradle-9.1.0-bin/...zip.lck (Read-only file system)
  make: *** [Makefile:80: lint-kotlin] Error 1

verification: |
  make check: not exit 0 on this host; Gradle fails before project tasks with
  `Could not determine a usable wildcard IP for this machine.`
  .venv/bin/python -m pytest tests/test_engine_seam_differential.py -q
  .............................                                            [100%]
  29 passed in 2.43s

files_touched:
  - kernel/engine_seam.py
  - content/seeds/seam-probe/items.yaml
  - content/seeds/seam-probe/jobs.yaml
  - content/seeds/seam-probe/rooms.yaml
  - content/seeds/seam-probe/world.yaml
  - content/seeds/seam-probe/world_overlay.json
  - tests/test_engine_seam_differential.py
  - work-orders/WO-M2-06/BENCH_REPORT.md

blockers: |
  Required `make check` cannot complete on this host because Gradle fails at startup with
  `Could not determine a usable wildcard IP for this machine.` The targeted differential suite is
  green. No divergence was observed between first-forge and seam-probe.

blueprint_finding: >
  seam-probe has its own world_overlay.json. Overlay generation and coverage are therefore
  Blueprint-specific and the selected seed must reach the coverage probe. This is recorded as a
  seam fact, not abstracted into a reusable Part.

reimplemented: none observed
recurrence: the parameterized coverage probe follows the existing differential-test shape; no second fleet consumer observed
generalizable: Blueprint-specific overlay selection and per-Blueprint differential reporting may be reusable, but no second real consumer yet
friction: the full gate depends on writable Go and Gradle caches; temporary GOCACHE resolved Go, but Gradle's wrapper cache remains read-only
pattern_shapes: parameterized probe, per-Blueprint verdict collection, data-only test Blueprint

pattern_screen:
  lane_echo: none observed in persistence, commands, events, transactions, world graph, or integration
  catalogue_match: Working Shelf Blueprint loader and validated-record loader consumed; no certified Blueprint/world-fixture Part exists
  recurrence_check: none observed; this is the first real second-Blueprint differential consumer
  verdict_note: first occurrence logged only; no extraction candidate opened
```
