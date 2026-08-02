"""CARD: mortality -- when a felled foe stays DOWN, and when it stands back up.

Until now every foe reassembled at full health the instant it fell -- the training dummy's whole
job, applied to the entire world -- so a kill read like sparring and nothing ever stayed cleared.
This gives a felled WORLD foe a real death: it drops out of its room and respawns on a timer set by
its tier, so clearing a room MEANS something for a while. The training dummy (and anything a seed
marks `reassembles`) is the deliberate exception -- collapsing and standing right back up is the
whole point of a sparring partner. This is the keel-approved half of "the world reads as cleared."

Lazy, never scheduled: a dead foe carries a `dead_until` beat; presence (kernel.world.npcs.npcs_in)
skips it, and the first presence check on or after that beat revives it in place. There is no
per-foe scheduler job, so this holds at world-generation scale (tens of thousands of foes) -- one
dict field and an integer compare, not a timer per creature. Pure over (npc, beat): tests drive the
beat directly, like the rest of the world clock (kernel.world.climate).
"""

from __future__ import annotations

from kernel.world.seed import Npc

# Respawn delay in world BEATS (one beat = one player command), by foe tier. A felled foe is absent
# for this many beats, then revives at full health. It escalates with tier: trash returns soon, a
# boss stays cleared far longer, a raid apex longer still. A starting curve for tuning, not a law.
RESPAWN_BEATS: dict[str, int] = {
    "normal": 15,
    "elite": 40,
    "boss": 120,
    "raid": 300,
}
_DEFAULT_RESPAWN = 15

# The transient combat marks a felled foe sheds either way (whole again on revival, gone on death).
_TRANSIENT: tuple[str, ...] = ("burn", "dazed", "charging", "weakened", "enraged")


def respawn_delay(npc: Npc) -> int:
    """Beats until this foe respawns, from its tier (an unknown tier gets the normal delay)."""
    return RESPAWN_BEATS.get(str(npc.get("tier", "normal")), _DEFAULT_RESPAWN)


def reassembles(npc: Npc) -> bool:
    """True for a foe that stands right back up at full health instead of dying -- the training
    dummy and anything a seed explicitly marks `reassembles`. Collapsing is its whole job."""
    return bool(npc.get("reassembles"))


def defeat_clause(npc: Npc) -> str:
    """The actor/room-facing phrase for a foe just felled: a reassembling foe stands back up, a
    mortal foe is slain. One source for the wording so every combat path reads the same."""
    return "collapses -- then reassembles itself" if reassembles(npc) else "collapses, slain"


def _shed_transient(npc: Npc) -> None:
    """Drop the transient combat marks (burn, daze, wind-up, weaken, enrage) a felled foe loses."""
    for key in _TRANSIENT:
        npc.pop(key, None)  # type: ignore[misc]  # each is a NotRequired Npc key


def fell(npc: Npc, beat: int) -> bool:
    """Resolve a foe reaching 0 HP. A REASSEMBLING foe is restored to full at once and returns
    False (it did not die). A MORTAL foe is left at 0 HP and marked dead until `beat +
    respawn_delay`, dropping from its room until then, and returns True (it died, and will respawn).
    Transient statuses clear either way, so a revived foe is whole and a dead one is bare."""
    _shed_transient(npc)
    if reassembles(npc):
        npc["hp_now"] = npc["hp"]
        return False
    npc["hp_now"] = 0
    npc["dead_until"] = beat + respawn_delay(npc)
    return True


def is_dead(npc: Npc, beat: int) -> bool:
    """Whether a foe is currently down. A foe whose respawn beat has ARRIVED is not dead: it is
    revived in place here (full health, the dead mark cleared) as a side effect, so the next
    presence check sees it alive again. Lazy revival -- no scheduler; the clock does the work the
    moment someone looks. A foe that was never felled (no `dead_until`) is trivially alive."""
    due = npc.get("dead_until")
    if due is None:
        return False
    if beat >= due:
        npc.pop("dead_until", None)
        npc["hp_now"] = npc["hp"]
        return False
    return True
