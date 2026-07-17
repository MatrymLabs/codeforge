"""CARD: aggression -- proactive NPCs that strike on the world's beat.

Reactive combat (parts.combat) answers a player's blow. Aggression is its other
half: an NPC flagged `aggressive` in the seed does not wait to be hit. On each
world beat -- every engine tick, the only clock the world has -- an aggressive NPC
that shares a room with the acting player opens with a strike of its own.

There is no background thread and no second door into world state: the player's
command IS the heartbeat (the engine tick is the only door). `menace` only asks
combat to resolve an unprovoked blow and returns the line for the tick to append;
state stays canonical, mutated solely by validated combat logic.
"""

from parts.combat import open_strike
from parts.npcs import NPCS, npcs_in
from parts.session import Session


def menace(session: Session) -> str:
    """Every aggressive NPC sharing the player's room opens with a strike this beat.

    Returns the combined strike line(s) (each already newline-led), or '' if none
    engage. A player with no calling yet (no stats) or a session no longer alive is
    left alone -- you cannot draw blood from someone who has not entered the fight."""
    if session.stats is None or not session.alive:
        return ""
    lines: list[str] = []
    for nid in npcs_in(session.location):
        npc = NPCS[nid]
        if not npc.get("aggressive"):
            continue
        blow = open_strike(session, npc)
        if blow:  # a passive foe (atk 0) lands nothing; skip its empty line
            lines.append(blow)
    return "".join(lines)
