# WO-BP-1 Bench Report

```yaml
packet_id: WO-BP-1
status: COMPLETE
branch: codex/wo-bp-1
commit: pending
pr_url: pending founder review

result: >
  Added the Blueprint compatibility seam. FORGE_BLUEPRINT and
  CODEFORGE_BLUEPRINTS_ROOT are accepted beside their old names, with the new
  spelling winning when both are set. The CLI accepts --blueprint and
  --blueprint-root beside --seed and --seed-root. The default root prefers
  content/blueprints/ when present and otherwise keeps content/seeds/.

store_search: >
  Certified Tier and Working Shelf were both searched for a configuration-alias,
  deprecation-shim, or settings-precedence Part. No matching Part was found;
  nothing was consumed.

failure_before_repair: |
  Focused proof after the initial test additions:
  pytest tests/test_seed.py tests/test_cli.py tests/test_seed_selection.py -q
  1 failed, 152 passed.
  test_reloading_the_seed_module_returns_it_to_the_default failed because a new
  CLI test leaked FORGE_BLUEPRINT into the existing reload test.

repair_and_rerun: |
  Scoped the new tests' environment setup through monkeypatch so the pre-existing
  environment is restored after each test.
  ruff format --check kernel/world/seed.py adapters/cli.py tests/test_seed.py tests/test_cli.py
  4 files already formatted
  ruff check kernel/world/seed.py adapters/cli.py tests/test_seed.py tests/test_cli.py
  All checks passed!
  pytest tests/test_seed.py tests/test_cli.py tests/test_seed_selection.py -q
  153 passed in 3.82s

verification: |
  export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  make proto && make check
  5300 passed, 54 skipped, 61 warnings in 151.54s
  Coverage: 93.46% (required: 85%)
  make check exited 0.
  git diff --check: clean.

files_touched:
  - kernel/world/seed.py
  - adapters/cli.py
  - tests/test_seed.py
  - tests/test_cli.py
  - work-orders/WO-BP-1/BENCH_REPORT.md

blockers: none

reimplemented: none observed; no existing Part matched the compatibility-alias seam
recurrence: alias fallback and precedence are repeated in the kernel and CLI consumers; BP-4 is the named second consumer
generalizable: configuration alias precedence is a candidate Part shape, but no extraction is warranted in this bounded order
friction: preserving the old identifiers and contracts requires parallel resolution paths; no test or gate friction remains

pattern_shapes: compatibility alias, new-name precedence, default-root fallback, CLI flag alias

pattern_screen:
  lane_echo: none observed in persistence, commands, events, transactions, world graph, or integration
  catalogue_match: no Certified Tier or Working Shelf Part matched this configuration-alias seam
  recurrence_check: repeated alias resolution is present in kernel and CLI; BP-4 is the named second consumer
  verdict_note: bounded compatibility logic is correct for this order; candidate extraction deferred until a reusable Part is approved
```
