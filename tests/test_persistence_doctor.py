"""Tests for the read-only persistence doctor."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from kernel.persistence_doctor import inspect_persistence
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


def test_doctor_separates_migration_head_from_model_schema_drift(monkeypatch, tmp_path):
    import kernel.world.db as db

    target = tmp_path / "migrated.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db, "DB_PATH", target)
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))

    command.upgrade(config, "head")
    report = inspect_persistence(f"sqlite:///{target}")

    assert report.exit_code == 1
    assert _states(report)["schema"] == "behind"
    assert _states(report)["migrations"] == "ready"
    assert "seed_runs" in report.to_dict()["checks"][1]["detail"]


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
