# WO-BP-1 BUILD SHEET

**Repo:** `codeforge`

## Scope

`codeforge` only. The two files where the Blueprint path and both environment variables are
resolved, the one CLI helper that extracts the flag, and their tests. **No identifier is renamed
and no content moves.** This order only makes the new names work.

## Invariant

**Every old name keeps working, unchanged, and every new name resolves to the same Blueprint.**
This order adds; it removes nothing. A consumer running `FORGE_SEED=aethryn` today must still be
running it successfully after this lands, or the stage has failed at its only job.

```yaml
packet_id:            WO-BP-1
title:                The compatibility seam, so the rename cannot break a consumer
stream:               engine
repository:           codeforge
goal: >
  Principal Engineer ruling 2026-08-14: Seed is gone, Blueprint replaces it, contracts included.
  This is stage 1 of five and it is the stage that makes the other four reversible.

  Accept the new spelling everywhere the old one is read, and keep the old one working:

    FORGE_BLUEPRINT           beside FORGE_SEED
    CODEFORGE_BLUEPRINTS_ROOT beside CODEFORGE_SEEDS_ROOT
    --blueprint               beside --seed
    --blueprint-root          beside --seed-root
    content/blueprints/       resolved if present, else content/seeds/

  New name wins when both are set. Old name works silently for now; the deprecation warning is
  BP-4's job, not this order's, because a warning on day one trains people to ignore it before the
  replacement exists in any doc.

out_of_scope: >
  Do NOT move content/seeds/. That is BP-2 and it is safe only because this order lands first.
  Do NOT rename SeedError, SeedRecord, SeedSpec, SEED_DIR, seed_root or seedlab; those are BP-3.
  Do NOT emit deprecation warnings; that is BP-4. Do NOT remove any old name; that is BP-5 and it
  needs its own ruling. Do NOT touch dated records under reports/ or docs/, which stay as written.

file_allowlist:
  - kernel/world/seed.py
  - adapters/cli.py
  - tests/test_seed.py
  - tests/test_cli.py

blast_radius: |
  $ grep -n 'os.environ.get' kernel/world/seed.py
  44:  SEEDS_ROOT = Path(os.environ.get("CODEFORGE_SEEDS_ROOT", str(_default_seeds_root)))
  46:  SEED_NAME = os.environ.get("FORGE_SEED", DEFAULT_SEED)

  Those two lines are the entire environment contract. Everything else in the tree SETS these
  variables rather than reading them, so a reader-side alias covers every setter without touching
  one of them. Verified 2026-08-14 on origin/main.

  $ grep -n '\-\-seed' adapters/cli.py | head
  52:  """Extract `--seed <name>` from args (mutates in place). Returns the name or None."""

boundary: >
  This order OWNS kernel/world/seed.py and adapters/cli.py, for name resolution ONLY: the env
  lookups, the root path resolution, and the flag extraction helper. Everything else in both files
  stays as it is.

  content/seeds/ is NOT in the allowlist and does not move here. The database and character store
  are not in the allowlist and need no change: they persist room labels and item prototype labels,
  never a Blueprint path, which is why this migration is safe at all.

preconditions: >
    CHECK: file kernel/world/seed.py contains CODEFORGE_SEEDS_ROOT
    CHECK: file kernel/world/seed.py contains FORGE_SEED
    CHECK: file adapters/cli.py exists

    Behavioural:
      export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
      make proto && make check                                    exit 0 before you start

contract_tests:
  - tests/test_seed.py
  - tests/test_cli.py
  ASSERTION-LOCKED across the whole suite. The proof of this order is that every existing test
  passes UNCHANGED. If an assertion has to move, you have changed behaviour, and this order is
  defined as the change that does not.

definition_of_done:
  - "FORGE_BLUEPRINT is read, and FORGE_SEED still is. When both are set, the new name wins."
  - "CODEFORGE_BLUEPRINTS_ROOT is read, and CODEFORGE_SEEDS_ROOT still is, same precedence."
  - "The root resolves content/blueprints/ when that directory exists, and content/seeds/ when it
     does not. Today only the second exists, so today nothing changes."
  - "`--blueprint` and `--blueprint-root` are accepted, and `--seed` and `--seed-root` still are."
  - "A NEW test proves EQUIVALENCE, not merely presence: set the old name and the new name in
     separate runs and assert they resolve to the SAME Blueprint. A test that only checks the new
     name parses would pass even if it resolved to nothing."
  - "A NEW test proves precedence: both set, new wins."
  - "The whole suite passes with NO test edited, and `git diff --stat` touches only the allowlist."
  - "make proto && make check green."

verification_command: |
  cd codeforge && make proto && make check && git diff --stat origin/main...HEAD

rollback: >
  git revert the commit. Every old name was still working throughout, so a revert returns the tree
  to a state no consumer could tell apart from this one.

approval_gates: >
  none. This order cannot break a consumer: it only widens what is accepted.

size:                 small

taint_class:          SAFE
                      This repository's own configuration surface. No external material.

# EXTRACTION CONTEXT - read before implementing
store_search_result: >
  Certified Tier (hardware-store/catalog/): searched for a config-alias, deprecation-shim or
  settings-precedence Part. Nothing catalogued. Working Shelf (codeforge/catalog/parts.yaml): the
  typed-settings experiment PRT-0006 is the nearest shape and governs validation rather than
  aliasing. BOTH tiers searched, both empty.

parts_to_consume:     none

watch_for: >
  "Accept the new name, fall back to the old, prefer the new" is about to be written four times in
  one file. If it reads like four copies of one rule, say so: this is a Part candidate with a named
  second consumer already visible, because BP-4 has to add a deprecation warning to every one of
  the same four sites.
