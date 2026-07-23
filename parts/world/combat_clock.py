"""CARD: combat_clock -- advance the combat clock one step (the shared round timer).

Every valid combat action advances the clock: cooldowns and statuses count down (the expired
drop off) and a job's custom resource regenerates by its per-tick rate. This is job-BLIND -- it
reads only the session's own boards (`cooldowns`, `statuses`, `resources["power"]`) and the
active job's `power_regen`, so any action from any source (a basic strike, an Engineer ability,
a future job's skill) advances the same timer without combat knowing which job is seated.

Split out of the Engineer kit, where it was misfiled as `engineer.tick`: the clock is a combat
concept, not an Engineer one. Engineer re-exports it (`tick`) for its own abilities; combat calls
`advance` on every landed strike, so cooldowns thaw and statuses age as rounds pass.
"""

from __future__ import annotations

from parts.world.jobs import JOBS
from parts.world.session import Session


def advance(session: Session) -> None:
    """Advance the combat clock one step: count cooldowns/statuses down, drop the expired, and
    regenerate the job's custom resource (Power Cells) by its per-tick rate."""
    for board in (session.cooldowns, session.statuses):
        for name in list(board):
            board[name] -= 1
            if board[name] <= 0:
                del board[name]
    power = session.resources.get("power")
    if power is not None and session.job in JOBS:
        regen = JOBS[session.job]["power_regen"]
        if regen and power.current < power.maximum:
            session.resources["power"] = power.heal(regen)
