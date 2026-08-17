"""CARD: analytics -- SQL analytics over the character archive (leaderboard, spread, wealth).

Some questions are set-shaped, not loop-shaped: "who are the top ten?", "how many stand in each
room?", "what does the treasury look like?". Those belong to SQL -- a declarative query language
that pushes the aggregation into the database engine -- not to a Python for-loop. This is the
polyglot spine's data-layer organ: SQL where SQL is the right tool.

Each analytic has TWO implementations with an identical result:
- a **Python reference** over rows already in memory (`*_py`) -- always correct, the fallback, and
  the thing the SQL is proven against;
- a **SQL query** run on the archive (`*_sql`) -- the accelerator, faster at scale, and portable:
  the same standard SQL (window functions, GROUP BY, aggregates) runs on the default SQLite AND on
  PostgreSQL (the dedicated CI job proves the window-function query on real Postgres).

It adds no dependency: SQLite is stdlib, SQLAlchemy and the Postgres driver are already present, so
the whole organ -- parity and benchmark -- runs in the base `make check` with nothing to build.

Inputs:  an open archive Session (SQL side) or a sequence of AnalyticsRow (Python side).
Outputs: ranked standings / a population spread / treasury stats -- identical from either side.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session as SqlSession

from kernel.world.db import CharacterRow


@dataclass(frozen=True)
class AnalyticsRow:
    """The analytics view of a character: only the columns the reports read."""

    name: str
    level: int
    xp: int
    location: str
    coins: int


@dataclass(frozen=True)
class Standing:
    """One leaderboard line: competition rank (ties share a rank), then who and their score."""

    rank: int
    name: str
    level: int
    xp: int


@dataclass(frozen=True)
class WealthStats:
    """The treasury at a glance. mean is derived so it never disagrees between SQL and Python."""

    players: int
    total: int
    high: int
    low: int

    @property
    def mean(self) -> float:
        return self.total / self.players if self.players else 0.0


def read_rows(session: SqlSession) -> list[AnalyticsRow]:
    """Load the analytics columns for every archived character (input to the Python reference)."""
    cols = select(
        CharacterRow.name,
        CharacterRow.level,
        CharacterRow.xp,
        CharacterRow.location,
        CharacterRow.coins,
    )
    return [AnalyticsRow(*row) for row in session.execute(cols).all()]


# --- leaderboard: the ranked standings (a window function, RANK() -- ties share a rank) ---------

_LEADERBOARD_SQL = text(
    """
    SELECT name, level, xp,
           RANK() OVER (ORDER BY level DESC, xp DESC) AS standing
    FROM characters
    ORDER BY level DESC, xp DESC, name ASC
    LIMIT :top
    """
)


def leaderboard_sql(session: SqlSession, top: int = 10) -> list[Standing]:
    rows = session.execute(_LEADERBOARD_SQL, {"top": top}).all()
    return [Standing(rank=int(r.standing), name=r.name, level=r.level, xp=r.xp) for r in rows]


def leaderboard_py(rows: list[AnalyticsRow], top: int = 10) -> list[Standing]:
    """RANK() in Python: order by (level desc, xp desc, name asc); a new (level, xp) takes the rank
    of its 1-based position, so ties share a rank and the next distinct score skips -- like SQL."""
    ordered = sorted(rows, key=lambda r: (-r.level, -r.xp, r.name))
    standings: list[Standing] = []
    prev_score: tuple[int, int] | None = None
    rank = 0
    for index, row in enumerate(ordered):
        score = (row.level, row.xp)
        if score != prev_score:
            rank = index + 1
            prev_score = score
        standings.append(Standing(rank=rank, name=row.name, level=row.level, xp=row.xp))
    return standings[:top]


# --- population spread: how many stand where (GROUP BY) -----------------------------------------

_POPULATION_SQL = text(
    """
    SELECT location, COUNT(*) AS n
    FROM characters
    GROUP BY location
    ORDER BY n DESC, location ASC
    """
)


def population_sql(session: SqlSession) -> list[tuple[str, int]]:
    return [(r.location, int(r.n)) for r in session.execute(_POPULATION_SQL).all()]


def population_py(rows: list[AnalyticsRow]) -> list[tuple[str, int]]:
    counts = Counter(row.location for row in rows)
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


# --- treasury: the economy at a glance (SUM/MAX/MIN aggregates) ---------------------------------

_WEALTH_SQL = text(
    """
    SELECT COUNT(*)                AS players,
           COALESCE(SUM(coins), 0) AS total,
           COALESCE(MAX(coins), 0) AS high,
           COALESCE(MIN(coins), 0) AS low
    FROM characters
    """
)


def wealth_sql(session: SqlSession) -> WealthStats:
    r = session.execute(_WEALTH_SQL).one()
    return WealthStats(players=int(r.players), total=int(r.total), high=int(r.high), low=int(r.low))


def wealth_py(rows: list[AnalyticsRow]) -> WealthStats:
    if not rows:
        return WealthStats(players=0, total=0, high=0, low=0)
    coins = [row.coins for row in rows]
    return WealthStats(players=len(coins), total=sum(coins), high=max(coins), low=min(coins))


def main() -> None:  # pragma: no cover - a live read of the real archive, not unit-tested
    """Print the live standings, spread, and treasury from the real archive (a runnable demo)."""
    from kernel.world.db import open_archive_session  # noqa: PLC0415

    with open_archive_session() as session:
        print("-- leaderboard --")
        for s in leaderboard_sql(session, top=10):
            print(f"  {s.rank:>3}. {s.name:<20} L{s.level}  {s.xp} xp")
        print("-- population --")
        for location, n in population_sql(session):
            print(f"  {location:<20} {n}")
        w = wealth_sql(session)
        print(f"-- treasury -- {w.players} players, {w.total} coins (high {w.high})")


if __name__ == "__main__":  # pragma: no cover
    main()
