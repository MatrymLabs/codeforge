"""SQL-backed implementation of the generic SeedStore protocol.

The file-backed store remains the compatibility default for local SeedLab homes. This adapter
uses the existing SQLAlchemy archive boundary for hosted or production-shaped deployments; it does
not expose sessions or SQL to the Seed Kernel and it does not replace the runtime content loader.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session as SqlSession

from kernel.seedlab.kernel import SeedKernelError, SeedRecord, SeedStore
from kernel.world.db import SeedRegistryRow, open_archive_session


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _decode_list(raw: str, field: str) -> list[object]:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise SeedKernelError(f"malformed SQL Seed {field}: {exc}") from exc
    if not isinstance(value, list):
        raise SeedKernelError(f"malformed SQL Seed {field}: expected a list")
    return value


@dataclass
class SqlSeedStore(SeedStore):
    """Persist Seed records through the existing SQLAlchemy database seam.

    ``session_factory`` is injectable for tests and alternate deployment wiring. Each operation
    owns one short-lived session and transaction, so a caller never shares a mutable SQLAlchemy
    session across requests or jobs.
    """

    session_factory: Callable[[], SqlSession] = open_archive_session

    def _write(self, session: SqlSession, record: SeedRecord) -> None:
        payload = record.to_dict()
        identity = payload["identity"]
        row = session.get(SeedRegistryRow, record.identity.seed_id)
        if row is None:
            row = SeedRegistryRow(seed_id=record.identity.seed_id)
            session.add(row)
        row.name = str(identity["name"])
        row.owner = str(identity["owner"])
        row.purpose = str(identity["purpose"])
        row.version = str(identity["version"])
        row.created_at = str(identity["created_at"])
        row.product_type = str(identity.get("product_type", ""))
        row.domain_modules = _json(identity.get("domain_modules", []))
        row.status = record.status
        row.started_at = record.started_at
        row.stopped_at = record.stopped_at
        row.audit = _json(payload["audit"])

    def save(self, record: SeedRecord) -> None:
        with self.session_factory() as session, session.begin():
            self._write(session, record)

    def save_many(self, records: list[SeedRecord]) -> None:
        """Import a preflighted batch in one database transaction."""
        with self.session_factory() as session, session.begin():
            for record in records:
                self._write(session, record)

    def load(self, seed_id: str) -> SeedRecord | None:
        with self.session_factory() as session:
            row = session.get(SeedRegistryRow, seed_id)
            return None if row is None else self._record(row)

    def all(self) -> list[SeedRecord]:
        with self.session_factory() as session:
            rows = session.query(SeedRegistryRow).order_by(SeedRegistryRow.seed_id).all()
            return [self._record(row) for row in rows]

    @staticmethod
    def _record(row: SeedRegistryRow) -> SeedRecord:
        try:
            return SeedRecord.from_dict(
                {
                    "identity": {
                        "seed_id": row.seed_id,
                        "name": row.name,
                        "owner": row.owner,
                        "purpose": row.purpose,
                        "version": row.version,
                        "created_at": row.created_at,
                        "product_type": row.product_type,
                        "domain_modules": _decode_list(row.domain_modules, "domain_modules"),
                    },
                    "status": row.status,
                    "started_at": row.started_at,
                    "stopped_at": row.stopped_at,
                    "audit": _decode_list(row.audit, "audit"),
                }
            )
        except (KeyError, TypeError, ValueError, SeedKernelError) as exc:
            raise SeedKernelError(f"malformed SQL Seed {row.seed_id!r}: {exc}") from exc
