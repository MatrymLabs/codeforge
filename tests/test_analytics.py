"""Test twin for parts.analytics -- SQL analytics proven equal to their Python reference.

Acceptance: on the same seeded archive, each SQL query returns exactly what the Python reference
computes (leaderboard, population spread, treasury), and the RANK() window function shares a rank on
ties and skips (the hostile case: equal level AND xp). Refusal / edge: an empty archive yields empty
standings, an empty spread, and a zeroed treasury with a safe mean (no divide-by-zero).

A Postgres-gated test proves the same window-function SQL runs on real PostgreSQL, not just SQLite,
so the "portable SQL" claim is demonstrated, not asserted. It skips unless POSTGRES_TEST_URL is set
(the dedicated Postgres CI job sets it); the rest run on in-memory SQLite in the base gate.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SqlSession
from sqlalchemy.pool import StaticPool

from parts.analytics import (
    Standing,
    WealthStats,
    leaderboard_py,
    leaderboard_sql,
    population_py,
    population_sql,
    read_rows,
    wealth_py,
    wealth_sql,
)
from parts.world.db import ArchiveBase, CharacterRow

# (name, level, xp, location, coins) -- hostile on purpose: (ashling, borin) tie on (level, xp) and
# so do (esk, fira); coins include a 0 (borin) so the treasury low is a real zero, not "unset".
_SEED = [
    ("ashling", 9, 500, "forge", 120),
    ("borin", 9, 500, "forge", 0),
    ("cade", 12, 100, "market", 50),
    ("dena", 12, 900, "market", 999),
    ("esk", 3, 10, "forge", 5),
    ("fira", 3, 10, "tunnel", 5),
]


def _seed_session(rows: list[tuple[str, int, int, str, int]]) -> SqlSession:
    # A private in-memory SQLite; StaticPool keeps the one connection (and its schema) for the test.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    ArchiveBase.metadata.create_all(engine)
    session = SqlSession(engine)
    session.add_all(
        CharacterRow(name=n, level=lvl, xp=xp, location=loc, coins=c)
        for (n, lvl, xp, loc, c) in rows
    )
    session.commit()
    return session


@pytest.fixture
def session() -> Iterator[SqlSession]:
    s = _seed_session(_SEED)
    yield s
    s.close()


def test_read_rows_loads_every_character(session):
    assert len(read_rows(session)) == len(_SEED)


def test_leaderboard_sql_equals_the_python_reference(session):
    rows = read_rows(session)
    assert leaderboard_sql(session, top=10) == leaderboard_py(rows, top=10)


def test_leaderboard_ranks_ties_the_way_sql_rank_does(session):
    # dena(12,900) is 1st, cade(12,100) 2nd; the 9/500 pair shares rank 3; the 3/10 pair shares 5
    standings = leaderboard_sql(session, top=10)
    assert [s.rank for s in standings] == [1, 2, 3, 3, 5, 5]
    assert standings[0] == Standing(rank=1, name="dena", level=12, xp=900)
    assert {s.name for s in standings if s.rank == 3} == {"ashling", "borin"}


def test_leaderboard_top_limits_both_sides_identically(session):
    rows = read_rows(session)
    assert leaderboard_sql(session, top=2) == leaderboard_py(rows, top=2)
    assert [s.name for s in leaderboard_sql(session, top=2)] == ["dena", "cade"]


def test_population_sql_equals_the_python_reference(session):
    rows = read_rows(session)
    assert population_sql(session) == population_py(rows)
    assert population_sql(session)[0] == ("forge", 3)  # the crowded room leads


def test_wealth_sql_equals_the_python_reference(session):
    rows = read_rows(session)
    assert wealth_sql(session) == wealth_py(rows)
    treasury = wealth_sql(session)
    assert treasury == WealthStats(players=6, total=1179, high=999, low=0)
    assert treasury.mean == pytest.approx(196.5)


def test_an_empty_archive_is_handled_by_both_sides():
    session = _seed_session([])
    try:
        assert leaderboard_sql(session) == leaderboard_py([]) == []
        assert population_sql(session) == population_py([]) == []
        empty = wealth_sql(session)
        assert empty == wealth_py([]) == WealthStats(players=0, total=0, high=0, low=0)
        assert empty.mean == 0.0  # no divide-by-zero on an empty treasury
    finally:
        session.close()


# --- portability: the same window-function SQL on real PostgreSQL ------------------------------

_PG_URL = os.environ.get("POSTGRES_TEST_URL", "").strip()


@pytest.mark.skipif(
    not _PG_URL, reason="set POSTGRES_TEST_URL to run the PostgreSQL analytics test"
)
def test_leaderboard_window_query_runs_on_postgresql():
    engine = create_engine(_PG_URL)
    ArchiveBase.metadata.drop_all(engine)
    ArchiveBase.metadata.create_all(engine)
    try:
        with SqlSession(engine) as write:
            write.add_all(
                CharacterRow(name=n, level=lvl, xp=xp, location=loc, coins=c)
                for (n, lvl, xp, loc, c) in _SEED
            )
            write.commit()
        with SqlSession(engine) as read:
            # RANK() OVER (...) must produce the same standings on Postgres as the Python reference
            assert leaderboard_sql(read, top=10) == leaderboard_py(read_rows(read), top=10)
            assert wealth_sql(read) == wealth_py(read_rows(read))
    finally:
        ArchiveBase.metadata.drop_all(engine)
        engine.dispose()
