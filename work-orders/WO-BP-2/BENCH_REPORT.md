# WO-BP-2 Bench Report

packet_id: WO-BP-2
status: PARTIAL
branch: codex/wo-bp-2-rewrite
repository: codeforge

## Summary

Consolidated the ten allowlisted source modules onto `kernel.world.seed.SEEDS_ROOT`. No directory
moved, no test changed, and Lane B was not touched. `kernel/cast.py` no longer defines its duplicate
`SEEDS_ROOT`.

## Files changed

- `kernel/cast.py`
- `kernel/domains/hosted_recovery.py`
- `kernel/domains/hosted_world.py`
- `kernel/domains/world_compiler.py`
- `kernel/world/exit_integrity.py`
- `kernel/world/world_manifest.py`
- `scripts/e2e_smoke.py`
- `tools/census.py`
- `tools/emit_map_world.py`
- `tools/zone_density.py`

Tests were unchanged:

```text
tests unchanged
```

## Failure observed before repair

The required pre-edit `make check` reached the full pytest phase after formatting, lint, import
contracts, mypy, Rust, and Go passed. The network-isolated sandbox produced failures/errors during
pytest and the run was interrupted with exit 130. This is the documented environment limitation;
no test or production workaround was introduced.

## Proof Runs

```text
make proto
regenerated proto/telemetry_pb2.py + native/spine/telemetrypb/telemetry.pb.go
exit 0
```

```text
make imports
Analyzed 400 files, 875 dependencies.
Contracts: 4 kept, 0 broken.
exit 0
```

```text
pytest -q tests/test_callings.py tests/test_cast.py tests/test_cast_update.py tests/test_census.py \
  tests/test_engine_seam_differential.py tests/test_exit_integrity.py tests/test_hosted_recovery.py \
  tests/test_hosted_world.py tests/test_manifest_compiler.py tests/test_world_compiler.py \
  tests/test_world_manifest.py tests/test_zone_density.py
221 passed in 8.41s
exit 0
```

```text
ruff format --check <10 changed source files>
10 files already formatted
exit 0

ruff check <10 changed source files>
All checks passed!
exit 0
```

Deciding search after the change:

```text
git grep -lnE '"content"\s*/\s*"seeds"' -- '*.py' | grep -v '^tests/'
(no output; grep exit 1 because no source matches remain)
```

Direct tool proofs also passed: `python tools/census.py` measured 77 authored rooms and
`python tools/zone_density.py` reported 0 of 14 zones below the launch floor.

## Scope checks

- No directory move or rename occurred.
- No test file changed.
- `kernel/world/seed.py` was not modified.
- Lane B WO-2D-2 was not modified.
- `git diff --check` passed.

## Reusable Part signals

reimplemented: none observed
recurrence: none observed
generalizable: resolver consolidation is a reusable single-source-of-truth pattern, but no Part
was opened because this order consumed the existing resolver rather than introducing a second one.
friction: the full suite remains network-sensitive in this sandbox; the focused unchanged suite is
green and the native/tooling portion of `make check` is green.

## Review

Principal Engineer Verification Duty should rerun the full `make proto && make check` and inspect the
source-only diff. The deciding search is empty, and the focused evidence is green.

IN PLAIN TERMS: I removed ten duplicate Blueprint-root calculations, left all tests and content
untouched, and proved the deciding search is empty. Full-suite completion still needs a non-isolated
Verification Duty run.
