"""CARD: aggression -- proactive NPCs that strike on the world's beat.

Reactive combat (parts.world.combat) answers a player's blow. Aggression is its other
half: an NPC flagged `aggressive` in the seed does not wait to be hit. On each
world beat -- every engine tick, the only clock the world has -- an aggressive NPC
that shares a room with the acting player opens with a strike of its own.

There is no background thread and no second door into world state: the player's
command IS the heartbeat (the engine tick is the only door). `menace` only asks
combat to resolve an unprovoked blow and returns the line for the tick to append;
state stays canonical, mutated solely by validated combat logic.
"""

from parts.world import threat
from parts.world.combat import open_strike
from parts.world.encounter_log import witness
from parts.world.events import announce_to
from parts.world.npcs import NPCS, npcs_in
from parts.world.session import SESSIONS, Session, sentence_case

# Unanswered world-beats an aggressive foe presses before it breaks off. The leash is the
# engineered exit the failsafe alone does not give: a player who cannot out-damage a foe and
# stops fighting is released instead of looped forever (hit -> restore -> hit). A player strike
# resets the count (parts.world.combat.attack), so a real fight keeps the foe engaged.
LEASH = 5


def _fighters_in(location: str) -> dict[str, Session]:
    """The heroes present in a room who can be struck: alive, with a calling. The pool a foe picks
    its target from by threat."""
    return {
        pid: s
        for pid, s in list(SESSIONS.items())
        if s.location == location and s.alive and s.stats is not None
    }


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
        dazed = npc.get("dazed", 0)
        if dazed > 0:  # crowd control: a dazed foe skips this beat's strike and does not press
            npc["dazed"] = dazed - 1  # the leash (the player buys real respite while it reels)
            if npc["dazed"] <= 0:
                npc.pop("dazed", None)
            lines.append(f"\n{sentence_case(npc['name'])} reels, too dazed to strike.")
            witness("dazed", npc["name"], "was too dazed to strike")
            continue
        beats = session.aggro_beats.get(nid, 0)
        if beats >= LEASH:
            continue  # already broken off; it waits for the player to re-provoke it
        session.aggro_beats[nid] = beats + 1
        if session.aggro_beats[nid] >= LEASH:
            # the leash snaps taut on this beat: the foe disengages instead of striking
            lines.append(f"\n{sentence_case(npc['name'])} breaks off its assault.")
            witness("leash_break", npc["name"], "broke off its assault")
            continue
        # The foe strikes whoever tops its threat table (the tank's whole job), falling back to the
        # hero whose beat this is when no threat is recorded yet. The blow resolves against the
        # victim; if that is not the acting hero, it is pushed to them, the room sees the broadcast.
        victim = threat.top_target(nid, _fighters_in(session.location)) or session
        blow = open_strike(victim, npc)
        if blow:  # a passive foe (atk 0) lands nothing; skip its empty line
            witness("open_strike", npc["name"], "struck first on the world beat")
            if victim is session:
                lines.append(blow)
                if (
                    "Training-ground failsafe" in blow
                ):  # the failsafe fired: one near-death per beat, then stop
                    break
            else:
                announce_to([victim.player_id], blow)  # the tank feels it; the actor sees the frame
    return "".join(lines)
