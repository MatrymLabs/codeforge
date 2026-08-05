"""Read-only persistence diagnostics for the CodeForge operator surface.

This module deliberately does not migrate, create tables, create backups, or mutate database
state. It projects the existing schema guard, Alembic revision graph, and local backup convention
into one truthful diagnostic that can be used by the CLI and future Creator Console views.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.engine import make_url

from kernel.world.db import engine_url
from kernel.world.schema_guard import missing_columns

if TYPE_CHECKING:
    from alembic.script import ScriptDirectory

CheckState = Literal[
    "ready",
    "new",
    "warning",
    "untracked",
    "behind",
    "diverged",
    "unavailable",
]


@dataclass(frozen=True)
class PersistenceCheck:
    """One read-only persistence diagnostic result."""

    name: str
    state: CheckState
    detail: str

    @property
    def is_failure(self) -> bool:
        """Whether this check represents a condition that should fail automation."""
        return self.state in {"behind", "diverged", "unavailable"}


@dataclass(frozen=True)
class PersistenceDoctorReport:
    """Structured persistence readiness evidence for operators and client consumers."""

    target: str
    checks: tuple[PersistenceCheck, ...]

    @property
    def overall(self) -> str:
        """Return the aggregate state without hiding warnings behind a green result."""
        if any(check.is_failure for check in self.checks):
            return "failed"
        if any(check.state in {"warning", "untracked"} for check in self.checks):
            return "warnings"
        return "ready"

    @property
    def exit_code(self) -> int:
        """Return a process status suitable for automation."""
        return 1 if self.overall == "failed" else 0

    def to_dict(self) -> dict[str, object]:
        """Serialize the diagnostic without exposing database credentials."""
        return {
            "target": self.target,
            "overall": self.overall,
            "checks": [
                {"name": check.name, "state": check.state, "detail": check.detail}
                for check in self.checks
            ],
        }

    def render(self) -> str:
        """Render a stable text report for terminals and logs."""
        lines = [
            "CODEFORGE PERSISTENCE DOCTOR",
            f"target: {self.target}",
            f"overall: {self.overall.upper()}",
        ]
        for check in self.checks:
            lines.append(f"[{check.state.upper()}] {check.name}: {check.detail}")
        return "\n".join(lines)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _migration_root() -> Path:
    """Locate migrations in a source checkout or an installed CodeForge wheel."""
    checkout_root = _repo_root() / "migrations"
    if (checkout_root / "versions").is_dir():
        return checkout_root
    try:
        import migrations
    except ImportError:
        return checkout_root
    return Path(migrations.__file__).resolve().parent


def _migration_script(repo_root: Path | None = None) -> ScriptDirectory:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = (repo_root / "migrations") if repo_root is not None else _migration_root()
    config_path = _repo_root() / "alembic.ini"
    config = Config(str(config_path)) if config_path.is_file() else Config()
    config.set_main_option("script_location", str(root))
    return ScriptDirectory.from_config(config)


def _target(url: str) -> tuple[str, Path | None, str]:
    parsed = make_url(url)
    backend = parsed.get_backend_name()
    if backend == "sqlite":
        database = parsed.database or ":memory:"
        if database == ":memory:":
            return backend, None, database
        path = Path(database).expanduser().resolve()
        return backend, path, str(path)
    return backend, None, parsed.render_as_string(hide_password=True)


def _migration_check(connection, present_tables: set[str], repo_root: Path | None) -> PersistenceCheck:
    try:
        from alembic.migration import MigrationContext

        script = _migration_script(repo_root)
        expected = set(script.get_heads())
        current = set(MigrationContext.configure(connection).get_current_heads())
    except Exception as exc:
        return PersistenceCheck("migrations", "unavailable", f"could not inspect Alembic: {exc}")

    if not present_tables and not current:
        return PersistenceCheck(
            "migrations", "new", f"database is uninitialized; expected head {', '.join(sorted(expected))}"
        )
    if not current:
        return PersistenceCheck(
            "migrations",
            "untracked",
            "tables exist but alembic_version has no recorded revision; use a reviewed migration path",
        )
    if current == expected:
        return PersistenceCheck("migrations", "ready", f"database at head {', '.join(sorted(current))}")

    known = {revision.revision for revision in script.walk_revisions(expected)}
    if not current <= known:
        state: CheckState = "diverged"
        reason = "database revision is not present in the checked-in migration graph"
    else:
        state = "behind"
        reason = "database revision is behind the checked-in migration head"
    return PersistenceCheck(
        "migrations", state, f"current={','.join(sorted(current))}; expected={','.join(sorted(expected))}; {reason}"
    )


def _backup_checks(backend: str, path: Path | None) -> tuple[PersistenceCheck, PersistenceCheck]:
    if backend != "sqlite":
        detail = "external backup policy; verify pg_dump/PITR from the deployment environment"
        return (
            PersistenceCheck("backups", "warning", detail),
            PersistenceCheck("recovery", "warning", "restore drill is external to this local diagnostic"),
        )
    if path is None:
        return (
            PersistenceCheck("backups", "warning", "in-memory SQLite has no durable backup target"),
            PersistenceCheck("recovery", "warning", "in-memory SQLite cannot provide restart recovery"),
        )
    if not path.exists():
        detail = "no database file yet; initialize the Seed before taking a backup"
        return PersistenceCheck("backups", "new", detail), PersistenceCheck("recovery", "new", detail)

    backup_dir = path.parent / "backups"
    snapshots = sorted(backup_dir.glob(f"{path.stem}-*.db")) if backup_dir.is_dir() else []
    if not snapshots:
        detail = f"no SQLite snapshots found under {backup_dir}; run `make backup`"
        return (
            PersistenceCheck("backups", "warning", detail),
            PersistenceCheck("recovery", "warning", "no snapshot is available for a restore drill"),
        )
    newest = snapshots[-1]
    backup_detail = f"{len(snapshots)} snapshot(s); newest {newest}"
    return (
        PersistenceCheck("backups", "ready", backup_detail),
        PersistenceCheck(
            "recovery",
            "warning",
            "snapshot is present, but this diagnostic does not claim a verified restore",
        ),
    )


def inspect_persistence(url: str | None = None, *, repo_root: Path | None = None) -> PersistenceDoctorReport:
    """Inspect database, schema, migration, backup, and recovery state without mutation."""
    active_url = url or engine_url()
    backend, path, target = _target(active_url)
    if backend == "sqlite" and path is not None and not path.exists():
        backups, recovery = _backup_checks(backend, path)
        return PersistenceDoctorReport(
            target,
            (
                PersistenceCheck("database", "new", "no database file exists yet"),
                PersistenceCheck("schema", "new", "a fresh database is accepted by the startup guard"),
                _migration_check_for_new(repo_root),
                backups,
                recovery,
            ),
        )

    engine: Engine | None = None
    try:
        engine = create_engine(active_url)
        with engine.connect() as connection:
            present_tables = set(inspect(connection).get_table_names())
            gaps = missing_columns(engine)
            schema = (
                PersistenceCheck("schema", "ready", "all declared model tables and columns are present")
                if not gaps
                else PersistenceCheck("schema", "behind", f"missing {', '.join(gaps)}; run `make db-migrate`")
            )
            checks = (
                PersistenceCheck("database", "ready", f"connected using {backend}"),
                schema,
                _migration_check(connection, present_tables, repo_root),
                *_backup_checks(backend, path),
            )
            return PersistenceDoctorReport(target, checks)
    except Exception as exc:
        return PersistenceDoctorReport(
            target,
            (
                PersistenceCheck("database", "unavailable", f"could not inspect database: {exc}"),
                PersistenceCheck("schema", "unavailable", "schema inspection was not completed"),
                PersistenceCheck("migrations", "unavailable", "migration inspection was not completed"),
                PersistenceCheck("backups", "unavailable", "backup inspection was not completed"),
                PersistenceCheck("recovery", "unavailable", "recovery inspection was not completed"),
            ),
        )
    finally:
        if engine is not None:
            engine.dispose()


def _migration_check_for_new(repo_root: Path | None) -> PersistenceCheck:
    try:
        heads = _migration_script(repo_root).get_heads()
    except Exception as exc:
        return PersistenceCheck("migrations", "unavailable", f"could not inspect Alembic: {exc}")
    return PersistenceCheck("migrations", "new", f"no revision recorded; expected head {', '.join(heads)}")
