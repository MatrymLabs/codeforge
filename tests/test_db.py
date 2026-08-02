"""Test twin for kernel/world/db.py -- the schema holds the laws now."""

from pathlib import Path

import pytest

import kernel.world.db as db
from kernel.world.characters import load_character, put_record, save_character
from kernel.world.db import CharacterRow, _default_db_path, engine_url, open_archive_session
from kernel.world.session import SESSIONS, Session


def test_engine_url_defaults_to_sqlite_at_db_path(monkeypatch, tmp_path):
    """No DATABASE_URL -> a SQLite file at DB_PATH (the zero-config dev/test default)."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "x.db")
    assert engine_url() == f"sqlite:///{tmp_path / 'x.db'}"


def test_database_url_overrides_to_postgres(monkeypatch):
    """DATABASE_URL wins -> the same ORM speaks PostgreSQL (production backend)."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@host:5432/codeforge")
    assert engine_url() == "postgresql+psycopg://u:p@host:5432/codeforge"


def test_blank_database_url_falls_back_to_sqlite(monkeypatch, tmp_path):
    """An empty/whitespace DATABASE_URL is treated as unset, not a broken URL."""
    monkeypatch.setenv("DATABASE_URL", "   ")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "y.db")
    assert engine_url().startswith("sqlite:///")


def test_default_db_path_is_absolute_and_repo_anchored(monkeypatch):
    """The wrong-cwd trap is closed: the default is never relative, so the
    server opens the same file from any launch directory."""
    monkeypatch.delenv("CODEFORGE_DB", raising=False)
    p = _default_db_path()
    assert p.is_absolute()
    assert p.name == "codeforge.db"
    assert (
        p.parent == Path(db.__file__).resolve().parent.parent.parent
    )  # kernel/world/db.py -> repo root


def test_codeforge_db_env_overrides_the_default(monkeypatch, tmp_path):
    target = tmp_path / "chosen.db"
    monkeypatch.setenv("CODEFORGE_DB", str(target))
    assert _default_db_path() == target


def test_tables_create_and_roundtrip():
    put_record("matrym", {"job": "vanguard", "level": 2, "xp": 90, "location": "courtyard"})
    record = load_character("matrym")
    assert record is not None
    assert record["level"] == 2
    assert record["rank"] == "player"  # column default
    assert "auth" not in record  # no auth columns set


def test_backup_then_restore_recovers_the_pre_backup_state(tmp_path):
    """Stage-9 recovery proof: back up the live DB, mutate it, restore the backup, and the
    pre-backup character state returns intact -- the recovery half of `make backup` that
    the live demo once lacked. Exercises restore_db's engine-dispose so the next read opens
    the RESTORED file, not a pre-restore connection."""
    put_record("keeper", {"job": "vanguard", "level": 5, "xp": 300, "location": "greenhold"})
    assert load_character("keeper")["level"] == 5

    backup = db.backup_db(dest_dir=tmp_path / "bk")
    assert backup.exists()

    # mutate the live DB well away from the backed-up state
    put_record("keeper", {"job": "vanguard", "level": 99, "xp": 9999, "location": "forge"})
    assert load_character("keeper")["level"] == 99

    restored = db.restore_db(backup)
    assert restored == Path(db.DB_PATH)

    rec = load_character("keeper")  # a fresh engine reads the restored file
    assert rec is not None
    assert (rec["level"], rec["xp"], rec["location"]) == (5, 300, "greenhold")


def test_restore_refuses_a_missing_backup(tmp_path):
    """Recovery fails loud, not silently: a non-existent backup path raises, never leaving
    the live DB half-overwritten."""
    with pytest.raises(FileNotFoundError):
        db.restore_db(tmp_path / "no-such-backup.db")


def test_save_character_never_touches_auth_columns():
    """The merge-save law, enforced by column scope."""
    put_record(
        "matrym",
        {"job": "", "level": 1, "xp": 0, "location": "forge", "auth": {"salt": "aa", "hash": "bb"}},
    )
    hero = Session(player_id="matrym", named=True, level=5, location="cellar")
    SESSIONS["matrym"] = hero
    save_character(hero)
    SESSIONS.clear()
    record = load_character("matrym")
    assert record["level"] == 5
    assert record["auth"] == {"salt": "aa", "hash": "bb"}  # survived the save


def test_unnamed_seats_write_no_rows():
    save_character(Session(player_id="player1"))
    with open_archive_session() as db:
        assert db.get(CharacterRow, "player1") is None


def test_backup_db_makes_a_valid_sqlite_copy(monkeypatch, tmp_path):
    import sqlite3

    from kernel.world.db import backup_db

    monkeypatch.delenv("DATABASE_URL", raising=False)
    live = tmp_path / "codeforge.db"
    monkeypatch.setattr(db, "DB_PATH", live)
    con = sqlite3.connect(live)  # a real SQLite db at DB_PATH with content to preserve
    con.execute("create table t (x)")
    con.execute("insert into t values (42)")
    con.commit()
    con.close()
    dest = backup_db(dest_dir=tmp_path / "backups")
    assert dest.exists() and dest.suffix == ".db"
    copy = sqlite3.connect(dest)  # the snapshot is a valid, openable copy carrying the row
    value = copy.execute("select x from t").fetchone()[0]
    copy.close()
    assert value == 42


def test_backup_db_refuses_a_non_sqlite_backend(monkeypatch):
    from kernel.world.db import backup_db

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/x")
    with pytest.raises(RuntimeError, match="pg_dump"):
        backup_db()


def test_a_backup_restores_and_the_store_boots_against_it(tmp_path):
    # The restore TEST the infra spec asks for: a backup is only real if it restores AND the store
    # boots against it. conftest already points DB_PATH at a tmp live db; write a real character,
    # snapshot it, LOSE the live db, restore from the snapshot, and confirm the store reads it back.
    from kernel.world.db import backup_db, restore_db

    put_record("ada", {"job": "vanguard", "level": 7, "location": "hall", "xp": 300})
    assert load_character("ada")["level"] == 7  # a real row in the live db
    snapshot = backup_db(dest_dir=tmp_path / "backups")

    # DISASTER: the live database is gone, and a fresh process holds no connection to it.
    Path(db.DB_PATH).unlink()
    db._ENGINES.clear()

    # RECOVERY: restore the snapshot over DB_PATH, then boot the store against it.
    restored = restore_db(snapshot)
    assert restored == Path(db.DB_PATH)
    assert load_character("ada")["level"] == 7  # the backup restored AND the store reads it clean


def test_restore_db_refuses_a_missing_backup_or_a_non_sqlite_backend(monkeypatch, tmp_path):
    from kernel.world.db import restore_db

    with pytest.raises(FileNotFoundError):
        restore_db(tmp_path / "nope.db")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/x")
    with pytest.raises(RuntimeError, match="pg_restore"):
        restore_db(tmp_path / "any.db")
