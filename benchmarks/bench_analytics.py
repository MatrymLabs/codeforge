"""Benchmark: SQL analytics vs the Python reference on a large archive.

Evidence for the data-layer organ -- for set-shaped questions (rank, group, aggregate), SQL keeps
the work in the database engine, while the Python path must pull every row across the boundary.
Seeds N synthetic characters into an in-memory SQLite and times each report both ways. Frameless
(perf_counter + statistics). Run: `python benchmarks/bench_analytics.py [n_characters]`.

The SQL side is always available (SQLite is stdlib), so this benchmark always runs.
"""

from __future__ import annotations

import random
import statistics
import sys
import time
from collections.abc import Callable

from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session as SqlSession
from sqlalchemy.pool import StaticPool

from parts.analytics import (
    leaderboard_py,
    leaderboard_sql,
    population_py,
    population_sql,
    read_rows,
    wealth_py,
    wealth_sql,
)
from parts.world.db import ArchiveBase, CharacterRow


def _seed(session: SqlSession, n: int) -> None:
    rng = random.Random(7)
    locations = [f"room_{i}" for i in range(50)]
    rows = [
        {
            "name": f"p{i}",
            "level": rng.randint(1, 60),
            "xp": rng.randint(0, 100_000),
            "location": rng.choice(locations),
            "coins": rng.randint(0, 50_000),
        }
        for i in range(n)
    ]
    session.execute(insert(CharacterRow), rows)
    session.commit()


def _median_ms(fn: Callable[[], object], runs: int = 7) -> float:
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50_000
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    ArchiveBase.metadata.create_all(engine)
    session = SqlSession(engine)
    _seed(session, n)

    reports: dict[str, tuple[Callable[[], object], Callable[[], object]]] = {
        "leaderboard": (
            lambda: leaderboard_sql(session, 10),
            lambda: leaderboard_py(read_rows(session), 10),
        ),
        "population": (lambda: population_sql(session), lambda: population_py(read_rows(session))),
        "wealth": (lambda: wealth_sql(session), lambda: wealth_py(read_rows(session))),
    }

    print(f"analytics benchmark -- {n:,} characters (in-memory SQLite)\n")
    print(f"  {'report':>12}   {'sql(ms)':>9}   {'python(ms)':>11}   {'speedup':>8}")
    for name, (sql_fn, py_fn) in reports.items():
        s = _median_ms(sql_fn)
        p = _median_ms(py_fn)
        print(f"  {name:>12}   {s:>9.2f}   {p:>11.2f}   {p / s:>7.1f}x")
    session.close()

    print(
        "\nSQL keeps the aggregation in the engine; the Python path must pull every row across the"
    )
    print("boundary first. The gap widens with the row count -- the set-shaped question wants SQL.")


if __name__ == "__main__":
    main()
