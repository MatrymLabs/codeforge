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

from parts.shelf import affixes
from parts.shelf.reward_curve import jp_for_kill, xp_for_kill
from parts.shelf.weighted_table import WeightedTable
from parts.world import items
from parts.world.combat_clock import advance as advance_clock
from parts.world.encounter_log import witness
from parts.world.engineer import emergency_repair
from parts.world.events import announce, announce_frame
from parts.world.frames import StrikeFrame
from parts.world.npcs import NPCS, npcs_in, trace_npc
from parts.world.progression_awards import award_jp, award_tp, award_xp
from parts.world.seed import Npc
from parts.world.session import Session, display_name, sentence_case

# Loot-only randomness. Combat MATH stays deterministic (no dice in damage); only a defeated foe's
# WEIGHTED loot table rolls here. A module-level RNG so tests seed or replace it for exact draws.
_LOOT_RNG = random.Random()  # nosec B311 -- game loot, not security; seeded for tests, not secrecy

DAMAGE_BASE = 3  # damage dealt = DAMAGE_BASE + strength // 3

# Readable names for the element/status codes a foe's blow may carry (seed RESIST_ORDER codes).
_ELEMENT_NAMES = {
    "FIR": "flame",
    "ICE": "frost",
    "LGT": "lightning",
    "WND": "gale",
    "ERT": "stone",
    "WTR": "flood",
    "HLY": "radiance",
    "DRK": "shadow",
    "PSN": "venom",
    "CRS": "curse",
}


def _typed_blow(session: Session, npc: Npc, power: int) -> tuple[int, int, str]:
    """Scale a blow of magnitude `power` by the player's resistance to the NPC's attack element.
    Returns (damage_to_take, hp_to_heal, note). An untyped blow (no element) passes through
    unchanged. Weak amplifies, Resist halves (floored 1), Immune nullifies, Absorb heals -- the
    same resistance grid the score sheet renders, now real in a fight."""
    element = npc.get("attack_element")
    if not element:
        return power, 0, ""
    from parts.world.character_view import session_resistance

    level = session_resistance(session, element)
    tag = _ELEMENT_NAMES.get(element, element)
    if level == "Weak":
        return power + power // 2, 0, f" The {tag} finds a weakness!"
    if level == "Resist":
        return max(1, power // 2), 0, f" You shrug off much of the {tag}."
    if level == "Immune":
        return 0, 0, f" You are immune to {tag}."
    if level == "Absorb":
        return 0, power, f" You drink in the {tag} (+{power} HP)."
    return power, 0, ""  # Normal: unchanged


def foe_resistance(npc: Npc, code: str) -> str:
    """A foe's resistance level to an element/status `code`, from its optional grid. The mirror of
    session_resistance -- a foe that declares nothing (or has no grid at all) reads Normal."""
    return npc.get("resistances", {}).get(code, "Normal")


def typed_hit(npc: Npc, element: str | None, dmg: int) -> tuple[int, str]:
    """Scale OUTGOING player damage by the foe's resistance to the ability's `element`. Untyped (no
    element) passes through unchanged. Weak +50%, Resist halves (floored 1), Immune/Absorb nullify
    -- a player's blow can never heal a foe, so a foe's Absorb reads as full immunity. Returns
    (damage, note): freeze the fire creature, don't burn it."""
    if not element:
        return dmg, ""
    level = foe_resistance(npc, element)
    tag = _ELEMENT_NAMES.get(element, element)
    if level == "Weak":
        return dmg + dmg // 2, f" The {tag} tears into it!"
    if level == "Resist":
        return max(1, dmg // 2), f" It shrugs off much of the {tag}."
    if level in ("Immune", "Absorb"):
        return 0, f" It is immune to {tag}."
    return dmg, ""  # Normal: unchanged


def _stat_bonus(session: Session, stat: str) -> int:
    """The total flat bonus to a derived stat from everything a character carries: equipped gear,
    the active job's perks, and the sworn Order. Combat reads the SAME composition as the score
    sheet (character_view.session_stat_modifiers), so gear and perks are real in a fight, not paper.
    An ungeared, orderless character gets 0 -- the base balance is unchanged."""
    from parts.world.character_view import session_stat_modifiers

    return sum(mod.flat for mod in session_stat_modifiers(session).get(stat, []))


def strike_power(session: Session) -> int:
    assert session.stats is not None
    # Base damage (attribute-driven), plus the ATK bonus your gear/perks/Order add on top.
    return DAMAGE_BASE + session.stats.get("strength").base // 3 + _stat_bonus(session, "ATK")


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


def _fall_to_death(session: Session, npc: Npc) -> str:
    """A LETHAL foe (a boss) fells the player: no in-place failsafe. The player wakes at their start
    room at full health, and the foe recovers -- the fight is earned again. Levels are kept."""
    from parts.world.world import START_ROOM  # lazy: world binds seed state at import

    session.location = START_ROOM
    hp = session.resources["hp"]
    session.resources["hp"] = hp.heal(hp.maximum)
    npc["hp_now"] = npc["hp"]  # the boss recovers for the rematch
    witness("fall", npc["name"], "felled the player, who woke where their road began")
    foe = sentence_case(npc["name"])
    return (
        f"{foe} fells you. Darkness takes you -- and you wake where your road "
        "began, whole but shaken. It still waits below."
    )


def _resolve_npc_blow(session: Session, npc: Npc, verb: str) -> str:
    """One NPC blow against the player: damage, room broadcast (typed StrikeFrame),
    the Engineer's Emergency Repair reaction, and the training-ground failsafe. `verb`
    is the opening phrase ('strikes back', 'lunges') so a counter and an unprovoked
    strike share one resolution. Returns the attacker-facing line(s) with NO leading
    newline; a passive NPC (atk 0) cannot land a blow and returns ''."""
    raw = npc_strike_power(npc)
    if raw <= 0:
        return ""  # the training dummy and every peaceful NPC: no blow
    # Your DEF (from gear/perks/Order) turns the blow, but a landed hit always stings: floor at 1.
    power = max(1, raw - _stat_bonus(session, "DEF"))
    warded = session.statuses.get("barrier", 0) > 0
    if warded:  # a deployed barrier (Engineer) turns half the blow while it holds
        power = max(1, power // 2)
    # A typed blow (the foe's attack_element) is scaled by the player's resistance to that element.
    power, healed, resist_note = _typed_blow(session, npc, power)
    session.resources["hp"] = session.resources["hp"].damage(power)
    if healed:  # Absorb: the element mends instead of harming
        session.resources["hp"] = session.resources["hp"].heal(healed)
    name = sentence_case(npc["name"])
    if power > 0:  # a nullified or absorbed blow lands nothing: no StrikeFrame to broadcast
        announce_frame(
            session.location,
            StrikeFrame(attacker_name=name, verb=verb, target_id=session.player_id, amount=power),
            exclude=session.player_id,
        )
    hp = session.resources["hp"]
    ward = " Your barrier turns half of it." if warded else ""
    if power > 0:
        body = f"{name} {verb} for {power}.{ward}{resist_note}"
    else:  # Immune or Absorb: the blow lands no damage, the note carries the outcome
        body = f"{name} {verb}.{resist_note}"
    line = f"{body} (HP {hp.current}/{hp.maximum})"
    # The Engineer's Emergency Repair reacts to a dangerous blow: it auto-heals once (then cools
    # down), and can pull the player back from a fall. Returns None for anyone else, or on cooldown.
    repair = emergency_repair(session)
    if repair is not None:
        line = f"{line}\n{repair}"
        hp = session.resources["hp"]  # re-read: the repair healed, so the fall-check sees the save
    if hp.is_depleted:
        fall = (
            _fall_to_death(session, npc) if npc.get("lethal") else _fall_and_recover(session, npc)
        )
        return f"{line}\n{fall}"
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


def _reward_amounts(session: Session, npc: Npc) -> tuple[int, int, int]:
    """The (XP, JP, TP) a kill pays. A levelled foe scales through the challenge curve -- fight up
    and earn more, grays pay nothing -- by the gap between fighter and foe; a levelless foe keeps
    its flat `xp` for all three (the tutorial economy). TP rides the job axis alongside JP."""
    level = npc.get("level")
    if level is None:
        flat = npc["xp"]
        return (flat, flat, flat)
    tier = npc.get("tier", "normal")
    job = session.job
    job_level = session.job_progress[job].job_level if job and job in session.job_progress else 1
    xp = xp_for_kill(session.level, level, tier)
    jp = jp_for_kill(job_level, level, tier)
    return (xp, jp, jp)


# Coins a kill drops per tier, multiplied by the foe's level (a boss is worth far more than a
# stray). A levelless tutorial foe pays a token purse off its flat xp, so first-forge still earns.
_TIER_COINS = {"normal": 1, "elite": 3, "boss": 10}


def _coin_reward(npc: Npc) -> int:
    """The coins a felled foe drops. Scales with level and tier; a levelless foe pays a token."""
    level = npc.get("level")
    if level is None:
        return max(1, npc["xp"] // 10)
    return level * _TIER_COINS.get(npc.get("tier", "normal"), 1)


def land_hit(session: Session, npc: Npc, nid: str, dmg: int) -> tuple[bool, str]:
    """Apply `dmg` to `npc` and resolve the outcome; return (defeated, tail).

    Advances the combat clock, re-engages an aggressive foe, and on defeat reassembles the target,
    witnesses it, awards XP/JP/TP, spawns drops + a loot roll, and fires the quest hook -- returning
    that as `tail` (empty when the foe survives). The CALLER owns the actor's own line, the room
    strike broadcast, and any counter, so `attack` and an ability share this defeat/award core."""
    npc["hp_now"] -= dmg
    advance_clock(session)  # a landed strike is a combat action: cooldowns thaw, statuses age
    if npc.get("aggressive"):
        session.aggro_beats[nid] = 0  # the player answered the foe: re-engage its leash from zero
    if npc["hp_now"] > 0:
        return (False, "")
    npc["hp_now"] = npc["hp"]  # the dummy reassembles at full health
    npc.pop("burn", None)  # a reassembled foe is whole again -- any burn is quenched
    announce(
        session.location,
        f"{sentence_case(npc['name'])} collapses -- then reassembles itself.",
        exclude=session.player_id,
    )
    witness("defeat", npc["name"], "fell in combat")
    xp_award, jp_award, tp_award = _reward_amounts(session, npc)
    rewards = award_xp(session, xp_award)
    for extra in (award_jp(session, jp_award), award_tp(session, tp_award)):
        if extra:
            rewards = f"{rewards}\n{extra}"
    coins = _coin_reward(npc)
    session.coins += coins
    rewards = f"{rewards}\nYou find {coins} coins. (purse: {session.coins})"
    # guaranteed drops, then one weighted loot roll -- both spawn fresh instances on the floor
    haul = "\n".join(
        part for part in (_spawn_drops(session, npc), _roll_loot(session, npc)) if part
    )
    if haul:
        rewards = f"{rewards}\n{haul}"
    from parts.world import quest  # lazy: combat is the low-level loop; the quest hook rides on top

    quest_line = quest.on_event(session, "defeat", nid)  # a boss's fall may complete a story beat
    if quest_line:
        rewards = f"{rewards}\n{quest_line}"
    return (True, rewards)


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
    exposed = session.statuses.get("analyzed", 0) > 0
    if exposed:  # a Diagnostic Scan revealed the foe's weak point: +50% damage while it holds
        dmg += dmg // 2
    weak = " (weak point!)" if exposed else ""
    announce(
        session.location,
        f"{display_name(session.player_id)} strikes {npc['name']} for {dmg}.",
        exclude=session.player_id,
    )
    struck = f"You strike {npc['name']} for {dmg}.{weak}"
    defeated, tail = land_hit(session, npc, nid, dmg)
    if not defeated:
        # An aggressive NPC's blow arrives on the world beat (parts.world.aggression), never as a
        # counter, so it strikes exactly once per tick -- never both counter and open-strike.
        counter = "" if npc.get("aggressive") else _counter_attack(session, npc)
        return f"{struck} ({npc['hp_now']}/{npc['hp']}){counter}"
    return f"{struck} It collapses -- then reassembles itself.\n{tail}"


BURN_TICKS = 3  # how many world beats a `brand` burn lasts before it burns out


def apply_burn(npc: Npc, damage: int, ticks: int = BURN_TICKS) -> None:
    """Lay a burn damage-over-time on a foe (a `brand` ability). It saps `damage` HP each world beat
    for `ticks` beats. A fresh brand refreshes the burn rather than stacking."""
    npc["burn"] = {"damage": max(1, damage), "ticks": max(1, ticks)}


def tick_burns(session: Session) -> str:
    """On the world beat, sap HP from every burning foe in the room, age the burn, and drop it when
    it burns out. A burn never fells a foe (floored at 1) -- it wears it down, but you land the
    finishing blow. Returns the lines the player sees, or '' when nothing is burning. Mutates NPC
    runtime state only (hp_now, burn), never the player's."""
    lines = []
    for nid in npcs_in(session.location):
        npc = NPCS[nid]
        burn = npc.get("burn")
        if not burn or npc["hp_now"] <= 0:
            continue
        npc["hp_now"] = max(1, npc["hp_now"] - burn["damage"])
        bar = f"{npc['hp_now']}/{npc['hp']}"
        lines.append(f"{sentence_case(npc['name'])} smoulders for {burn['damage']}. ({bar})")
        burn["ticks"] -= 1
        if burn["ticks"] <= 0:
            npc.pop("burn", None)
    return ("\n".join(lines) + "\n") if lines else ""


def _spawn_loot(session: Session, prototype: str, level: int = 0) -> str:
    """Spawn one loot instance into the room (object instancing, so it never collides with the seed
    original), announce it, and return the line -- or '' if the prototype is unknown or at its
    instance ceiling (skipped, never a crash). The shared spawn used by drops and the loot roll.

    An EQUIPPABLE drop from a levelled foe runs through the affix factory (parts.shelf.affixes): it
    rolls a rarity + named affixes onto the instance, so one base weapon falls as a spread of gear
    ('a Cruel notched blade of the Bear [rare]'). Non-gear and levelless drops are unchanged."""
    try:
        iid = items.clone(prototype, session.location)
    except items.ItemError:
        return ""
    item = items.ITEMS[iid]
    rarity = ""
    if item.get("slot") and level > 0:  # a levelled foe's gear rolls a rarity + affixes
        base = item["name"]  # drop the leading article so "Fleet a blade" reads "Fleet blade"
        for article in ("a ", "an ", "the "):
            if base.lower().startswith(article):
                base = base[len(article) :]
                break
        rolled = affixes.roll(_LOOT_RNG, base, item["mods"], level)
        item["name"], item["mods"], item["rarity"] = rolled.name, rolled.mods, rolled.rarity
        rarity = "" if rolled.rarity == "common" else f" [{rolled.rarity}]"
    line = f"{sentence_case(item['name'])}{rarity} drops to the ground."
    announce(session.location, line, exclude=session.player_id)
    return line


def _spawn_drops(session: Session, npc: Npc) -> str:
    """Spawn a defeated NPC's GUARANTEED drops (`drops`): a fresh instance of each. Returns the
    drop line(s), or ''. A levelled foe's equippable drops roll a rarity + affixes."""
    level = npc.get("level", 0)
    return "\n".join(line for p in npc.get("drops", []) if (line := _spawn_loot(session, p, level)))


def _roll_loot(session: Session, npc: Npc) -> str:
    """Roll a defeated NPC's WEIGHTED loot table (`loot`) once and spawn the outcome. Outcomes are
    item prototypes plus the reserved `nothing` (a no-drop weight); the draw uses the module RNG so
    it is seedable. Returns the loot line, or '' (no table, or 'nothing' rolled)."""
    table = npc.get("loot")
    if not table:
        return ""
    outcome = WeightedTable(list(table.items())).pick(_LOOT_RNG)
    return "" if outcome == "nothing" else _spawn_loot(session, outcome, npc.get("level", 0))
