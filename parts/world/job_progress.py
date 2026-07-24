"""CARD: job_progress -- per-job progression records (job level, JP, TP) behind a storage PORT.

A character progresses in many jobs; each job keeps its own level, JP, and TP, so changing jobs
never erases a prior job's rank. This card is the domain side of that storage: a frozen
`JobProgress` value object, the narrow `JobProgressStore` PORT (the persistence contract), and a
pure in-memory adapter for tests and reuse. The SQL adapter lives in job_progress_sql (the framework
stays behind the boundary); the module-level `load`/`save` wrappers delegate to it by default, so
existing callers are unchanged while the boundary is now swappable and testable.

This is the assimilation pattern (docs/persistence_ports.md): the domain names a narrow Python port;
a framework (SQLAlchemy) implements it as an adapter; the domain never imports the framework. Import
stays engine-free -- SQLAlchemy is reached only through the lazily-loaded adapter (EXP-003).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class JobProgress:
    """One character's standing in one job. A fresh job starts at level 1 with nothing earned."""

    job_id: str
    job_level: int = 1
    jp: int = 0
    tp: int = 0


@runtime_checkable
class JobProgressStore(Protocol):
    """The persistence boundary for job records: load a character's jobs, upsert them. Any adapter
    (SQL, in-memory, a future backend) satisfies this narrow contract; the domain depends on it, not
    on a framework."""

    def load(self, character_name: str) -> dict[str, JobProgress]:
        """Every job record for a character, keyed by job id. Empty for an unknown character."""
        ...

    def save(self, character_name: str, records: Iterable[JobProgress]) -> None:
        """Upsert a character's job records."""
        ...


class InMemoryJobProgressStore:
    """A dict-backed JobProgressStore: dependency-free, deterministic. Drives the contract tests and
    is a ready reuse for a save-less or test world."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, JobProgress]] = {}

    def load(self, character_name: str) -> dict[str, JobProgress]:
        return dict(self._jobs.get(character_name, {}))

    def save(self, character_name: str, records: Iterable[JobProgress]) -> None:
        bucket = self._jobs.setdefault(character_name, {})
        for record in records:
            bucket[record.job_id] = record


def _default_store() -> JobProgressStore:
    """The default backend: the SQL adapter, imported lazily so this module stays engine-free at
    import time (the JobProgress value object rides the hot `import forge` path)."""
    from parts.world.job_progress_sql import SqlJobProgressStore

    return SqlJobProgressStore()


def load_job_progress(
    character_name: str, store: JobProgressStore | None = None
) -> dict[str, JobProgress]:
    """Every job record for a character by job id. Uses the SQL store unless one is injected."""
    return (store or _default_store()).load(character_name)


def save_job_progress(
    character_name: str, records: Iterable[JobProgress], store: JobProgressStore | None = None
) -> None:
    """Upsert a character's job records. Uses the SQL store unless one is injected."""
    (store or _default_store()).save(character_name, records)
