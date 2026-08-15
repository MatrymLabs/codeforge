# WO-2D-2B Bench Report

packet_id: WO-2D-2B
status: READY_FOR_VERIFICATION
branch: codex/wo-2d-2b
repository: codeforge

## Summary

Moved the game-facing Engine contract from the platform seam instrument into
`kernel/world/engine.py`. `kernel/engine_seam.py` re-exports `Engine`, `Engine0D`, and
`NodePosition`, so existing imports remain compatible while `kernel/world/session.py` consumes the
contract from the World Package. The differential harness and its tests remain in place.

## Files changed

- `kernel/world/engine.py`
- `kernel/engine_seam.py`
- `kernel/world/session.py`
- `tests/test_engine.py`
- `registry/designations/modules.json`
- `work-orders/WO-2D-2B/BENCH_REPORT.md`

`tests/test_engine_seam_differential.py` and `kernel/world_boundary.py` were not edited.

## Failure before repair

The pre-move baseline was the unmerged WO-2D-2 branch, where the Session implementation imported
`kernel.engine_seam`. Its required checks had already passed formatting, Ruff, import contracts,
native lint, and mypy, but the unchanged full pytest lane reproduced sandbox failures/errors and was
interrupted with exit 130. This order changes declarations and import paths only; no behavior
failure was observed before the move.

## Move details

`NodePosition`, `Engine`, and `Engine0D` now live in `kernel/world/engine.py` with a World Package
CARD docstring. The platform seam imports and re-exports them, while retaining `ChunkPosition`,
`Engine2DStub`, `Engine2D`, the battery, probes, saboteurs, and differential runner. Session now
imports `Engine` and `Engine0D` from `kernel.world.engine`.

The new module has a test twin and designation `MOD-04.162`. No logic, method body, default, or
message was changed.

## Proof Runs

```text
python -c "from kernel.world_boundary import world_boundary_gaps, world_import_violations; print(world_boundary_gaps(), world_import_violations())"
[] {}
exit 0
```

```text
pytest -q tests/test_engine.py tests/test_engine_seam_differential.py tests/test_world_boundary.py tests/test_session.py
53 passed in 2.93s
exit 0
```

```text
make repo-integrity
registry validates:   yes
world boundary:       clean (platform -> world, one way)
exit 0
```

```text
make check
ruff format --check .
1114 files already formatted
ruff check .
All checks passed!
Contracts: 4 kept, 0 broken.
Success: no issues found in 826 source files
typecheck-rust: native/codeforge_nav
typecheck-go: native/edge
typecheck-go: native/spine
pytest ...
... F ... E ...
exit 130
```

The full gate's formatting, Ruff, import contracts, mypy, Rust and Go lint/type checks all passed.
The unchanged pytest lane again encountered the known sandbox failures/errors around 36-41 percent
and was interrupted. The focused proof and boundary gate are green.

## Scope checks

- `kernel/world_boundary.py` was not edited.
- `tests/test_engine_seam_differential.py` was not edited.
- `kernel/world/engine.py` has no platform import.
- No `kernel/world/*.py` module imports `kernel.engine_seam` after the move.
- The differential-only `ChunkPosition`, `Engine2DStub`, and `Engine2D` stayed in `engine_seam.py`.
- `git diff --check` passed.

## Reusable Part signals

reimplemented: none observed; the existing Engine contract moved without logic changes.
recurrence: this is a layering fault caused by an order that put a World Package consumer on a
platform import path. No second world-to-platform engine import appeared during the screen.
generalizable: keep domain contracts in the domain package and let platform instruments import them;
compatibility re-exports make a contract move reviewable without widening callers.
friction: the sandbox's unchanged full pytest lane cannot produce a clean verdict because of its
socket/network restrictions, while static, boundary, registry, and focused behavioral checks pass.

## Review

Principal Engineer Verification Duty should verify this branch together with WO-2D-2, rerun
`make proto && make check` in a non-isolated environment, and confirm the re-export compatibility.
The two branches must be integrated only in the stated order. No merge was performed.

IN PLAIN TERMS: the engine contract now belongs to the game, Session no longer reaches into the platform, and the seam instrument still works through compatibility re-exports. The boundary proof is empty and focused tests are green; full-suite completion still needs a non-isolated verifier.
