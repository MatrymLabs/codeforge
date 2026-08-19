# ADR-0013: SQL analytics (a query language as the accelerator)

Status: Accepted (2026-07-28)

## Context

The polyglot organs so far reach for a systems language (Rust, C++, Go) or a contract format
(Protocol Buffers). But a whole class of questions the game will ask -- "who are the top ten?", "how
many stand in each room?", "what does the treasury hold?" -- are **set-shaped**, not loop-shaped. The
right language for those is **SQL**: a declarative query language that pushes aggregation, grouping,
ranking, and window functions into the database engine instead of dragging every row into a Python
loop.

The archive already persists characters through SQLAlchemy (SQLite by default, PostgreSQL via
`DATABASE_URL`), so the data is there. What was missing was the discipline for admitting SQL as a
first-class analytics language, the same way the other organs were admitted.

## Decision

Adopt SQL as the **analytics accelerator**, under the now-familiar shape (Python-first, identical
interface, parity, benchmark), with one property that makes it lighter than the earlier organs: **it
adds no dependency and needs no toolchain**. SQLite is stdlib; SQLAlchemy and the Postgres driver are
already in the stack. So the whole organ -- parity and benchmark -- runs in the base `make check` with
nothing to build.

1. **Python-first with a fallback.** Each analytic ships as a pure-Python reference over rows in
   memory (`leaderboard_py`, `population_py`, `wealth_py`) -- always correct, and the behaviour the SQL
   is proven against.
   This rule governs accelerating an existing capability; it does not choose the lane for a new Target Product, which follows the omnicode rule in `CLAUDE.md` where a Blueprint builds in whatever language its Target Product requires.
2. **A narrow, identical interface.** The SQL query (`*_sql`) returns the *same* typed result as the
   Python reference for the same data (`Standing`, a population spread, `WealthStats`).
3. **A parity test.** On a seeded archive, each SQL result is pinned equal to the Python reference,
   including the hostile case that exercises the query's semantics: the RANK() window function must
   share a rank on ties (equal level AND xp) and skip, exactly as the Python reference does.
4. **Committed benchmark evidence.** `benchmarks/bench_analytics.py` records the measured benefit at
   scale. Measured 2026-07-28 (Pi, 50k characters, in-memory SQLite): leaderboard **5.0x**, population
   **11.5x**, treasury **24.7x** faster than pulling the rows into Python and looping. Honest label:
   **verified improvement**, widening with the row count.
5. **Governance (reuse, not a new dependency).** This organ deliberately adds nothing: stdlib
   `sqlite3`, plus the already-approved SQLAlchemy and Postgres/`psycopg` extra. That is the correct
   answer under the dependency doctrine -- the right tool was already in the box.
6. **Portability, proven.** The SQL is standard (window functions, GROUP BY, aggregates), so it runs
   unchanged on SQLite AND PostgreSQL. A Postgres-gated test
   (`tests/test_analytics.py::test_leaderboard_window_query_runs_on_postgresql`) proves the
   window-function query on a real Postgres in the dedicated `postgres` CI job; it skips on SQLite so
   the base gate stays green.

## Consequences

- **Positive:** set-shaped reports are expressed in the language built for them, proven equal to a
  Python reference and measurably faster; the polyglot breadth now includes the data layer; and,
  unusually, the organ is fully exercised by the base gate (no optional toolchain) while still proving
  portability to a real analytics database.
- **Costs / risks:** two implementations of each report to keep in step (the parity test enforces it);
  raw SQL must stay dialect-portable (standard SQL only -- the Postgres job is the guard). Bounded by
  the Python reference, which is always correct and always available.
- **Exit:** delete `kernel/analytics.py` and its tests; nothing else depends on it. The persisted data
  and the ORM are untouched.
