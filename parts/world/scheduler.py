"""CARD: scheduler -- a timed-job registry the world beat drains (deferred work, on the game clock).

The engine has no free-running loop; time is the world BEAT, advanced once per tick (parts.world.
climate). This is the seam for work that should happen LATER: close an expired auction, fire a timed
world event, expire a buff. A job is registered for a due beat and the tick drains it when the beat
arrives, so scheduling stays deterministic and testable (drive it with a beat number, never a
wall-clock) and off any background thread.

One-shot or recurring: a job with `every > 0` re-arms itself for `due + every` after each firing. A
job that raises is DROPPED rather than allowed to crash the tick or wedge the clock: a broken
scheduled task must never take the world down. Jobs are in-memory (the process's live intentions);
anything that must survive a restart re-registers its sweep at boot over its own persisted rows (the
auction re-arms an expiry sweep against the auction table), so the scheduler needs no persistence.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class _Job:
    due: int  # the world beat at or after which this job fires
    run: Callable[[], None]
    every: int  # 0 = one-shot; > 0 = re-arm for due + every after each firing


_JOBS: list[_Job] = []


def schedule(due_beat: int, run: Callable[[], None], *, every: int = 0) -> None:
    """Register `run` to fire once at `due_beat` (or every `every` beats from then, if given). The
    tick fires it via run_due when the beat arrives."""
    _JOBS.append(_Job(due_beat, run, max(0, every)))


def run_due(now_beat: int) -> int:
    """Fire every job due at or before `now_beat`, in registration order, and return how many fired.
    A one-shot is removed; a recurring job re-arms for now_beat + its interval. A job that raises is
    dropped (a broken job never wedges the clock or crashes the tick)."""
    fired = 0
    for job in list(_JOBS):
        if job.due > now_beat:
            continue
        try:
            job.run()
        except Exception:  # noqa: BLE001 -- a scheduled job must never take the tick down
            _drop(job)
            continue
        fired += 1
        if job.every > 0:
            job.due = now_beat + job.every
        else:
            _drop(job)
    return fired


def tick(_session: object) -> str:
    """Drain jobs due on the current world beat. Silent, so it composes into the tick like the
    climate ticker; called AFTER the climate ticker has advanced the beat."""
    from parts.world import climate

    run_due(climate.now())
    return ""


def pending() -> int:
    """How many jobs are waiting (for tests and diagnostics)."""
    return len(_JOBS)


def clear() -> None:
    """Drop all jobs. For tests and a clean reboot."""
    _JOBS.clear()


def _drop(job: _Job) -> None:
    """Remove a job if still present (run_due iterates a snapshot; a job may already be gone)."""
    if job in _JOBS:
        _JOBS.remove(job)
