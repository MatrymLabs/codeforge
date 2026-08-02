"""CARD: job_progress_sql -- the SQLAlchemy adapter for the JobProgressStore port.

The framework kept behind the boundary. `job_progress` (the domain) names the narrow
`JobProgressStore` port and never imports SQLAlchemy; this adapter implements that port over the
`job_progress` table, holding the ORM query logic that used to live in the domain module. Swapping
persistence (a different backend, an in-memory store for a test) means swapping this adapter, not
touching the domain -- the point of the assimilation pattern (docs/persistence_ports.md).

SQLAlchemy and kernel.world.db are imported LAZILY inside methods, so importing this adapter (and
so the domain module that lazily reaches it) never triggers the ~400ms SQLAlchemy import on the hot
`import forge` path (EXP-003).
"""

from __future__ import annotations

from collections.abc import Iterable

from kernel.world.job_progress import JobProgress


class SqlJobProgressStore:
    """A JobProgressStore backed by the SQL `job_progress` table (one row per character+job)."""

    def load(self, character_name: str) -> dict[str, JobProgress]:
        """Every job record for a character, keyed by job id. Empty for an unknown/new character."""
        from sqlalchemy import select

        from kernel.world.db import JobProgressRow, open_archive_session

        with open_archive_session() as db:
            rows = db.execute(
                select(JobProgressRow).where(JobProgressRow.character_name == character_name)
            ).scalars()
            return {
                row.job_id: JobProgress(row.job_id, row.job_level, row.jp, row.tp) for row in rows
            }

    def save(self, character_name: str, records: Iterable[JobProgress]) -> None:
        """Upsert a character's job records. The character row must already exist (the FK)."""
        from kernel.world.db import JobProgressRow, open_archive_session

        with open_archive_session() as db:
            for record in records:
                row = db.get(JobProgressRow, (character_name, record.job_id)) or JobProgressRow(
                    character_name=character_name, job_id=record.job_id
                )
                row.job_level = record.job_level
                row.jp = record.jp
                row.tp = record.tp
                db.add(row)
            db.commit()
