# WO-BP-3B Bench Report

```yaml
packet_id: WO-BP-3B
status: BLOCKED
branch: codex/wo-bp-3b
base: 3cb6b78a1faa03e1679f4138a8564568511bd643

result: >
  The required precondition holds and BP-3A is an ancestor of origin/main. The measured
  SEED_DIR radius is 71 occurrences, but one caller is scripts/aethryn_campaign.py, outside
  this Build Sheet's file allowlist. I stopped before applying the rename and restored the
  working tree. No source or test file was changed, and no alias was added.

precondition: |
  git grep -l "SEED_DIR" -- kernel/seedlab/
  [no output]

  git merge-base --is-ancestor 9af2ae7b origin/main; echo BP3A_IN_MAIN:$?
  BP3A_IN_MAIN:0

  BP-3A alias shape verified at 9af2ae7b:
  class BlueprintError(Exception):
  SeedError = BlueprintError

blast_radius: |
  git grep -c "SEED_DIR" | awk -F: '{s+=$NF} END{print s+0}'
  71

  git grep -l "SEED_DIR" -- kernel/seedlab/
  [no output]

  Files containing the identifier:
  adapters/cli.py
  kernel/engine_seam.py
  kernel/world/abilities.py
  kernel/world/authored_towns.py
  kernel/world/crafting.py
  kernel/world/derived.py
  kernel/world/doors.py
  kernel/world/gearsets.py
  kernel/world/items.py
  kernel/world/job_ladder.py
  kernel/world/jobs.py
  kernel/world/npcs.py
  kernel/world/professions.py
  kernel/world/progression.py
  kernel/world/quest.py
  kernel/world/seed.py
  kernel/world/world.py
  kernel/world/zones.py
  scripts/aethryn_campaign.py
  tests/test_campaign.py
  tests/test_seed.py
  tests/test_seed_selection.py

allowlist_finding: |
  scripts/aethryn_campaign.py contains SEED_DIR, but scripts/** is absent from the allowlist.
  The authorized paths include kernel/world/**, kernel/engine_seam.py, adapters/**, tools/**,
  tests/**, and this report. The script is a content-side caller, not a SeedLab occurrence, but
  it cannot be renamed under this order. I did not widen the allowlist or leave a partial rename.

registry_docker_workflows: |
  git grep -n "SEED_DIR" -- registry/ Dockerfile Dockerfile.api deploy/ .github/
  [no output]

store_search: >
  Certified Tier (hardware-store/catalog/) was searched first for staged-rename and
  deprecation-alias Parts; no matching card was found. Working Shelf (codeforge/catalog/parts.yaml)
  was searched second for the same terms; no matching entry was found. No Part was consumed.

verification: |
  export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  make proto && make check
  make proto exit 0; make check exit 0
  5308 passed, 54 skipped, 58 warnings in 146.12s
  Coverage: 93.46% (required: 85%)

  After stopping and restoring the mechanical trial:
  git diff --stat
  [no output]
  git diff --check
  [no output]

blockers: >
  Principal Engineer decision required: widen the allowlist to include scripts/aethryn_campaign.py,
  or leave this caller for a follow-up order. The rename cannot satisfy its measured 71-occurrence
  boundary while that authorized path is excluded.

reimplemented: none; the rename was not applied
recurrence: the alias-then-migrate shape recurs from BP-3A, but this order stopped at an allowlist boundary
generalizable: measure the complete identifier radius before a mechanical rename and compare every path to the allowlist
friction: the scoped search found one content caller in scripts/** after the sheet's broad-looking boundary was read literally

pattern_shapes: staged identifier rename, compatibility alias, allowlist boundary

pattern_screen:
  lane_echo: persistence, commands, events, world graph, and integration were screened; no source change was made
  catalogue_match: no Certified Tier or Working Shelf Part matched
  recurrence_check: alias-then-migrate is the second occurrence; no Part was self-certified
  verdict_note: BLOCKED at the authorized file boundary; no partial rename was left behind
```

IN PLAIN TERMS: I measured the rename and found one legitimate content caller in a folder this order does not allow me to edit. I stopped before changing code, so the next decision is simply whether that script belongs in this rename or in its own order. The key concept is blast-radius discipline: the measured thing must fit the approved file boundary before a bulk rename begins.
