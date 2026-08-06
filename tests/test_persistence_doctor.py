"""Tests for the read-only persistence doctor."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from kernel.persistence_doctor import inspect_persistence
from kernel.platform import validate_startup_schema
from kernel.world.db import ArchiveBase


def _states(report):
    return {check.name: check.state for check in report.checks}


def test_doctor_reports_a_new_database_without_creating_it(tmp_path):
    target = tmp_path / "new.db"

    report = inspect_persistence(f"sqlite:///{target}")

    assert not target.exists()
    assert report.exit_code == 0
    assert _states(report) == {
        "database": "new",
        "schema": "new",
        "migrations": "new",
        "backups": "new",
        "recovery": "new",
    }


def test_doctor_reports_schema_drift_and_does_not_repair_it(tmp_path):
    target = tmp_path / "behind.db"
    engine = create_engine(f"sqlite:///{target}")
    ArchiveBase.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE audit_events"))

    report = inspect_persistence(f"sqlite:///{target}")

    assert report.exit_code == 1
    assert _states(report)["schema"] == "behind"
    assert "audit_events" in report.to_dict()["checks"][1]["detail"]


def test_doctor_reports_current_schema_without_claiming_untracked_migrations_are_ready(tmp_path):
    target = tmp_path / "untracked.db"
    engine = create_engine(f"sqlite:///{target}")
    ArchiveBase.metadata.create_all(engine)

    report = inspect_persistence(f"sqlite:///{target}")

    assert report.exit_code == 0
    states = _states(report)
    assert states["database"] == "ready"
    assert states["schema"] == "ready"
    assert states["migrations"] == "untracked"
    assert report.overall == "warnings"


def test_doctor_reports_a_database_at_the_checked_in_migration_head(monkeypatch, tmp_path):
    import kernel.world.db as db

    target = tmp_path / "migrated.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db, "DB_PATH", target)
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))

    command.upgrade(config, "head")
    report = inspect_persistence(f"sqlite:///{target}")
    engine = create_engine(f"sqlite:///{target}")
    try:
        validate_startup_schema(engine)
    finally:
        engine.dispose()

    assert report.exit_code == 0
    assert _states(report)["schema"] == "ready"
    assert _states(report)["migrations"] == "ready"


def test_cli_doctor_supports_structured_output(monkeypatch, capsys):
    import adapters.cli as cli
    from kernel.persistence_doctor import PersistenceCheck, PersistenceDoctorReport

    report = PersistenceDoctorReport(
        "/tmp/codeforge.db",
        (PersistenceCheck("database", "ready", "connected using sqlite"),),
    )
    monkeypatch.setattr("kernel.persistence_doctor.inspect_persistence", lambda: report)

    assert cli.main(["doctor", "--json"]) == 0
    assert '"overall": "ready"' in capsys.readouterr().out


def test_selected_database_isolation_and_recovery_follow_codeforge_db(monkeypatch, tmp_path):
    """The selected database, not the import-time repository default, owns recovery evidence."""
    import kernel.world.db as db

    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    backup_dir = tmp_path / "backups"

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("CODEFORGE_DB", str(first))
    with db.open_archive_session() as session:
        session.add(db.AccountRow(name="first-account", auth_salt="salt", auth_hash="hash"))
        session.commit()
    backup = db.backup_db(backup_dir)
    assert backup.parent == backup_dir
    assert backup.name.startswith("first-")

    monkeypatch.setenv("CODEFORGE_DB", str(second))
    with db.open_archive_session() as session:
        assert session.get(db.AccountRow, "first-account") is None

    restored = tmp_path / "restored.db"
    db.restore_db(backup, dest=restored)
    monkeypatch.setenv("CODEFORGE_DB", str(restored))
    with db.open_archive_session() as session:
        assert session.get(db.AccountRow, "first-account") is not None
