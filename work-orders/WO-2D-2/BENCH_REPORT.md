# WO-2D-2 Bench Report

packet_id: WO-2D-2
status: READY_FOR_VERIFICATION
branch: codex/wo-2d-2
repository: codeforge

## Summary

`Session` now carries an engine-native `position`. The existing `location` constructor argument is
still accepted at all existing call sites, but reads through `engine.room_of(position)` and writes
through `engine.place(room)`. Every session defaults to a fresh `Engine0D`; no module-level engine
singleton was introduced.

## Files changed

- `kernel/world/session.py`
- `tests/test_session.py`
- `work-orders/WO-2D-2/BENCH_REPORT.md`

`tests/test_engine_seam_differential.py` was inspected and unchanged. No consumer, persistence,
gateway, engine-seam, or differential-battery source file was edited.

## Baseline before repair

The required baseline ran from `origin/main` before the session change. `make proto` passed. The
unchanged repository gate passed formatting, Ruff, Rust and Go lint, import contracts, and reached
mypy, then the full pytest phase reproduced the sandbox failure pattern around 36-47 percent and
was interrupted with exit 130. The visible failures were pre-existing environment failures, not
Session behavior failures.

Representative baseline failure:

```text
pytest -n auto --cov=kernel --cov=adapters --cov=content --cov=forge --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=85
...
F................E...............E......EEE......EEEE......EEEEE...
exit 130
```

## Implementation

The dataclass retains `location: str` as its public typed field and constructor parameter. Runtime
access is installed as a descriptor after class creation so existing consumers continue to typecheck
as string room-label consumers while the value is derived from the injected engine. Construction
stages the initial room until the dataclass has assigned the engine, then calls `engine.place()`.
Assignment after construction calls `engine.place()` directly.

The deciding test injects an engine whose `room_of()` deliberately changes `forge` to
`derived:forge`. It also assigns `courtyard`, asserts the opaque position is replaced, and verifies
the derived location follows the new position. This proves the engine is in the path rather than
merely adding an unused field.

## Proof Runs

```text
pytest -q tests/test_session.py tests/test_engine_seam_differential.py
42 passed in 1.18s
exit 0
```

```text
pytest -q tests/test_session.py tests/test_engine_seam_differential.py tests/test_characters.py tests/test_travel.py tests/test_ranks.py tests/test_creator_workshop.py tests/test_gmcp.py tests/test_game_session.py
171 passed in 2.57s
exit 0
```

```text
ruff check kernel/world/session.py tests/test_session.py tests/test_engine_seam_differential.py
All checks passed!
exit 0

mypy kernel/world/session.py tests/test_session.py tests/test_engine_seam_differential.py
Success: no issues found in 3 source files
exit 0
```

Post-fix `make proto` passed. Post-fix `make check` passed formatting, Ruff, Rust and Go lint,
import contracts, full mypy (`824 source files`, no errors), Rust and Go type checks, and reached
the unchanged full pytest phase. That phase reproduced failures/errors around 36-45 percent and
was interrupted with exit 130.

The broader boundary run including `tests/test_gateway.py` produced 185 passes, 41 socket setup
errors, and one TLS socketpair failure because this sandbox denies socket operations. The gateway
errors are environment failures; the non-network boundary set above is green.

## Scope checks

- `git diff --stat` touches only `kernel/world/session.py`, `tests/test_session.py`, and this report.
- `tests/test_engine_seam_differential.py` remains unchanged.
- The 123 consumer call sites remain unchanged.
- Character persistence remains label-based and its tests pass.
- No default-engine accessor or module-level singleton was added.
- `git diff --check` passed.

## Reusable Part signals

reimplemented: none observed; the existing Engine Protocol was consumed directly.
recurrence: the engine seam previously had no Session consumer, and the first implementation shape
lost the typed location contract under mypy. The correction kept the public contract while wiring
the runtime path.
generalizable: a compatibility-preserving descriptor can place a new domain seam behind an existing
typed constructor and consumer surface when a mechanical migration is explicitly out of scope.
friction: the full sandbox suite cannot open sockets, so gateway tests and the full pytest lane do
not provide a clean local verdict; the boundary tests that do not require sockets are green.

## Review

Principal Engineer Verification Duty should rerun `make proto && make check` in a non-isolated
environment, inspect the two-file source/test diff, and confirm no consumer edits are required. No
merge was performed.

IN PLAIN TERMS: sessions now carry opaque engine positions while every old caller still reads and writes room labels. The engine injection is proven by a relabeling test; focused boundary tests and all static gates are green, but this sandbox cannot provide a clean full-suite or gateway verdict.
