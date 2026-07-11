"""CARD: job_progress -- per-job progression records (job level, JP, TP), SQL-backed.

A character progresses in many jobs; each job keeps its own level, JP, and TP, so changing
jobs never erases a prior job's rank. This card is the storage door for those records: a
frozen `JobProgress` value object plus load/save over the `job_progress` table. It knows the
database, not the Session -- the runtime wiring (populating a session, persisting on save)
lives in characters.py, which keeps this module free of engine imports and cycle-free.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

# sqlalchemy and parts.db import lazily inside the load/save functions (below), so importing
# this module for the JobProgress value object (via parts.session, on the hot `import forge`
# path) never triggers the ~400ms SQLAlchemy import (EXP-003).


@dataclass(frozen=True)
class JobProgress:
    """One character's standing in one job. A fresh job starts at level 1 with nothing earned."""

    job_id: str
    job_level: int = 1
    jp: int = 0
    tp: int = 0


def load_job_progress(character_name: str) -> dict[str, JobProgress]:
    """Every job record for a character, keyed by job id. Empty for an unknown/new character."""
    from sqlalchemy import select

    from parts.db import JobProgressRow, open_archive_session

    with open_archive_session() as db:
        rows = db.execute(
            select(JobProgressRow).where(JobProgressRow.character_name == character_name)
        ).scalars()
        return {row.job_id: JobProgress(row.job_id, row.job_level, row.jp, row.tp) for row in rows}


def save_job_progress(character_name: str, records: Iterable[JobProgress]) -> None:
    """Upsert a character's job records. The character row must already exist (the FK)."""
    from parts.db import JobProgressRow, open_archive_session

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
