"""PostgreSQL integration: prove the ORM models round-trip on a real Postgres.

This test builds its OWN engine from POSTGRES_TEST_URL, so it deliberately bypasses the
conftest SQLite quarantine (the unit suite always runs on tmp SQLite). It is skipped unless
POSTGRES_TEST_URL is set, so local runs and the SQLite CI job stay green; the dedicated
Postgres CI job sets the URL and runs it against a service container.
"""

import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SqlSession

from parts.world.db import ArchiveBase, CharacterRow

_URL = os.environ.get("POSTGRES_TEST_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not _URL, reason="set POSTGRES_TEST_URL to run the PostgreSQL integration test"
)


def test_orm_round_trips_on_postgresql():
    engine = create_engine(_URL)
    ArchiveBase.metadata.drop_all(engine)  # clean slate, whatever a prior run left
    ArchiveBase.metadata.create_all(engine)
    try:
        with SqlSession(engine) as write:
            write.add(
                CharacterRow(name="pg_hero", job="smith", level=3, location="forge", rank="player")
            )
            write.commit()
        with SqlSession(engine) as read:
            row = read.scalars(select(CharacterRow).where(CharacterRow.name == "pg_hero")).one()
            assert row.level == 3
            assert row.job == "smith"
    finally:
        ArchiveBase.metadata.drop_all(engine)
        engine.dispose()
