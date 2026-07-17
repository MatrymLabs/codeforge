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

# Unanswered world-beats an aggressive foe presses before it breaks off. The leash is the
# engineered exit the failsafe alone does not give: a player who cannot out-damage a foe and
# stops fighting is released instead of looped forever (hit -> restore -> hit). A player strike
# resets the count (parts.combat.attack), so a real fight keeps the foe engaged.
LEASH = 5


def menace(session: Session) -> str:
    """Every aggressive NPC sharing the player's room opens with a strike this beat, until it
    hits the leash and breaks off.

    Returns the combined line(s) (each already newline-led), or '' if none engage. A player
    with no calling yet (no stats) or a session no longer alive is left alone. Two hazards are
    bounded here: the LEASH releases a foe after too many unanswered beats, and the loop stops
    after the first blow that fells the player, so a restored player is never re-felled by a
    second aggressor inside one beat."""
    if session.stats is None or not session.alive:
        return ""
    lines: list[str] = []
    for nid in npcs_in(session.location):
        npc = NPCS[nid]
        if not npc.get("aggressive"):
            continue
        beats = session.aggro_beats.get(nid, 0)
        if beats >= LEASH:
            continue  # already broken off; it waits for the player to re-provoke it
        session.aggro_beats[nid] = beats + 1
        if session.aggro_beats[nid] >= LEASH:
            # the leash snaps taut on this beat: the foe disengages instead of striking
            lines.append(f"\n{npc['name'].capitalize()} breaks off its assault.")
            continue
        blow = open_strike(session, npc)
        if blow:  # a passive foe (atk 0) lands nothing; skip its empty line
            lines.append(blow)
            if "wake restored" in blow:  # the failsafe fired: one near-death per beat, then stop
                break
    return "".join(lines)
