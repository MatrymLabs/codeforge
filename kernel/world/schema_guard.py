"""CARD: schema_guard -- refuse to serve on a database behind the current models.

A persistent SQLite file drifts silently. `create_all(checkfirst=True)` builds a MISSING TABLE, but
it never adds a MISSING COLUMN to a table that already exists. Likewise, an older migrated database
can be missing a newly introduced table. When a migration adds a column or table, the running
database is never upgraded, and the first query for it takes the gateway down. The unit tests never
catch this - each runs against a fresh, fully-built tmp database. So the server itself checks, at
power-on, that every model table and column exists, and refuses to start LOUD if any is missing,
naming the one command that fixes it.

Read-only: it inspects, it never migrates. Mutating persistent data is a human-approved step
(`make db-migrate`), not a silent startup side effect. A brand-new database with no tables yet is
NOT drift - `create_all` will build it correctly - so only a partially populated existing database
trips the guard.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, inspect

from kernel.world.db import ArchiveBase, engine_url


class SchemaError(RuntimeError):
    """The database is behind the models: fail loud."""


def missing_columns(engine: Engine | None = None) -> list[str]:
    """Every missing model table or `table.column` in an existing database, in order.

    A database with no tables is treated as new and returns no gaps. Once any table exists, a
    missing model table is drift and is reported as ``table (missing table)``.
    """
    own_engine = engine is None
    engine = engine or create_engine(engine_url())
    try:
        inspector = inspect(engine)
        present_tables = set(inspector.get_table_names())
        if not present_tables:
            return []
        gaps: list[str] = []
        for table in ArchiveBase.metadata.sorted_tables:
            if table.name not in present_tables:
                gaps.append(f"{table.name} (missing table)")
                continue
            columns = {col["name"] for col in inspector.get_columns(table.name)}
            gaps.extend(
                f"{table.name}.{column.name}"
                for column in table.columns
                if column.name not in columns
            )
        return gaps
    finally:
        if own_engine:
            engine.dispose()


def require_current_schema(engine: Engine | None = None) -> None:
    """Raise SchemaError if a declared table or column is missing. A no-op when the schema is
    current, so the server starts normally on a healthy or brand-new database."""
    gaps = missing_columns(engine)
    if gaps:
        raise SchemaError(
            "database schema is behind the code -- missing "
            f"{', '.join(gaps)}. Run `make db-migrate` (alembic upgrade head) before serving."
        )
