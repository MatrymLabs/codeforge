"""Configured persistence for registered source snapshots and their provenance.

Source files remain at the path recorded by ``SourceRecord``. This registry persists the approved
snapshot and legal-use metadata so a workspace can recover what it connected to after restart.
Legacy JSON records remain readable through the explicit dual-read transition.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session as SqlSession

from kernel.platform_db import SeedSourceRow, open_archive_session
from kernel.seedlab.project_model import Provenance
from kernel.seedlab.source_connector import SourceConnectorError, SourceRecord
from kernel.shelf.atomic_write import atomic_write_text

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


class ProvenanceStoreError(SourceConnectorError):
    """A provenance record is malformed, corrupt, or conflicts with immutable evidence."""


def _safe_segment(value: str) -> str:
    return _UNSAFE.sub("_", value)


def _record_to_dict(record: SourceRecord) -> dict[str, object]:
    return {
        "source_id": record.source_id,
        "provenance": {
            "source_id": record.provenance.source_id,
            "owner": record.provenance.owner,
            "license": record.provenance.license,
            "visibility": record.provenance.visibility,
            "allowed_use": record.provenance.allowed_use,
        },
        "root": record.root,
        "file_count": record.file_count,
        "branch": record.branch,
        "commit": record.commit,
        "digest": getattr(record, "digest", ""),
    }


def _record_from_dict(data: dict[str, object]) -> SourceRecord:
    try:
        raw_provenance = data["provenance"]
        if not isinstance(raw_provenance, dict):
            raise TypeError("provenance must be a mapping")
        values = {
            "source_id": str(data["source_id"]),
            "provenance": Provenance(**raw_provenance),
            "root": str(data["root"]),
            "file_count": int(data["file_count"]),
            "branch": None if data.get("branch") is None else str(data["branch"]),
            "commit": None if data.get("commit") is None else str(data["commit"]),
        }
        try:
            return SourceRecord(
                **values,
                digest=str(data.get("digest", "")),
            )
        except TypeError:
            # Compatibility with the pre-digest SourceRecord contract.
            return SourceRecord(**values)
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceConnectorError(f"malformed source record: {exc}") from exc


@runtime_checkable
class ProvenanceStore(Protocol):
    """Persistence seam for immutable registered source snapshots."""

    def save(self, seed_id: str, record: SourceRecord) -> None: ...

    def load(self, seed_id: str, source_id: str) -> SourceRecord | None: ...

    def all_for_seed(self, seed_id: str) -> list[SourceRecord]: ...


@dataclass
class FileProvenanceStore:
    """One JSON source snapshot per Seed and source ID."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, seed_id: str, source_id: str) -> Path:
        return self.root / _safe_segment(seed_id) / f"{_safe_segment(source_id)}.json"

    def save(self, seed_id: str, record: SourceRecord) -> None:
        target = self._path(seed_id, record.source_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(_record_to_dict(record), indent=2, sort_keys=True)
        existing = self.load(seed_id, record.source_id)
        if existing is not None and existing != record:
            raise ProvenanceStoreError(
                f"source {record.source_id!r} already exists with different provenance"
            )
        atomic_write_text(target, payload)

    def load(self, seed_id: str, source_id: str) -> SourceRecord | None:
        path = self._path(seed_id, source_id)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise TypeError("record must be a mapping")
            return _record_from_dict(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, SourceConnectorError) as exc:
            raise ProvenanceStoreError(f"corrupt provenance record {path}") from exc

    def all_for_seed(self, seed_id: str) -> list[SourceRecord]:
        root = self.root / _safe_segment(seed_id)
        if not root.is_dir():
            return []
        return [
            record
            for path in sorted(root.glob("*.json"))
            if (record := self.load(seed_id, path.stem)) is not None
        ]


@dataclass
class SqlProvenanceStore:
    """Durable source snapshots using the platform SQL persistence boundary."""

    session_factory: Callable[[], SqlSession] = open_archive_session

    def save(self, seed_id: str, record: SourceRecord) -> None:
        payload = json.dumps(_record_to_dict(record), sort_keys=True, separators=(",", ":"))
        with self.session_factory() as session, session.begin():
            row = session.get(SeedSourceRow, (seed_id, record.source_id))
            if row is not None:
                if row.source_json != payload:
                    raise ProvenanceStoreError(
                        f"source {record.source_id!r} already exists with different provenance"
                    )
                return
            session.add(
                SeedSourceRow(seed_id=seed_id, source_id=record.source_id, source_json=payload)
            )

    def load(self, seed_id: str, source_id: str) -> SourceRecord | None:
        with self.session_factory() as session:
            row = session.get(SeedSourceRow, (seed_id, source_id))
        return None if row is None else self._decode(row)

    def all_for_seed(self, seed_id: str) -> list[SourceRecord]:
        with self.session_factory() as session:
            rows = (
                session.query(SeedSourceRow)
                .filter(SeedSourceRow.seed_id == seed_id)
                .order_by(SeedSourceRow.source_id)
                .all()
            )
        return [self._decode(row) for row in rows]

    @staticmethod
    def _decode(row: SeedSourceRow) -> SourceRecord:
        try:
            raw = json.loads(row.source_json)
            if not isinstance(raw, dict):
                raise TypeError("record must be a mapping")
            return _record_from_dict(raw)
        except (json.JSONDecodeError, TypeError, ValueError, SourceConnectorError) as exc:
            raise ProvenanceStoreError(
                f"corrupt SQL provenance record {row.seed_id}/{row.source_id}"
            ) from exc


@dataclass
class DualReadProvenanceStore:
    """Read legacy source snapshots while writing new provenance to SQL."""

    primary: ProvenanceStore
    legacy: ProvenanceStore

    def save(self, seed_id: str, record: SourceRecord) -> None:
        self.primary.save(seed_id, record)

    def load(self, seed_id: str, source_id: str) -> SourceRecord | None:
        primary = self.primary.load(seed_id, source_id)
        legacy = self.legacy.load(seed_id, source_id)
        return self._merge(primary, legacy, source_id)

    def all_for_seed(self, seed_id: str) -> list[SourceRecord]:
        primary = {record.source_id: record for record in self.primary.all_for_seed(seed_id)}
        legacy = {record.source_id: record for record in self.legacy.all_for_seed(seed_id)}
        return [
            self._merge(primary.get(source_id), legacy.get(source_id), source_id)
            for source_id in sorted(primary.keys() | legacy.keys())
        ]

    @staticmethod
    def _merge(
        primary: SourceRecord | None,
        legacy: SourceRecord | None,
        source_id: str,
    ) -> SourceRecord:
        if primary is not None and legacy is not None and primary != legacy:
            raise ProvenanceStoreError(
                f"source {source_id!r} differs between SQL and legacy stores"
            )
        record = primary or legacy
        if record is None:
            raise ProvenanceStoreError(f"source {source_id!r} is missing from both stores")
        return record


def provenance_store(backend: str, home: Path) -> ProvenanceStore:
    """Build the source-provenance store selected by the shared SeedLab backend."""
    if backend == "file":
        return FileProvenanceStore(Path(home) / "sources")
    primary = SqlProvenanceStore()
    if backend == "sql":
        return primary
    if backend == "sql-dual-read":
        return DualReadProvenanceStore(primary, FileProvenanceStore(Path(home) / "sources"))
    raise ProvenanceStoreError(
        f"unknown provenance store backend {backend!r}; expected file, sql, or sql-dual-read"
    )


def configured_provenance_store(home: Path) -> ProvenanceStore:
    """Open source provenance through the shared SeedLab registry configuration."""
    backend = os.environ.get("CODEFORGE_SEED_REGISTRY", "file").strip() or "file"
    return provenance_store(backend, home)
