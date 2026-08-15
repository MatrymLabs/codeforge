# WO-BP-2 BUILD SHEET

**Repo:** `codeforge`

## Scope

`codeforge` only. The nine SOURCE files that reconstruct the Blueprint root path independently, so
that afterwards exactly one place resolves it. **No directory moves in this order.**

## Invariant

**Behaviour is identical and the suite proves it by passing unchanged.** This order removes
duplicate knowledge of where Blueprints live; it does not change where they live. If a test has to
change, the consolidation altered behaviour and the order has failed.

```yaml
packet_id:            WO-BP-2
title:                One resolver for the Blueprint root, before anything moves
stream:               engine
repository:           codeforge
goal: >
  REWRITTEN 2026-08-15, after the first version was blocked by Codex for a defect in the order
  rather than in the work. That version said "git mv plus nine text sites" and was wrong by an
  order of magnitude, because its blast radius searched for the literal string `content/seeds` and
  the path is assembled from pathlib SEGMENTS in most places:

      SEED = Path(__file__).resolve().parent.parent / "content" / "seeds" / "aethryn"

  A literal grep cannot see that. Nine source files and twenty test files build the root that way,
  and `kernel/cast.py:35` defines its own second `SEEDS_ROOT` constant.

  So the move is not the problem. THE PROBLEM IS THAT THIRTY PLACES KNOW WHERE BLUEPRINTS LIVE.
  This order collapses the nine source ones onto the single resolver that already exists in
  kernel/world/seed.py, which BP-1 already taught to accept both the old and the new location.
  After this, moving the directory is a one-line change instead of a thirty-file sweep.

out_of_scope: >
  Do NOT move content/seeds/. That is BP-2b and it becomes trivial once this lands.
  Do NOT change kernel/world/seed.py. It already resolves both locations; this order makes other
  files USE it.
  Do NOT rename SeedError, SeedRecord, SEED_DIR, seed_root or seedlab; that is BP-3.
  Do NOT rewrite the twenty TEST files that build their own paths. They are fixtures pointing at
  known content, and changing them in the same commit as source would make the diff unreviewable.
  Log them for BP-2c and leave them.

file_allowlist:
  - kernel/cast.py
  - kernel/domains/hosted_recovery.py
  - kernel/domains/hosted_world.py
  - kernel/domains/world_compiler.py
  - kernel/world/exit_integrity.py
  - kernel/world/world_manifest.py
  - scripts/e2e_smoke.py
  - tools/census.py
  - tools/emit_map_world.py
  - tools/zone_density.py

blast_radius: |
  SEARCHED IN THREE FORMS, because the first version searched one and missed most of them.

  $ git grep -ln "content/seeds" -- '*.py'                      # literal
  10 files, of which 5 are source

  $ git grep -lnE '"content"\s*/\s*"seeds"' -- '*.py'          # pathlib segments
  29 files, of which 9 are source and 20 are tests

  $ git grep -lnE '/\s*"seeds"|"seeds"\s*/' -- '*.py'          # any joined segment
  45 files

  The nine SOURCE files in the allowlist are the union of forms 1 and 2 excluding tests. The
  twenty test files are deliberately deferred to BP-2c.

  Known duplicate to remove: kernel/cast.py:35 defines its own `SEEDS_ROOT`, a second copy of the
  constant at kernel/world/seed.py:50.

boundary: >
  This order OWNS the nine source files listed. It does NOT own kernel/world/seed.py, whose
  resolver is the thing being consumed rather than changed, and it does NOT own the twenty test
  files, which are BP-2c.

  If consuming the resolver creates an import cycle, that is a finding and the order is BLOCKED.
  `tools/` and `scripts/` importing from `kernel.world.seed` may be a layering question the
  import-linter contract answers; run `make imports` and believe it rather than working around it.

preconditions: >
    CHECK: file kernel/world/seed.py contains CODEFORGE_BLUEPRINTS_ROOT
    CHECK: file tools/census.py contains content
    CHECK: file kernel/cast.py contains SEEDS_ROOT

    Behavioural:
      export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
      make proto && make check                                    exit 0 before you start

contract_tests: >
  ASSERTION-LOCKED across the whole suite. The proof of this order is that every existing test
  passes UNCHANGED, including the twenty that build their own paths. Those tests are the evidence:
  they resolve the same directory a different way, so if consolidation changed anything they break.

definition_of_done:
  - "Each of the nine source files resolves the Blueprint root from kernel/world/seed.py rather
     than rebuilding it from `Path(...) / \"content\" / \"seeds\"`."
  - "kernel/cast.py no longer defines a second SEEDS_ROOT."
  - "`git grep -lnE '\"content\"\\s*/\\s*\"seeds\"' -- '*.py' | grep -v ^tests/` returns NOTHING.
     That command is the deciding test: it is the same search that was missed the first time, and
     if it still finds a source file the order is not done."
  - "The twenty test files are UNCHANGED and listed in the Bench Report for BP-2c."
  - "make imports passes; if the layering forbids tools/ importing kernel/, report it BLOCKED."
  - "make proto && make check green, whole suite, no test edited."

verification_command: |
  cd codeforge && make proto && make check && git grep -lnE '"content"\s*/\s*"seeds"' -- '*.py' | grep -v '^tests/' | wc -l

rollback: >
  git revert. Every file returns to building its own path, which is where it is today.

approval_gates: >
  none. Nothing moves and nothing is renamed.

size:                 medium

taint_class:          SAFE

# EXTRACTION CONTEXT
store_search_result: >
  Certified Tier and Working Shelf both searched for a path-resolution or single-source-of-truth
  Part. Nothing catalogued. The resolver being consolidated onto already exists in this repository.

parts_to_consume:     kernel/world/seed.py's SEEDS_ROOT and SEED_DIR. That is the point of the order.

watch_for: >
  Nine files independently knowing a filesystem layout is a duplication the pull rule cares about.
  If the consolidation reveals a tenth that the three searches missed, say which form hid it: that
  is the finding, and it is more valuable than the consolidation itself.
