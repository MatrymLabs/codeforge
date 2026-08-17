"""CARD: schema_guard -- refuse to serve on a database whose columns are behind the models.

A persistent SQLite file drifts silently. `create_all(checkfirst=True)` builds a MISSING TABLE, but
it never adds a MISSING COLUMN to a table that already exists. So when a migration adds a column
the running database is never upgraded, the first query for that column takes the gateway down (it
did: `no such column: characters.secondary_job` crashed every login until `alembic upgrade head`
ran). The unit tests never catch this - each runs against a fresh, fully-built tmp database. So the
server itself checks, at power-on, that every column the models declare exists, and refuses to start
LOUD if any is missing, naming the one command that fixes it.

Read-only: it inspects, it never migrates. Mutating persistent data is a human-approved step
(`make db-migrate`), not a silent startup side effect. A brand-new database with no tables yet is
NOT drift - `create_all` will build it correctly - so only an existing table missing a column trips
the guard.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, inspect

from kernel.world.db import ArchiveBase, engine_url


class SchemaError(RuntimeError):
    """The database is behind the models (a table exists but lacks a column): fail loud."""


def missing_columns(engine: Engine | None = None) -> list[str]:
    """Every `table.column` the models declare that an EXISTING table is missing, in order.

    A table that does not exist at all is skipped (not drift: `create_all` will build it whole). The
    result is empty when the schema is current - the common, healthy case.
    """
    own_engine = engine is None
    engine = engine or create_engine(engine_url())
    try:
        inspector = inspect(engine)
        present_tables = set(inspector.get_table_names())
        gaps: list[str] = []
        for table in ArchiveBase.metadata.sorted_tables:
            if table.name not in present_tables:
                continue  # a whole missing table is not drift; create_all handles it
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
    """Raise SchemaError if any declared column is missing from an existing table. A no-op when the
    schema is current, so the server starts normally on a healthy or brand-new database."""
    gaps = missing_columns(engine)
    if gaps:
        raise SchemaError(  # noqa: TRY003
            "database schema is behind the code -- missing "
            f"{', '.join(gaps)}. Run `make db-migrate` (alembic upgrade head) before serving."
        )
