# WO-BP-2B Bench Report

```yaml
packet_id: WO-BP-2B
status: COMPLETE
branch: codex/wo-bp-2b
base: c67e10950e4a19f4069530f3ef698928ec73a76c
commits: f08391da (move/cast); registry pointer commit pending

result: >
  Re-measured the radius on origin/main before moving anything, then performed the
  allowlisted git mv and repointed the measured test/prose references. The move is
  byte-preserving and the resolver selects content/blueprints/ without changing
  kernel/world/seed.py. The widened allowlist permitted the two cast copier basename
  repairs, and the second widening permitted the curated Registry path pointers. All
  stale content/seeds references owned by this order now resolve to content/blueprints/.

store_search: >
  Certified Tier (hardware-store/catalog/) and Working Shelf (codeforge/catalog/parts.yaml)
  were both searched for directory-rename, path-migration, reference-repoint, and blueprint
  migration Parts. No matching Part was found; nothing was consumed.

pre_move_measurement: |
  git grep -lE 'content/seeds|"content"\s*/\s*"seeds"' | wc -l
  44

  git grep -lE '"content"\s*/\s*"seeds"' -- '*.py'
  tests/test_abilities.py
  tests/test_authored_towns.py
  tests/test_bounties.py
  tests/test_cast.py
  tests/test_cli.py
  tests/test_combat.py
  tests/test_crafting_materials.py
  tests/test_delve.py
  tests/test_emit_map_world.py
  tests/test_gather.py
  tests/test_hosted_recovery.py
  tests/test_hosted_world.py
  tests/test_job_ladder.py
  tests/test_journey_aethryn.py
  tests/test_manifest_compiler.py
  tests/test_professions.py
  tests/test_quest.py
  tests/test_townsfolk.py
  tests/test_travel.py
  tests/test_world_manifest.py

  git grep -lE 'content/seeds|"content"\s*/\s*"seeds"' -- '*.py' | grep -v ^tests/
  adapters/cli.py
  kernel/domains/hosted_world.py
  kernel/world/world_manifest.py
  tools/emit_map_world.py

  Counts: 44 overall, 20 segmented-path Python test files, 4 non-test prose-only modules.
  Preconditions were present: content/seeds existed; kernel/world/seed.py contained both
  _default_blueprints_root and _default_seeds_root; make proto && make check was green on
  c67e1095 before this order began.

failure_before_repair: |
  After the move and the measured path repoints, the contract tests passed:
  .venv/bin/pytest --no-cov -q tests/test_seed.py tests/test_abilities.py tests/test_authored_towns.py
  205 passed in 3.76s

  The remaining literal-path tests were then run before any further repair:
  .venv/bin/pytest --no-cov -q tests/test_callings.py tests/test_engine_seam_differential.py tests/test_census.py tests/test_hosted_world.py tests/test_world_manifest.py
  7 failed, 87 passed in 2.76s
  The seven failures were real repository paths in test_callings.py and
  test_engine_seam_differential.py. Their references were repointed; fixture-local paths and
  historical comments were left unchanged.

repair_and_rerun: |
  The seven stale runtime references were repointed and the targeted set passed:
  .venv/bin/pytest --no-cov -q tests/test_callings.py tests/test_engine_seam_differential.py tests/test_census.py tests/test_hosted_world.py tests/test_world_manifest.py
  94 passed in 2.18s

  Ruff formatting was then applied to the two long path expressions and the four allowlisted
  prose-only modules. The first full check reached the suite but failed as follows:
  18 failed, 5290 passed, 54 skipped, 58 warnings in 244.34s
  Coverage: 93.40% (required: 85%)

  Twelve failures were the cast dependency:
  tests/test_cast.py failed with FileExistsError because kernel/cast.py:347 ignored only
  the literal basename "seeds" while kernel/cast.py:357 copied the resolved SEEDS_ROOT,
  now content/blueprints/, after the content layer had already copied that directory.
  The widened allowlist now permits the minimal fix, applied in both kernel/cast.py and its
  twin kernel/cast_update.py. The focused rerun passed:
  .venv/bin/pytest --no-cov -q tests/test_cast.py tests/test_cast_update.py
  96 passed in 2.13s

  The remaining six full-gate failures are live registry/evidence failures, not cast failures.
  registry/designations/rooms.json still contains 11 records naming
  content/seeds/first-forge/rooms.yaml. registry/** is outside the current allowlist, so those
  paths were not changed. The isolated proof reproduced the finding:
  .venv/bin/pytest --no-cov -vv tests/test_evidence_gate.py tests/test_frameup.py tests/test_qualitygate.py tests/test_registry.py
  6 failed, 63 passed in 7.97s

  Post-cast full proof:
  export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  make proto && make check
  6 failed, 5302 passed, 54 skipped, 74 warnings in 154.98s
  Coverage: 93.49% (required: 85%). Ruff, import contracts, mypy, Rust, and Go gates passed;
  all cast failures are gone. The six failures are the same 11 stale registry records.

final_leg: |
  Independent measurement before the final repair:
    rooms.json: 18 stale file pointers (12 first-forge, 6 haven-city)
    modules.json: 1 prose mention
  The normalized JSON structure comparison was True: no record was added, removed, reclassified,
  or re-described. Only the directory prefix changed in those 19 strings.

  .venv/bin/pytest --no-cov -q tests/test_registry.py tests/test_evidence_gate.py tests/test_frameup.py tests/test_qualitygate.py
  targeted registry/self-audit tests passed.

  export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
  make proto && make check
  make proto exit 0; make check exit 0
  5308 passed, 54 skipped, 58 warnings in 148.87s
  Coverage: 93.46% (required: 85%).

verification: |
  git diff --cached --summary -M
  Every content file is reported as a 100% rename from content/seeds/ to content/blueprints/.
  The resolver code was read after the move:
    _default_world_root = (
        _default_blueprints_root if _default_blueprints_root.is_dir() else _default_seeds_root
    )
  With content/blueprints/ present, the preferred branch is selected. content/seeds/ is absent
  and content/blueprints/ is present. kernel/world/seed.py has no diff.

files_touched: |
  Allowlisted content/** move, tests/** path references, the four named prose-only modules,
  kernel/cast.py, kernel/cast_update.py, registry/designations/rooms.json,
  registry/designations/modules.json, and this report. No source outside the allowlist was changed.

blockers: none

reimplemented: none observed; no Certified Tier or Working Shelf Part matched this directory move
recurrence: directory moves with compatibility fallbacks recur, and basename filters can evade literal/path-segment searches
generalizable: path migration review needs a basename/filter search in addition to full-path spellings
friction: the measured radius required four distinct reference classes; the final Registry class was corrected with pointer-only edits

pattern_shapes: directory move, compatibility fallback, path-segment repoint, basename filter

pattern_screen:
  lane_echo: integration and world-graph path consumers were screened; cast generation is the integration finding
  catalogue_match: no Certified Tier or Working Shelf Part matched
  recurrence_check: this is the second compatibility-fallback directory shape; the third instance should become a Part
  verdict_note: COMPLETE; all four reference classes were corrected within the amended allowlist
```

IN PLAIN TERMS: The folder moved cleanly, both cast copiers exclude `blueprints`, and the 18 Registry
file pointers plus one prose pointer now name the moved directory. Records were not otherwise
changed, unrelated `.seedlab/seeds` stores were untouched, and the full gate is green.
