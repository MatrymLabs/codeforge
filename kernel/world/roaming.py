"""CARD: roaming -- ambient NPCs that drift between rooms on the world's beat (world life).

The world was a frozen diorama: every NPC stood exactly where the seed placed it, forever. This is
the other half of the beat aggression already rides -- a peaceful NPC flagged `wander` in the seed
ambles from room to room, so a town feels lived-in and the wilds feel inhabited. There is still no
background thread and no second door into world state: the player's command IS the heartbeat, and
`roam` only asks the world to move a wanderer and returns the line for the tick to append.

Bounded by design: roaming is scoped to the player's ROOM and its immediate neighbours, so the cost
is a handful of NPCs per beat, not the whole world, and the player always SEES the drift they cause:
a creature here wanders off, a creature next door ambles in. Peaceful only (seed-gated to a non-
aggressive NPC), so a fight is never interrupted by a foe wandering out of the room mid-swing. Moves
are deterministic under a seeded RNG, so the test twin names exact outcomes.
"""

import random

from kernel.world.events import announce
from kernel.world.npcs import NPCS, apply_npc_moves, npcs_in
from kernel.world.session import Session, sentence_case
from kernel.world.world import WORLD

# World flavor, not security: a seeded module RNG so tests replace it for exact drift.
_ROAM_RNG = random.Random()  # nosec B311  # noqa: S311

# One in this many beats a given wanderer moves. A drift, not a frenzy: high enough that a room does
# not churn every turn, low enough that the world visibly breathes over a short walk.
ROAM_CHANCE = 4


def roam(session: Session) -> str:
    """Drift the ambient `wander` NPCs near the player one step, and return the line(s) the player
    sees (each newline-led), or ''. A wanderer in the player's room may leave through a random exit;
    a wanderer in a neighboring room may amble in. Non-wanderers and a roomless session are left
    alone; the room index is updated once, only for the NPCs that actually moved."""
    here = session.location
    room = WORLD.get(here)
    if room is None:
        return ""
    exits: dict[str, str] = room.get("exits", {})
    lines: list[str] = []
    moves: list[tuple[str, str, str]] = []  # (nid, old_room, new_room), applied to the index at end

    # OUT: a wanderer standing with the player may leave through a random exit.
    if exits:
        for nid in list(npcs_in(here)):
            npc = NPCS[nid]
            if not npc.get("wander") or _ROAM_RNG.randrange(ROAM_CHANCE) != 0:
                continue
            direction = _ROAM_RNG.choice(sorted(exits))
            npc["location"] = exits[direction]
            moves.append((nid, here, exits[direction]))
            name = sentence_case(npc["name"])
            announce(here, f"{name} wanders {direction}.", exclude=session.player_id)
            lines.append(f"\n{name} wanders {direction}.")

    # IN: a wanderer in a neighboring room may amble into the player's room (at most one per exit).
    for _direction, adjacent in sorted(exits.items()):
        for nid in list(npcs_in(adjacent)):
            npc = NPCS[nid]
            if not npc.get("wander") or _ROAM_RNG.randrange(ROAM_CHANCE) != 0:
                continue
            npc["location"] = here
            moves.append((nid, adjacent, here))
            lines.append(f"\n{sentence_case(npc['name'])} wanders in.")
            break

    if moves:
        # One incremental index update after all of this beat's moves are decided (not mid-loop, so
        # a lookup inside the loops still sees pre-roam positions -- the old rebuild-once rule).
        apply_npc_moves(moves)
    return "".join(lines)
