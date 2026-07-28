"""CARD: boss_specials -- a telegraphed boss SPECIAL: a wind-up you can read, then a heavy unleash.

Boss fights had a second gear (parts.world.boss_phases: a wounded boss enrages and hits harder), but
every blow still arrived the same instant it was thrown -- nothing to READ, nothing to answer. This
is the encounter mechanic that gear was building toward: a telegraphed special. Once enraged, a boss
may spend a beat WINDING UP (it announces the wind-up and lands no blow that beat), and on the NEXT
beat it UNLEASHES -- a heavier hit whose affliction is guaranteed, not merely rolled. The wind-up is
a free beat for the hero to heal, ward, or run: the fight becomes a conversation, not a slugfest.

Data-driven and opt-in: a boss declares a `special` ({telegraph, mult?, cadence?}) in the seed. The
charge is deterministic once begun (a flag on the NPC, cleared on unleash) and self-limiting (only
an enraged boss winds up, at most 1-in-`cadence` of its beats). combat._resolve_npc_blow calls it as
it resolves the boss's strike; the guaranteed affliction rides the boss's existing `inflicts`.
"""

from __future__ import annotations

import random

from parts.world.seed import Npc
from parts.world.session import sentence_case

#: Runtime RNG for the charge cadence: encounter variety, not security. Tests monkeypatch it.
_SPECIAL_RNG = random.Random()  # nosec B311 -- combat variety, not cryptographic

DEFAULT_MULT = 2  # how much harder an unleashed special lands, on top of any enrage scaling
DEFAULT_CADENCE = 3  # begin a wind-up on at most 1-in-this of an enraged boss's beats


def is_charging(npc: Npc) -> bool:
    """Whether this boss is mid-wind-up (it telegraphed last beat and unleashes on this one)."""
    return bool(npc.get("charging"))


def maybe_begin_charge(npc: Npc) -> str:
    """On an enraged boss's beat, maybe BEGIN a special: set the charging flag and return the
    telegraph line. Returns '' (and starts nothing) for a non-boss, a boss without a `special`, a
    boss not yet enraged, one already charging, or when the cadence roll declines. The wind-up beat
    lands no blow (the caller returns this line), so the hero gets a beat to answer."""
    from parts.world.boss_phases import is_boss, is_enraged

    special = npc.get("special")
    if not special or not is_boss(npc) or not is_enraged(npc) or is_charging(npc):
        return ""
    raw_cadence = special.get("cadence", DEFAULT_CADENCE)
    cadence = raw_cadence if isinstance(raw_cadence, int) else DEFAULT_CADENCE
    if cadence > 1 and _SPECIAL_RNG.randrange(cadence) != 0:
        return ""  # not this beat
    npc["charging"] = True
    telegraph = str(special.get("telegraph") or f"{sentence_case(npc['name'])} gathers its power")
    return f"{telegraph}..."


def unleash(npc: Npc, raw: int) -> tuple[int, str]:
    """Resolve a charging boss's UNLEASH: clear the flag, scale the blow by the special's `mult`,
    return (blow, line). The caller applies the boss's `inflicts` as a GUARANTEED effect on this hit
    (parts.world.afflictions.inflict). A non-charging boss is unchanged (raw, '')."""
    if not is_charging(npc):
        return raw, ""
    npc.pop("charging", None)
    special = npc.get("special") or {}
    raw_mult = special.get("mult", DEFAULT_MULT)
    mult = raw_mult if isinstance(raw_mult, int) else DEFAULT_MULT
    blow = max(raw + 1, raw * max(2, mult))  # always a real spike, even for a tiny raw
    return blow, f"{sentence_case(npc['name'])} unleashes its special!"
