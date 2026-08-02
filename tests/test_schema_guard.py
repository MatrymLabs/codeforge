"""Tests for the schema guard: it passes a current (or brand-new) DB and trips on a dropped column.

The bug this guards against took the live gateway down: a persistent database missing a migrated
column crashed every login. `create_all` could not fix it (it adds tables, not columns), and the
unit suite never saw it (each test runs on a fresh, fully-built tmp DB). So the acceptance case here
is "a fresh DB is fine" and the refusal case is "a table missing a column fails loud, by name".
"""

import pytest
from sqlalchemy import create_engine, text

from kernel.world.db import ArchiveBase, engine_url
from kernel.world.schema_guard import SchemaError, missing_columns, require_current_schema


def _fresh_engine():
    """An engine on the quarantined tmp DB with the full current schema built."""
    engine = create_engine(engine_url())
    ArchiveBase.metadata.create_all(engine)
    return engine


def test_a_current_schema_reports_no_gaps():
    engine = _fresh_engine()
    assert missing_columns(engine) == []
    require_current_schema(engine)  # no raise


def test_a_brand_new_empty_database_is_not_drift():
    # no tables at all is a new DB create_all will build, not a behind-schema one
    engine = create_engine(engine_url())
    assert missing_columns(engine) == []
    require_current_schema(engine)


def test_a_table_missing_a_column_is_flagged_by_name():
    engine = _fresh_engine()
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE characters DROP COLUMN secondary_job"))  # simulate the drift
    gaps = missing_columns(engine)
    assert "characters.secondary_job" in gaps


def test_require_current_schema_fails_loud_and_names_the_fix():
    engine = _fresh_engine()
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE characters DROP COLUMN coins"))
    with pytest.raises(SchemaError) as err:
        require_current_schema(engine)
    assert "characters.coins" in str(err.value)
    assert "db-migrate" in str(err.value)  # the guard names the one command that fixes it
