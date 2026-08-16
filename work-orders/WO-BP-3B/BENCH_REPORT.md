# WO-BP-3B Bench Report

```yaml
packet_id: WO-BP-3B
status: COMPLETE
branch: codex/wo-bp-3b
base: 2ff5dd5ec384dcbe9f6f2bd29f94f4731a0c826a
implementation_head: e3b920c2

result: >
  Resumed after the Principal Engineer amended the allowlist to include scripts/**. Renamed the
  content-side SEED_DIR identifier to BLUEPRINT_DIR across all authorized callers, defined the
  compatibility alias SEED_DIR = BLUEPRINT_DIR, and added an identity regression test. kernel/seedlab/**
  was not changed and contains no SEED_DIR reference.

sync: |
  ship synced to 9e6cc59ddc93b1f984fe90fafe41b2181d8a74e8 by a non-destructive merge.
  codeforge synced to 2ff5dd5ec384dcbe9f6f2bd29f94f4731a0c826a by a non-destructive merge.
  git rev-list --count HEAD..origin/main
  0

preconditions: |
  git grep -l "SEED_DIR" -- kernel/seedlab/
  [no output]

  git grep -c "SEED_DIR" | awk -F: '{s+=$NF} END{print s+0}'
  77 before repair; 12 after repair, including historical Work Order text and the required alias/test references.

  git grep -n "SEED_DIR" -- registry/ Dockerfile Dockerfile.api deploy/ .github/
  [no output before and after repair]

changes: |
  BLUEPRINT_DIR is now the canonical content directory name in kernel/world/seed.py and all
  allowlisted callers, including scripts/aethryn_campaign.py. The module retains:

  BLUEPRINT_DIR = ...
  SEED_DIR = BLUEPRINT_DIR

  tests/test_seed.py asserts `SEED_DIR is BLUEPRINT_DIR`.

files_touched: |
  adapters/cli.py
  kernel/engine_seam.py
  kernel/world/{abilities,authored_towns,crafting,derived,doors,gearsets,items,job_ladder,jobs,npcs,professions,progression,quest,seed,world,zones}.py
  scripts/aethryn_campaign.py
  tests/{test_campaign,test_seed,test_seed_selection}.py
  work-orders/WO-BP-3B/BENCH_REPORT.md

verification: |
  Focused contract tests:
  pytest tests/test_seed.py tests/test_campaign.py tests/test_seed_selection.py -q
  121 passed, 3 skipped in 2.78s

  Full Proof Run:
  export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  make proto && make check
  PROOF_EXIT:0
  5310 passed, 54 skipped, 58 warnings in 155.31s
  Coverage: 93.46% (required: 85%)
  Contracts: 4 kept, 0 broken.
  Success: no issues found in 826 source files

  Additional gate:
  make lint typecheck
  LINT_TYPECHECK_EXIT:0

  Boundary checks:
  git diff --name-only -- kernel/seedlab/
  [no output]
  git grep -l "SEED_DIR" -- kernel/seedlab/
  [no output]
  git diff --check
  [no output]

  Failure before repair, preserved from the prior blocked attempt:
  The first mechanical trial found scripts/aethryn_campaign.py outside the then-current allowlist,
  so the trial was restored and reported BLOCKED. After the allowlist amendment, the same complete
  radius was migrated and the full Proof Run passed.

registry_docker_workflows: >
  No SEED_DIR reference in registry/, Dockerfile, Dockerfile.api, deploy/, or .github/ before or
  after the migration.

store_search: >
  Certified Tier (hardware-store/catalog/) was searched first for staged-rename and deprecation-
  alias Parts; no matching card was found. Working Shelf (codeforge/catalog/parts.yaml) was searched
  second for the same terms; no matching entry was found. No Part was consumed.

blockers: none

reimplemented: none; the existing BP-3A compatibility-alias shape was consumed as the approved pattern
recurrence: alias-then-migrate is the second occurrence after BP-3A; no Part was self-certified
generalizable: measure the complete identifier radius, verify exclusions, then migrate every allowlisted caller with an identity test
friction: the initial Build Sheet omitted scripts/**; the amended scope resolved the only content-side caller boundary

pattern_shapes: staged identifier rename, compatibility alias, allowlist boundary

pattern_screen:
  lane_echo: persistence, commands, events, world graph, and integration screened; no new runtime shape introduced
  catalogue_match: no Certified Tier or Working Shelf Part matched
  recurrence_check: alias-then-migrate is the second occurrence; the approved BP-3A pattern was reused
  verdict_note: first attempt correctly blocked at the stale allowlist; after amendment, migration completed with no SeedLab spill
```

IN PLAIN TERMS: The content loader and its callers now use the clearer Blueprint name, while old
imports still work through a direct alias. This keeps the rename reversible and leaves the separate
SeedLab subsystem untouched.
