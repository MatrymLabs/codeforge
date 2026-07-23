"""CARD: combat -- the training loop: strike, defeat, hand off to the leveling engine.

Assembly card: npcs (targets) + stats (damage). Damage is deterministic in v0: no dice
yet, so every number in the test twin is exact. The one randomness is a defeated foe's
WEIGHTED loot roll (`_roll_loot`, parts.shelf.weighted_table), and even that is seedable: it draws
from `_LOOT_RNG`, a module-level RNG tests replace for exact outcomes. The dummy reassembles on
defeat -- it is a training dummy; collapsing is its job. A landed strike advances the combat clock
(`combat_clock`), so cooldowns thaw and statuses age as rounds pass. When a foe falls,
combat hands the reward to the leveling engine (`progression_awards`) rather than climbing
the curves itself: damage, timing, and progression are separate responsibilities.

An NPC that carries a seed `atk` stat strikes back when it survives a
blow (the training dummy carries none, so it stays passive). If a
counter-strike would fell the player, a training-ground failsafe
restores them in place -- a fight never leaves anyone in a broken state.
"""

import random

from parts.shelf.weighted_table import WeightedTable
from parts.world import items
from parts.world.combat_clock import advance as advance_clock
from parts.world.encounter_log import witness
from parts.world.engineer import emergency_repair
from parts.world.events import announce, announce_frame
from parts.world.frames import StrikeFrame
from parts.world.npcs import NPCS, trace_npc
from parts.world.progression_awards import award_jp, award_tp, award_xp
from parts.world.seed import Npc
from parts.world.session import Session, display_name, sentence_case

# Loot-only randomness. Combat MATH stays deterministic (no dice in damage); only a defeated foe's
# WEIGHTED loot table rolls here. A module-level RNG so tests seed or replace it for exact draws.
_LOOT_RNG = random.Random()  # nosec B311 -- game loot, not security; seeded for tests, not secrecy

DAMAGE_BASE = 3  # damage dealt = DAMAGE_BASE + strength // 3


def strike_power(session: Session) -> int:
    assert session.stats is not None
    return DAMAGE_BASE + session.stats.get("strength").base // 3


def npc_strike_power(npc: Npc) -> int:
    """An NPC's counter-attack damage. Deterministic in v0 (no dice); 0 means passive."""
    return max(0, npc.get("atk", 0))


def _fall_and_recover(session: Session, npc: Npc) -> str:
    """Safe defeat: a felled player is restored in place. Never a broken state (v0 failsafe)."""
    hp = session.resources["hp"]
    session.resources["hp"] = hp.heal(hp.maximum)  # back to full; location unchanged
    witness("fall", npc["name"], "felled the player; the failsafe restored them")
    return (
        f"You fall to {npc['name']}, and wake restored at full health. (Training-ground failsafe.)"
    )


def _resolve_npc_blow(session: Session, npc: Npc, verb: str) -> str:
    """One NPC blow against the player: damage, room broadcast (typed StrikeFrame),
    the Engineer's Emergency Repair reaction, and the training-ground failsafe. `verb`
    is the opening phrase ('strikes back', 'lunges') so a counter and an unprovoked
    strike share one resolution. Returns the attacker-facing line(s) with NO leading
    newline; a passive NPC (atk 0) cannot land a blow and returns ''."""
    power = npc_strike_power(npc)
    if power <= 0:
        return ""  # the training dummy and every peaceful NPC: no blow
    session.resources["hp"] = session.resources["hp"].damage(power)
    name = sentence_case(npc["name"])
    announce_frame(
        session.location,
        StrikeFrame(attacker_name=name, verb=verb, target_id=session.player_id, amount=power),
        exclude=session.player_id,
    )
    hp = session.resources["hp"]
    line = f"{name} {verb} for {power}. (HP {hp.current}/{hp.maximum})"
    # The Engineer's Emergency Repair reacts to a dangerous blow: it auto-heals once (then cools
    # down), and can pull the player back from a fall. Returns None for anyone else, or on cooldown.
    repair = emergency_repair(session)
    if repair is not None:
        line = f"{line}\n{repair}"
        hp = session.resources["hp"]  # re-read: the repair healed, so the fall-check sees the save
    if hp.is_depleted:
        return f"{line}\n{_fall_and_recover(session, npc)}"
    return line


def _counter_attack(session: Session, npc: Npc) -> str:
    """A surviving NPC with an atk stat strikes back. Passive NPCs return ''; text is projection."""
    body = _resolve_npc_blow(session, npc, "strikes back")
    return f"\n{body}" if body else ""


def open_strike(session: Session, npc: Npc) -> str:
    """An aggressive NPC strikes first, unprovoked -- the world-beat twin of the counter.
    Same resolution (damage, failsafe, Engineer reaction); only the opening verb differs.
    Driven by parts.world.aggression on the tick, not by a player's blow. Passive NPCs return ''."""
    body = _resolve_npc_blow(session, npc, "lunges")
    return f"\n{body}" if body else ""


def attack(session: Session, word: str) -> str:
    """One strike of the training loop."""
    if session.stats is None:
        return "You have no calling yet. Type JOBS before you pick a fight."
    nid = trace_npc(word, session.location)
    if nid is None:
        return "There is no one like that here."
    npc = NPCS[nid]
    if npc["hp"] <= 0:
        return f"{sentence_case(npc['name'])} is not something you can fight."
    dmg = strike_power(session)
    npc["hp_now"] -= dmg
    advance_clock(session)  # a landed strike is a combat action: cooldowns thaw, statuses age
    if npc.get("aggressive"):
        session.aggro_beats[nid] = 0  # the player answered the foe: re-engage its leash from zero
    announce(
        session.location,
        f"{display_name(session.player_id)} strikes {npc['name']} for {dmg}.",
        exclude=session.player_id,
    )
    if npc["hp_now"] > 0:
        hit = f"You strike {npc['name']} for {dmg}. ({npc['hp_now']}/{npc['hp']})"
        # An aggressive NPC's blow arrives on the world beat (parts.world.aggression), never as a
        # counter, so it strikes exactly once per tick -- never both counter and open-strike.
        counter = "" if npc.get("aggressive") else _counter_attack(session, npc)
        return f"{hit}{counter}"
    npc["hp_now"] = npc["hp"]  # the dummy reassembles at full health
    announce(
        session.location,
        f"{sentence_case(npc['name'])} collapses -- then reassembles itself.",
        exclude=session.player_id,
    )
    witness("defeat", npc["name"], "fell in combat")
    defeat = f"You strike {npc['name']} for {dmg}. It collapses -- then reassembles itself."
    rewards = award_xp(session, npc["xp"])
    for extra in (award_jp(session, npc["xp"]), award_tp(session, npc["xp"])):
        if extra:
            rewards = f"{rewards}\n{extra}"
    result = f"{defeat}\n{rewards}"
    # guaranteed drops, then one weighted loot roll -- both spawn fresh instances on the floor
    haul = "\n".join(
        part for part in (_spawn_drops(session, npc), _roll_loot(session, npc)) if part
    )
    if haul:
        result = f"{result}\n{haul}"
    from parts.world import quest  # lazy: combat is the low-level loop; the quest hook rides on top

    quest_line = quest.on_event(session, "defeat", nid)  # a boss's fall may complete a story beat
    return f"{result}\n{quest_line}" if quest_line else result


def _spawn_loot(session: Session, prototype: str) -> str:
    """Spawn one loot instance into the room (object instancing, so it never collides with the seed
    original), announce it, and return the line -- or '' if the prototype is unknown or at its
    instance ceiling (skipped, never a crash). The shared spawn used by drops and the loot roll."""
    try:
        iid = items.clone(prototype, session.location)
    except items.ItemError:
        return ""
    line = f"{sentence_case(items.ITEMS[iid]['name'])} drops to the ground."
    announce(session.location, line, exclude=session.player_id)
    return line


def _spawn_drops(session: Session, npc: Npc) -> str:
    """Spawn a defeated NPC's GUARANTEED drops (`drops`): a fresh instance of each. Returns the
    drop line(s), or ''."""
    return "\n".join(line for p in npc.get("drops", []) if (line := _spawn_loot(session, p)))


def _roll_loot(session: Session, npc: Npc) -> str:
    """Roll a defeated NPC's WEIGHTED loot table (`loot`) once and spawn the outcome. Outcomes are
    item prototypes plus the reserved `nothing` (a no-drop weight); the draw uses the module RNG so
    it is seedable. Returns the loot line, or '' (no table, or 'nothing' rolled)."""
    table = npc.get("loot")
    if not table:
        return ""
    outcome = WeightedTable(list(table.items())).pick(_LOOT_RNG)
    return "" if outcome == "nothing" else _spawn_loot(session, outcome)
