"""CARD: boss_phases -- give boss fights a second gear: a wounded boss ENRAGES and hits harder.

Every foe fought the same: trade blows until one falls, the numbers flat the whole way down. A boss
should have a TURN -- a threshold where a cornered warden stops fighting like the trash and rages.
This adds that, the smallest real encounter mechanic: when a boss-tier foe drops to its enrage
threshold, its blows scale up and the room hears it announced ONCE. Nothing else changes -- normal
foes, and a boss above the line, strike exactly as before -- so the escalation is felt only where it
belongs: the back half of a boss fight, which now bites.

Deterministic (a HP threshold, not a die) and self-healing (the flag clears when the boss recovers
above the line, so a rematch re-announces). `boss_phase(npc, raw)` returns the possibly-scaled blow
and a one-time transition line; combat._resolve_npc_blow calls it as it computes a foe's strike.
"""

from __future__ import annotations

from kernel.world.seed import Npc
from kernel.world.session import sentence_case

ENRAGE_AT = 0.30  # a boss at or below this fraction of its max HP enrages
ENRAGE_MULT = 1.5  # how much harder an enraged boss's blows land


def is_boss(npc: Npc) -> bool:
    """Whether a foe is boss-tier (the only foes that gain a phase; elites and trash do not)."""
    return npc.get("tier") == "boss"


def is_enraged(npc: Npc) -> bool:
    """Whether a boss is currently in its enraged phase (below the threshold, second gear on)."""
    return bool(npc.get("enraged"))


def boss_phase(npc: Npc, raw: int) -> tuple[int, str]:
    """Adjust a boss's outgoing blow for its phase, and report a one-time transition. Returns
    (blow, line): `blow` is `raw` scaled up while enraged (unchanged for a non-boss or a healthy
    boss); `line` is the enrage announcement the first time it crosses the line, else ''. A boss
    that recovers above the threshold clears its own flag, so the next descent re-announces."""
    max_hp = npc.get("hp", 0)
    if not is_boss(npc) or max_hp <= 0:
        return raw, ""
    if npc.get("hp_now", max_hp) / max_hp > ENRAGE_AT:
        npc.pop(
            "enraged", None
        )  # healthy again (a rematch after recovery): re-arm the announcement
        return raw, ""
    newly = not npc.get("enraged")
    npc["enraged"] = True
    blow = max(raw + 1, int(raw * ENRAGE_MULT))  # always a real increase, even for a tiny raw
    line = f"{sentence_case(npc['name'])} enrages, and its blows redouble!" if newly else ""
    return blow, line
