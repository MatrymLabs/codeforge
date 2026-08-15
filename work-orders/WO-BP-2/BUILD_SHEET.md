# WO-BP-2 BUILD SHEET

**Repo:** `codeforge`

## Scope

`codeforge` only. The content directory moves from `content/seeds/` to `content/blueprints/`, and
the handful of code and config sites that name that path in a way git will not follow are updated.

## Invariant

**The move is a rename, never an edit.** Every file under the directory arrives byte-identical, and
`git log --follow` still reaches its history. A Blueprint whose contents changed during a move is
two changes wearing one commit, and nobody reviewing it can tell which broke something.

```yaml
packet_id:            WO-BP-2
title:                Move the content: content/seeds becomes content/blueprints
stream:               engine
repository:           codeforge
goal: >
  BP-2 of five. BP-1 landed as #977 and already resolves `content/blueprints/` when that directory
  exists and `content/seeds/` when it does not, so this order is a `git mv` that flips which branch
  of that resolution is taken. Nothing else in the seam has to change.

  Then fix the sites that name the path as text, which git cannot follow: docstrings, a hardcoded
  Path in the exit-integrity check, and a line of authored world topology.

out_of_scope: >
  Do NOT edit the CONTENT of any moved file. Not a room label, not a description, not a whitespace
  fix, however tempting while the file is open. A rename commit whose files also changed is
  unreviewable.
  Do NOT rename SeedError, SeedRecord, SeedSpec, SEED_DIR, seed_root or seedlab; those are BP-3.
  Do NOT remove the `content/seeds/` fallback from kernel/world/seed.py; that is BP-5 and it needs
  its own ruling. A consumer with an old checkout still resolves through it.
  Do NOT emit deprecation warnings; that is BP-4.

file_allowlist:
  - content/seeds/                        (moved, not edited)
  - content/blueprints/                   (its destination)
  - adapters/cli.py                       (docstring path text only)
  - kernel/domains/hosted_world.py        (docstring path text only)
  - kernel/world/exit_integrity.py        (a hardcoded Path)
  - kernel/world/world_manifest.py        (docstring path text only)
  - tools/emit_map_world.py               (comment path text only)
  - content/world/topology.yaml           (a documentation line)
  - tests/                                (the 5 files naming the path)

blast_radius: |
  $ git ls-files 'content/seeds/*' | wc -l
  103        files moved, byte-identical

  $ git grep -n "content/seeds" -- '*.py' '*.yaml' '*.yml' '*.toml' Makefile | grep -v '^tests/'
  adapters/cli.py:409                 docstring
  adapters/cli.py:427                 help text, ALREADY says "content/blueprints/ or content/seeds/"
  content/world/topology.yaml:51      documentation line
  kernel/domains/hosted_world.py:8    docstring
  kernel/domains/hosted_world.py:79   docstring
  kernel/world/exit_integrity.py:118  HARDCODED Path, the one that actually breaks
  kernel/world/exit_integrity.py:119  HARDCODED Path, the one that actually breaks
  kernel/world/world_manifest.py:198  docstring
  tools/emit_map_world.py:588         comment

  $ git grep -ln 'content/seeds' -- 'tests/*' | wc -l
  5

  Measured 2026-08-14 on origin/main. Only exit_integrity.py:118-119 are executable path
  references; everything else in that list is prose that names the path. The distinction matters:
  the executable two break the moment the directory moves, and the rest are merely wrong.

boundary: >
  This order OWNS the content directory and the nine text sites above. It does NOT own
  kernel/world/seed.py: BP-1 already made that file resolve both locations, and this order is
  correct precisely because it does not have to touch it. If you find yourself needing to edit
  kernel/world/seed.py to make the move work, STOP and file BLOCKED, because that means BP-1's
  seam is not doing what #977 verified it does.

preconditions: >
    CHECK: file kernel/world/seed.py contains CODEFORGE_BLUEPRINTS_ROOT
    CHECK: file content/seeds/first-forge/world.yaml exists
    CHECK: file content/blueprints/first-forge/world.yaml absent

    Behavioural:
      export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
      make proto && make check                                    exit 0 before you start

contract_tests: >
  ASSERTION-LOCKED across the whole suite. Five test files name the path and may have that STRING
  updated; no assertion may change meaning. If a test has to assert something different after a
  directory rename, the rename changed behaviour and this order has failed its invariant.

definition_of_done:
  - "`git mv content/seeds content/blueprints`, so history follows. A delete-and-add loses
     `git log --follow` for 103 files and is not acceptable."
  - "Every moved file byte-identical. Prove it: `git diff -M --stat origin/main...HEAD` shows
     renames with no content change."
  - "kernel/world/exit_integrity.py:118-119 point at the new path. These are the only two
     EXECUTABLE references; everything else in the list is prose."
  - "The seven prose sites name the new path."
  - "kernel/world/seed.py is NOT modified. BP-1 already resolves both."
  - "The old path still resolves for a consumer who sets CODEFORGE_SEEDS_ROOT explicitly, because
     BP-1's fallback is untouched."
  - "make proto && make check green, and the whole suite passes."

verification_command: |
  cd codeforge && make proto && make check && git diff -M --stat origin/main...HEAD | tail -5

rollback: >
  git revert. The directory moves back, and BP-1's resolution follows it without further change,
  which is the property that makes this stage safe.

approval_gates: >
  none. BP-1 made this reversible.

size:                 small

taint_class:          SAFE

# EXTRACTION CONTEXT
store_search_result: >
  Certified Tier and Working Shelf both searched for a content-migration or path-rename Part.
  Nothing catalogued in either. This is a one-off directory move.

parts_to_consume:     none

watch_for: >
  If `git mv` on 103 files produces anything other than pure renames in `git diff -M`, say what
  changed and why before committing. A rename that git records as delete-plus-add loses the
  history of every Blueprint in the tree.
