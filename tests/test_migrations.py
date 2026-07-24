"""Round-trip test for migrations/ -- the downgrade path is evidence, not dead code.

The postgres CI job crash-checks `alembic upgrade head` (the up path only); the three
downgrade() functions had zero coverage. This drives upgrade -> downgrade -> upgrade on a
throwaway SQLite file, proving every migration walks BOTH directions and that a downgrade
leaves a clean base the upgrades can rebuild from.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

import parts.world.db as db

_REPO = Path(__file__).resolve().parent.parent


def _tables(path: Path) -> set[str]:
    con = sqlite3.connect(path)
    names = {row[0] for row in con.execute("select name from sqlite_master where type='table'")}
    con.close()
    return names


def _config() -> Config:
    cfg = Config(str(_REPO / "alembic.ini"))
    cfg.set_main_option("script_location", str(_REPO / "migrations"))
    return cfg


def test_migrations_round_trip_upgrade_downgrade_upgrade(monkeypatch, tmp_path):
    """upgrade head -> full schema; downgrade base -> schema gone; upgrade head -> rebuilt."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    target = tmp_path / "migration-roundtrip.db"
    monkeypatch.setattr(db, "DB_PATH", target)  # env.py resolves the URL via engine_url()

    command.upgrade(_config(), "head")
    built = _tables(target)
    assert {"characters", "accounts", "job_progress"} <= built

    command.downgrade(_config(), "base")
    after_down = _tables(target)
    # every schema table is gone; only alembic's own version bookkeeping may remain
    assert not ({"characters", "accounts", "job_progress"} & after_down)

    command.upgrade(_config(), "head")  # a clean base rebuilds: downgrades left no debris
    assert {"characters", "accounts", "job_progress"} <= _tables(target)


def test_each_migration_steps_down_one_revision_at_a_time(monkeypatch, tmp_path):
    """Walk head -> -1 -> -1 -> -1: each individual downgrade() runs, not just the bulk path."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    target = tmp_path / "migration-steps.db"
    monkeypatch.setattr(db, "DB_PATH", target)

    command.upgrade(_config(), "head")
    for _ in range(5):  # five filed revisions, five individual steps
        command.downgrade(_config(), "-1")
    assert not ({"characters", "accounts", "job_progress"} & _tables(target))
