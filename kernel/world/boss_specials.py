"""CARD: boss_specials -- a telegraphed boss SPECIAL: a wind-up you can read, then an unleash.

Boss fights had a second gear (kernel.world.boss_phases: a wounded boss enrages and hits harder),but
every blow still arrived the same instant it was thrown -- nothing to READ, nothing to answer. This
is the encounter mechanic that gear was building toward: a telegraphed special. Once enraged, a boss
may spend a beat WINDING UP (it announces the wind-up and lands no blow that beat), and on the NEXT
beat it UNLEASHES. The wind-up is a free beat for the hero to heal, ward, or run: the fight is
a conversation, not a slugfest.

Three `kind`s of unleash give bosses mechanic VARIETY, not just flavour:
  * `strike` (default) -- a heavier hit whose affliction is guaranteed, not merely rolled.
  * `mend`            -- the boss heals, turning the fight into a DPS race: out-damage the heal
                         or it never ends. Lands only a normal blow, not a spike.
  * `drain`           -- vampiric: it spikes the hero AND heals itself for half the blow. Unlike
                         `mend`, the heal RIDES the hit, so you mitigate/interrupt it, not out-DPS.

Data-driven and opt-in: a boss declares a `special` ({kind?, telegraph, mult?, heal?, cadence?}) in
the seed. The charge is deterministic once begun (a flag on the NPC, cleared on unleash) and
self-limiting (only an enraged boss winds up, at most 1-in-`cadence` of its beats).
combat._resolve_npc_blow calls it as it resolves the boss's strike.
"""

from __future__ import annotations

import random

from kernel.world.seed import Npc
from kernel.world.session import sentence_case

#: Runtime RNG for the charge cadence: encounter variety, not security. Tests monkeypatch it.
_SPECIAL_RNG = random.Random()  # nosec B311  # noqa: S311

DEFAULT_MULT = 2  # how much harder a `strike` unleash lands, atop any enrage scaling
DEFAULT_CADENCE = 3  # begin a wind-up on at most 1-in-this of an enraged boss's beats
DEFAULT_HEAL = 20  # HP a `mend` special restores per unleash (seed overrides with `heal`)


def is_charging(npc: Npc) -> bool:
    """Whether this boss is mid-wind-up (it telegraphed last beat and unleashes on this one)."""
    return bool(npc.get("charging"))


def maybe_begin_charge(npc: Npc) -> str:
    """On an enraged boss's beat, maybe BEGIN a special: set the charging flag and return the
    telegraph line. Returns '' (and starts nothing) for a non-boss, a boss without a `special`, a
    boss not yet enraged, one already charging, or when the cadence roll declines. The wind-up beat
    lands no blow (the caller returns this line), so the hero gets a beat to answer."""
    from kernel.world.boss_phases import is_boss, is_enraged

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
    """Resolve a charging boss's UNLEASH: clear the flag and return (blow, line), dispatched on the
    special's `kind`. The caller applies the boss's `inflicts` as a GUARANTEED effect on this hit
    (kernel.world.afflictions.inflict). A non-charging boss is unchanged (raw, '')."""
    if not is_charging(npc):
        return raw, ""
    npc.pop("charging", None)
    special = npc.get("special") or {}
    name = sentence_case(npc["name"])
    if special.get("kind") == "mend":
        raw_heal = special.get("heal", DEFAULT_HEAL)
        heal = raw_heal if isinstance(raw_heal, int) and raw_heal > 0 else DEFAULT_HEAL
        cap = npc.get("hp", 0)  # never past full health
        before = npc.get("hp_now", cap)
        npc["hp_now"] = min(cap, before + heal)
        mended = npc["hp_now"] - before
        return raw, f"{name} knits its wounds shut (+{mended} HP) -- burn it down!"
    if special.get("kind") == "drain":  # vampiric: spike the hero AND drink the wound to heal
        raw_mult = special.get("mult", DEFAULT_MULT)
        mult = raw_mult if isinstance(raw_mult, int) else DEFAULT_MULT
        blow = max(raw + 1, raw * max(2, mult))
        drained = max(1, blow // 2)  # heal half the spike; the heal RIDES the hit, unlike `mend`
        cap = npc.get("hp", 0)
        before = npc.get("hp_now", cap)
        npc["hp_now"] = min(cap, before + drained)
        gained = npc["hp_now"] - before
        return blow, f"{name} drinks your wound (+{gained} HP) as it strikes -- mitigate or fall!"
    # default `strike`: a heavy spike
    raw_mult = special.get("mult", DEFAULT_MULT)
    mult = raw_mult if isinstance(raw_mult, int) else DEFAULT_MULT
    blow = max(raw + 1, raw * max(2, mult))  # always a real spike, even for a tiny raw
    return blow, f"{name} unleashes its special!"
