"""Seed registry selection and the explicit file-to-SQL migration boundary.

The migration path is intentionally separate from normal startup. ``sql-dual-read`` is a temporary
compatibility mode: SQL is the write authority, while legacy file records remain readable until an
operator runs the import and removes the old store. Explicit imports reject conflicting records.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

from kernel.seedlab.kernel import FileSeedStore, SeedRecord, SeedStore
from kernel.seedlab.sql_store import SqlSeedStore

FILE = "file"
SQL = "sql"
SQL_DUAL_READ = "sql-dual-read"
BACKENDS = (FILE, SQL, SQL_DUAL_READ)


class SeedRegistryError(ValueError):
    """The configured registry backend or migration state is unsafe."""


class SeedRegistryConflict(SeedRegistryError):
    """The legacy and SQL registries contain different records for one Seed id."""


@dataclass(frozen=True)
class SeedRegistryMigration:
    """Evidence from one explicit file-to-SQL import."""

    imported: int
    already_present: int
    source_records: int


@dataclass
class DualReadSeedStore(SeedStore):
    """Read legacy files during migration while writing all new state to SQL."""

    primary: SeedStore
    legacy: SeedStore

    def load(self, seed_id: str) -> SeedRecord | None:
        primary = self.primary.load(seed_id)
        legacy = self.legacy.load(seed_id)
        return _merge(seed_id, primary, legacy)

    def all(self) -> list[SeedRecord]:
        primary = {record.identity.seed_id: record for record in self.primary.all()}
        legacy = {record.identity.seed_id: record for record in self.legacy.all()}
        records: list[SeedRecord] = []
        for seed_id in sorted(primary.keys() | legacy.keys()):
            records.append(_merge(seed_id, primary.get(seed_id), legacy.get(seed_id)))  # type: ignore[arg-type]
        return records

    def save(self, record: SeedRecord) -> None:
        self.primary.save(record)


def _merge(seed_id: str, primary: SeedRecord | None, legacy: SeedRecord | None) -> SeedRecord:
    del seed_id  # reserved for diagnostics if the transition policy becomes stricter
    return primary or legacy  # type: ignore[return-value]


def seed_store(backend: str, home: Path) -> SeedStore:
    """Build the selected store without changing the local compatibility default."""
    if backend == FILE:
        return FileSeedStore(Path(home) / "seeds")
    primary = SqlSeedStore()
    if backend == SQL:
        return primary
    if backend == SQL_DUAL_READ:
        return DualReadSeedStore(primary, FileSeedStore(Path(home) / "seeds"))
    raise SeedRegistryError(
        f"unknown Seed registry backend {backend!r}; expected one of {BACKENDS}"
    )


def migrate_file_registry(
    home: Path,
    *,
    target: SqlSeedStore | None = None,
) -> SeedRegistryMigration:
    """Preflight and import all legacy records into SQL without overwriting conflicts."""
    source_records = FileSeedStore(Path(home) / "seeds").all()
    primary = target or SqlSeedStore()
    existing = {record.identity.seed_id: record for record in primary.all()}
    imports = [record for record in source_records if record.identity.seed_id not in existing]
    for record in source_records:
        current = existing.get(record.identity.seed_id)
        if current is not None and current != record:
            raise SeedRegistryConflict(
                f"Seed {record.identity.seed_id!r} differs; import aborted before writes"
            )
    if imports:
        primary.save_many(imports)
    return SeedRegistryMigration(
        len(imports), len(source_records) - len(imports), len(source_records)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import legacy SeedLab records into SQL.")
    parser.add_argument("--home", default=os.environ.get("SEEDLAB_HOME", ".seedlab"))
    args = parser.parse_args(argv)
    try:
        result = migrate_file_registry(Path(args.home))
    except SeedRegistryError as exc:
        parser.error(str(exc))
    print(
        f"seed registry migration: imported={result.imported} "
        f"already_present={result.already_present} source_records={result.source_records}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
