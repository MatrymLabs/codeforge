"""CARD: tutorial -- a state-driven onboarding ladder: tell a new hero the next step (game).

The gap analysis named it: "onboarding - no tutorial". A first-time player dropped into a MUD prompt
with no guidance bounces off it. This is the fix, and it is not a scripted rail: it READS the hero's
own state and names the single next thing worth doing, so the guidance is always current and never
gets in the way. Pick a calling, learn to fight, gear up, then the world is yours: each step unlocks
the next by simply doing it, the way the whole game teaches (show the working thing, then let them
do it). The `tutorial` verb surfaces the current step at any time; a brand-new hero is nudged toward
it once on first login, and a hero who has found their feet is never nagged again.
"""

from __future__ import annotations

from kernel.world.seed import SEED_NAME
from kernel.world.session import Session
from kernel.world.world_manifest import describe_world

# The world names ITSELF. This line used to read "Welcome to Aethryn", hardcoded, so a player on
# any other seed was welcomed to a world they were not in, and a third-party seed had no way to
# correct it without editing Python. The world is data: the title comes from the booted seed's
# world.yaml, or is derived from its id when it ships none. Bound at import like the rest of the
# seed surface, so the guidance costs no file read per step.
WORLD_TITLE = describe_world(SEED_NAME).title


def next_step(session: Session) -> str:
    """The single next thing this hero should do, read from live state (the guided first hour).
    A ladder: no calling -> a calling untested -> tested but ungeared -> established."""
    if session.stats is None or not session.job:
        return (
            f"Welcome to {WORLD_TITLE}, Forger. First, choose a calling: type JOBS to see them, "
            "then JOB <name> to take one."
        )
    if session.level < 2:  # noqa: PLR2004
        return (
            "You have a calling. Now learn to fight: ATTACK a foe (a training dummy is safe), "
            "and type SKILLS to see the abilities your calling wields."
        )
    if not session.equipped:
        return (
            "You are growing stronger. Gear up: pick something up (GET <item>), then EQUIP it. "
            "SCORE shows how your gear shapes your stats."
        )
    return (
        "You have found your feet, Forger. The world is open now: type HELP for every command, "
        "or simply set out and explore. Your road is your own."
    )


def greeting(session: Session) -> str:
    """A brand-new hero's first-login nudge toward the tutorial, or '' for an established hero (one
    who already holds a calling), so a returning veteran is never nagged. Fired once, on login."""
    if session.job:  # already chose a calling -> established; no onboarding nudge
        return ""
    return f"[New to Aethryn? Type TUTORIAL any time for a guided start.]\n{next_step(session)}"
