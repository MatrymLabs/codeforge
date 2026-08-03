"""CARD: combat -- the training loop: strike, defeat, hand off to the leveling engine.

Assembly card: npcs (targets) + stats (damage). Damage MATH is deterministic; the one die on a
blow is its VARIANCE -- a rare miss, a rare crit, an occasional glance -- drawn from `_COMBAT_RNG`,
a module-level RNG the test suite installs NEUTRAL (always a normal hit) so every exact number in
the twin still holds, and variance tests force an outcome. A defeated foe's WEIGHTED loot roll
(`_roll_loot`, kernel.shelf.weighted_table) draws from a second seedable RNG, `_LOOT_RNG`. A fall
carries a modest, reversible stake (`_death_toll`): carried coins scatter and a non-lethal fall
wakes at half health -- defeat costs something, so it is no longer consequence-free. A felled foe's
fate is the mortality card's call (`kernel.world.mortality`): a mortal world foe DIES and respawns
on a tier timer (a cleared room stays cleared for a while), while the training dummy and anything a
seed marks `reassembles` stands right back up -- collapsing is its job. A landed strike advances
the combat clock
(`combat_clock`), so cooldowns thaw and statuses age as rounds pass. When a foe falls,
combat hands the reward to the leveling engine (`progression_awards`) rather than climbing
the curves itself: damage, timing, and progression are separate responsibilities.

An NPC that carries a seed `atk` stat strikes back when it survives a
blow (the training dummy carries none, so it stays passive). If a
counter-strike would fell the player, a training-ground failsafe
restores them in place -- a fight never leaves anyone in a broken state.
"""

import random

from kernel.shelf import affixes, target_disambig
from kernel.shelf.reward_curve import jp_for_kill, xp_for_kill
from kernel.shelf.weighted_table import WeightedTable
from kernel.world import items, threat
from kernel.world.boss_phases import boss_phase
from kernel.world.coinage import purse
from kernel.world.combat_clock import advance as advance_clock
from kernel.world.encounter_log import witness
from kernel.world.engineer import emergency_repair
from kernel.world.events import announce, announce_frame
from kernel.world.frames import StrikeFrame
from kernel.world.npcs import NPCS, npcs_in, resolve_npc_target, trace_npc
from kernel.world.progression_awards import award_jp, award_tp, award_xp
from kernel.world.seed import Npc
from kernel.world.session import Session, display_name, sentence_case

# Loot-only randomness. A defeated foe's WEIGHTED loot table rolls here. A module-level RNG so tests
# seed or replace it for exact draws.
_LOOT_RNG = random.Random()  # nosec B311 -- game loot, not security; seeded for tests, not secrecy

# Combat variance -- the ONE die on a blow. Damage MATH stays deterministic; this rolls whether a
# blow whiffs, glances, crits, or lands normally. The test suite installs a NEUTRAL RNG (always a
# normal hit, note below) so exact-number assertions hold; variance tests force an outcome. Live
# play is stochastic -- fights breathe instead of reading off a table.
_COMBAT_RNG = random.Random()  # nosec B311 -- game feel, not security; neutralized in tests

MISS_CHANCE = 0.05  # a blow goes wide: 0 damage
CRIT_CHANCE = 0.10  # a critical strike: CRIT_MULT times damage
GLANCE_CHANCE = 0.15  # a glancing blow: half damage (floored 1)
CRIT_MULT = 2  # a crit doubles the blow


def _apply_variance(dmg: int) -> tuple[int, str]:
    """Roll the one die on a landed blow of magnitude `dmg`. Returns (damage, note):

    - miss (MISS_CHANCE): 0 damage, " (miss!)"
    - crit (CRIT_CHANCE): CRIT_MULT x damage, " (critical!)"
    - glance (GLANCE_CHANCE): half damage (floored 1), " (glancing)"
    - normal (the rest): `dmg` unchanged, "" (no note)

    A non-positive `dmg` passes through untouched (no die on a blow that was already nothing). The
    suite's neutral RNG always rolls into the normal band, so existing exact numbers are preserved.
    """
    if dmg <= 0:
        return dmg, ""
    roll = _COMBAT_RNG.random()
    if roll < MISS_CHANCE:
        return 0, " (miss!)"
    if roll < MISS_CHANCE + CRIT_CHANCE:
        return dmg * CRIT_MULT, " (critical!)"
    if roll < MISS_CHANCE + CRIT_CHANCE + GLANCE_CHANCE:
        return max(1, dmg // 2), " (glancing)"
    return dmg, ""


DAMAGE_BASE = 3  # damage dealt = DAMAGE_BASE + strength // 3

# Death stakes -- a modest, reversible cost so defeat is no longer consequence-free. Carried coins
# scatter on a fall (banked coins are safe -- only what you carry is at risk), and a non-lethal fall
# wakes at half health rather than full. A lethal boss fall already stakes the trip home; it pays
# the coin toll too. The knobs are named so the balance is one edit, not a hunt.
DEATH_COIN_PENALTY = 0.10  # a tenth of carried coins scatter when you fall
DEATH_HP_FRACTION = 0.5  # a non-lethal fall wakes you at this fraction of full health
# K2: a LETHAL death (a real boss, not the training-ground failsafe) also batters your worn gear.
# Dying to a boss is no longer a free trip home + full heal: your gear takes wear you must mend, a
# reversible stake that feeds the same coin sink as combat durability (kernel.world.durability). The
# training-ground failsafe stays gentle (no gear toll) so a new hero learning to fight is not taxed.
DEATH_DURABILITY_TOLL = 10  # points of wear each worn piece takes on a lethal death (a tuning knob)


def _death_toll(session: Session) -> int:
    """Scatter DEATH_COIN_PENALTY of the hero's carried coins on a fall; return the coins lost
    (0 for an empty purse). Banked/vaulted coins are safe -- only the carried purse is staked."""
    lost = int(session.coins * DEATH_COIN_PENALTY)
    session.coins -= lost
    return lost


def _death_gear_toll(session: Session) -> int:
    """Batter the hero's WORN gear on a lethal death: each equipped piece takes a
    DEATH_DURABILITY_TOLL of wear (reversible via `mend`). Returns how many pieces were worn.
    A bare hero (nothing equipped) takes no toll; broken-to-zero pieces floor, never go negative."""
    from kernel.world import durability

    worn = 0
    for iid in session.equipped.values():
        durability.wear(iid, DEATH_DURABILITY_TOLL)  # a clean no-op on any non-gear id
        worn += 1
    return worn


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
    from kernel.world.character_view import session_resistance

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


def elemental_profile(npc: Npc) -> str:
    """A readable line on a foe's elemental nature: the element its blows carry and its non-normal
    resistances (weaknesses, resistances, immunities, absorptions). '' when the foe is wholly
    untyped -- nothing to learn. This is what makes the resistance system discoverable, not
    guesswork: the player learns to freeze the fire creature instead of dying to find out."""
    lines: list[str] = []
    attack = npc.get("attack_element")
    if attack:
        lines.append(f"Its blows strike with {_ELEMENT_NAMES.get(attack, attack)}.")
    by_level: dict[str, list[str]] = {}
    for code, level in npc.get("resistances", {}).items():
        if level != "Normal":
            by_level.setdefault(level, []).append(_ELEMENT_NAMES.get(code, code))
    labels = {"Weak": "Weak to", "Resist": "Resists", "Immune": "Immune to", "Absorb": "Absorbs"}
    for level in ("Weak", "Resist", "Immune", "Absorb"):
        elems = by_level.get(level)
        if elems:
            lines.append(f"{labels[level]} {', '.join(sorted(elems))}.")
    return " ".join(lines)


def examine_foe(session: Session, word: str) -> str:
    """`examine <target>` -- read a creature's condition and elemental nature (the JRPG 'scan').
    Any calling can do it and it applies no status. An unknown target and a peaceful NPC both
    fail cleanly, so a curious player is never punished for looking."""
    if not word.strip():
        return "Examine whom? Try: examine <target>"
    nid = trace_npc(word, session.location)
    if nid is None:
        return "There is no one like that here to examine."
    npc = NPCS[nid]
    name = sentence_case(npc["name"])
    if npc["hp"] <= 0:
        return f"{name} is no creature you can fight -- nothing to size up."
    profile = elemental_profile(npc)
    nature = f" {profile}" if profile else " You sense no elemental nature about it."
    return f"{name}: {npc['hp_now']}/{npc['hp']} HP.{nature}"


def _wear_gear(session: Session, slot: str) -> None:
    """Wear the piece in `slot` by one point, if the hero has one equipped there. The economy's
    durability drain: a struck blade and a dented breastplate are what make repair (a coin sink)
    necessary. A bare slot is a clean no-op."""
    from kernel.world import durability

    iid = session.equipped.get(slot)
    if iid is not None:
        durability.wear(iid)


def _stat_bonus(session: Session, stat: str) -> int:
    """The total flat bonus to a derived stat from everything a character carries: equipped gear,
    the active job's perks, and the sworn Order. Combat reads the SAME composition as the score
    sheet (character_view.session_stat_modifiers), so gear and perks are real in a fight, not paper.
    An ungeared, orderless character gets 0 -- the base balance is unchanged."""
    from kernel.world.character_view import session_stat_modifiers

    return sum(mod.flat for mod in session_stat_modifiers(session).get(stat, []))


def strike_power(session: Session) -> int:
    assert session.stats is not None
    # Base damage (attribute-driven), plus the ATK bonus your gear/perks/Order add on top.
    return DAMAGE_BASE + session.stats.get("strength").base // 3 + _stat_bonus(session, "ATK")


def npc_strike_power(npc: Npc) -> int:
    """An NPC's counter-attack damage. Deterministic in v0 (no dice); 0 means passive."""
    return max(0, npc.get("atk", 0))


def _fall_and_recover(session: Session, npc: Npc) -> str:
    """Non-lethal defeat: the failsafe pulls a felled player back in place (never a broken state),
    but the fall now carries a stake. Carried coins scatter and the hero wakes at HALF health, not
    full, so defeat costs something. Location unchanged."""
    lost = _death_toll(session)
    hp = session.resources["hp"]
    revived = max(1, int(hp.maximum * DEATH_HP_FRACTION))  # wake at DEATH_HP_FRACTION of full
    session.resources["hp"] = hp.heal(hp.maximum).damage(hp.maximum - revived)  # -> exactly revived
    witness("fall", npc["name"], "felled the player; the failsafe restored them, at a cost")
    toll = f" You scatter {purse(lost)} in the fall." if lost else ""
    return f"You fall to {npc['name']}, and wake at half health.{toll} (Training-ground failsafe.)"


def _fall_to_death(session: Session, npc: Npc) -> str:
    """A LETHAL foe (a boss) fells the player: no in-place failsafe. The player wakes at their start
    room at full health, and the foe recovers -- the fight is earned again. A real death carries
    real, reversible stakes: scattered coins, battered gear (K2), and XP progress toward the next
    level (K5) -- but NEVER a level: the hero keeps every level they earned."""
    from kernel.world.progression_awards import apply_xp_debt
    from kernel.world.world import START_ROOM  # lazy: world binds seed state at import

    lost = _death_toll(session)
    battered = _death_gear_toll(session)  # K2: a real death batters your gear (mend it)
    debt = apply_xp_debt(session)  # K5: a real death costs progress toward the next level
    session.location = START_ROOM
    hp = session.resources["hp"]
    session.resources["hp"] = hp.heal(hp.maximum)
    npc["hp_now"] = npc["hp"]  # the boss recovers for the rematch
    witness("fall", npc["name"], "felled the player, who woke where their road began")
    foe = sentence_case(npc["name"])
    toll = f" {purse(lost)} scatters from your purse." if lost else ""
    gear = f" Your gear is battered in the fall ({battered} worn; MEND it)." if battered else ""
    xp = f" The fall sets your progress back {debt} XP (your level holds)." if debt else ""
    return (
        f"{foe} fells you. Darkness takes you -- and you wake where your road "
        f"began, whole but shaken.{toll}{gear}{xp} It still waits below."
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
    # A telegraphed boss SPECIAL (kernel.world.boss_specials): an enraged boss may spend this beat
    # WINDING UP (it announces and lands no blow, a free beat for the hero), then UNLEASH next --
    # a heavier hit whose affliction is guaranteed. A non-boss or an un-special boss is untouched.
    from kernel.world.boss_specials import is_charging, maybe_begin_charge, unleash

    special_line, guaranteed = "", False
    if is_charging(npc):
        raw, special_line = unleash(npc, raw)
        guaranteed = True
    else:
        telegraph = maybe_begin_charge(npc)
        if telegraph:
            announce(session.location, telegraph, exclude=session.player_id)
            return telegraph  # the wind-up: no blow this beat, only the read
    # A wounded BOSS enrages (kernel.world.boss_phases): below its threshold its blows redouble, and
    # the room hears it announced once. A non-boss, or a boss above the line, is untouched.
    raw, phase_line = boss_phase(npc, raw)
    # A RAID boss scales its DIFFICULTY with the co-located cohort: the more heroes stand against
    # it, the harder its blows land (a raid should demand the trinity, not fall to a bigger zerg).
    # A solo cohort is x1 (backward-compatible); each extra mate adds RAID_DIFFICULTY_PER_MEMBER.
    if npc.get("raid"):
        from kernel.world.party import members_in_room

        present = len(members_in_room(session.player_id, session.location))
        cohort = min(RAID_COHORT_CAP, max(1, present))
        if cohort > 1:
            raw = int(raw * (1 + (cohort - 1) * RAID_DIFFICULTY_PER_MEMBER))
    # A weakened foe (a `weaken` ability) lands softer, and this blow spends one weaken charge.
    sapped = npc.get("weakened", 0)
    if sapped > 0:
        raw = max(1, raw // 2)
        npc["weakened"] = sapped - 1
        if npc["weakened"] <= 0:
            npc.pop("weakened", None)
    # Your DEF (from gear/perks/Order) turns the blow, but a landed hit always stings: floor at 1.
    power = max(1, raw - _stat_bonus(session, "DEF"))
    warded = session.statuses.get("barrier", 0) > 0
    if warded:  # a deployed barrier (Engineer) turns half the blow while it holds
        power = max(1, power // 2)
    # The one die: the foe may whiff, glance, or crit -- UNLESS this is a telegraphed unleash, which
    # was announced and connects by design (a guaranteed special never whiffs).
    vnote = ""
    if not guaranteed:
        power, vnote = _apply_variance(power)
    # A typed blow (the foe's attack_element) is scaled by the player's resistance to that element.
    power, healed, resist_note = _typed_blow(session, npc, power)
    session.resources["hp"] = session.resources["hp"].damage(power)
    if power > 0:  # a landed blow dents worn armour (economy: durability -> repair)
        _wear_gear(session, "body")
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
    sap = " (weakened)" if sapped > 0 else ""
    if power > 0:
        body = f"{name} {verb} for {power}.{sap}{ward}{resist_note}{vnote}"
    else:  # a miss, or an Immune/Absorb: the blow lands no damage, the note carries the outcome
        body = f"{name} {verb}.{resist_note}{vnote}"
    line = f"{body} (HP {hp.current}/{hp.maximum})"
    # A boss's venomous or stunning blow may lay an affliction on the player (afflictions.py), from
    # the NPC's `inflicts` spec -- but an UNLEASHED special's affliction is GUARANTEED (it was
    # telegraphed; it connects). Only a blow that landed damage can afflict.
    if power > 0:
        from kernel.world.afflictions import inflict, maybe_inflict

        spec = npc.get("inflicts")
        if guaranteed and spec:
            afflicted: str | None = inflict(session, spec)
        else:
            afflicted = maybe_inflict(session, spec)
        if afflicted:
            line = f"{line}\n{afflicted}"
    if phase_line:  # a fresh enrage announces before the blow it empowers
        line = f"{phase_line}\n{line}"
    if special_line:  # an unleashed special announces before its heavy blow
        line = f"{special_line}\n{line}"
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
    Driven by kernel.world.aggression on tick, not by a player's blow. Passive NPCs return ''."""
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


# The first kill of a boss each PERIOD pays this multiple of its coin drop as a bounty, then nothing
# extra until the period rolls. The foe stays farmable (after K1 it dies and respawns on its timer),
# but infinite farming no longer pays infinite reward -- the endgame's reason to return
# (kernel.world.lockouts). A raid is a weekly cadence and pays far more than a daily boss (a party's
# marquee objective, not a solo lap).
BOSS_BOUNTY_MULT = 5
RAID_BOUNTY_MULT = 20
RAID_COHORT_MIN = (
    2  # a raid's marquee weekly bounty pays only to a co-located cohort, not a solo lap
)
# Raid DIFFICULTY scales with the cohort too: a raid boss hits +20% per extra hero present, so a
# bigger band faces a bigger threat (not just a bigger reward). Solo (cohort 1) is x1, unchanged.
RAID_DIFFICULTY_PER_MEMBER = 0.20
RAID_COHORT_CAP = 8  # beyond this the scaling flattens, so a zerg cannot inflate it without bound


def _kill_bounty(session: Session, npc: Npc, nid: str) -> str:
    """A lockout-gated bonus on the period's first kill of a raid (weekly) or a boss (daily). It
    returns the bounty line (and credits the coins), or '' for a normal foe, or one already claimed
    this period. A raid outranks the plain boss cadence: it is checked first."""
    from kernel.world import lockouts

    if npc.get("raid"):
        key, period, mult, label = (
            f"raid:{nid}",
            lockouts.this_week_utc(),
            RAID_BOUNTY_MULT,
            "Weekly raid",
        )
    elif npc.get("tier") == "boss":
        key, period, mult, label = f"boss:{nid}", lockouts.today_utc(), BOSS_BOUNTY_MULT, "Daily"
    else:
        return ""
    if not lockouts.claim(session, key, period):
        # Already cleared this period: no repeat bounty, but ACKNOWLEDGE the clear so the endgame
        # reads as completed, not silently farmed. The base drop still stands (this rides on top).
        span = "this week" if npc.get("raid") else "today"
        return f"({sentence_case(npc['name'])} is already cleared {span}; felled for the drop.)"
    bonus = _coin_reward(npc) * mult
    cohort_note = ""
    if npc.get("raid"):
        # A raid rewards a COHORT: the marquee bounty scales with the party present for the kill, so
        # a full band earns more than a solo lap (the stated intent, now paid). members_in_room
        # includes the killer, so a solo raider scales x1 (unchanged); each present mate adds one.
        from kernel.world.party import members_in_room

        cohort = max(1, len(members_in_room(session.player_id, session.location)))
        bonus *= cohort
        if cohort >= RAID_COHORT_MIN:
            cohort_note = (
                f" (a cohort of {cohort} splits the raid, and the bounty scales with them)"
            )
    session.coins += bonus
    return (
        f"{label} bounty! The first {npc['name']} falls: you claim {purse(bonus)} extra."
        f"{cohort_note} (purse: {purse(session.coins)})"
    )


def land_hit(session: Session, npc: Npc, nid: str, dmg: int) -> tuple[bool, str]:
    """Apply `dmg` to `npc` and resolve the outcome; return (defeated, tail).

    Advances the combat clock, re-engages an aggressive foe, and on defeat reassembles the target,
    witnesses it, awards XP/JP/TP, spawns drops + a loot roll, and fires the quest hook -- returning
    that as `tail` (empty when the foe survives). The CALLER owns the actor's own line, the room
    strike broadcast, and any counter, so `attack` and an ability share this defeat/award core."""
    npc["hp_now"] -= dmg
    advance_clock(session)  # a landed strike is a combat action: cooldowns thaw, statuses age
    threat.add(nid, session.player_id, dmg)  # damage builds aggro: the foe remembers who hurt it
    if npc.get("aggressive"):
        session.aggro_beats[nid] = 0  # the player answered the foe: re-engage its leash from zero
    if npc["hp_now"] > 0:
        return (False, "")
    threat.clear(nid)  # a felled foe holds no grudge -- the aggro table resets
    # A mortal world foe DIES and respawns on a tier timer (it drops from the room until then); the
    # training dummy and anything a seed marks `reassembles` stands right back up. Statuses clear
    # either way. This is the keel-approved "a cleared room stays cleared for a while" behaviour.
    from kernel.world import climate, mortality

    mortality.fell(npc, climate.now())
    announce(
        session.location,
        f"{sentence_case(npc['name'])} {mortality.defeat_clause(npc)}.",
        exclude=session.player_id,
    )
    witness("defeat", npc["name"], "fell in combat")
    xp_award, jp_award, tp_award = _reward_amounts(session, npc)
    rewards = award_xp(session, xp_award)
    for extra in (award_jp(session, jp_award), award_tp(session, tp_award)):
        if extra:
            rewards = f"{rewards}\n{extra}"
    # Shared combat: a party-mate present for the kill shares its advancement (the reward half of
    # fighting as one). One call at the reward seam; the sharing logic lives in party_rewards.
    from kernel.world.party_rewards import share_kill

    shared = share_kill(
        session.player_id, session.location, npc["name"], xp_award, jp_award, tp_award
    )
    if shared:
        rewards = f"{rewards}\n{shared}"
    coins = _coin_reward(npc)
    session.coins += coins
    rewards = f"{rewards}\nYou find {purse(coins)}. (purse: {purse(session.coins)})"
    bounty = _kill_bounty(
        session, npc, nid
    )  # endgame: the period's-first bonus (daily boss / weekly raid)
    if bounty:
        rewards = f"{rewards}\n{bounty}"
    # guaranteed drops, then one weighted loot roll -- both spawn fresh instances on the floor
    haul = "\n".join(
        part for part in (_spawn_drops(session, npc), _roll_loot(session, npc)) if part
    )
    if haul:
        rewards = f"{rewards}\n{haul}"
    from kernel.world import (
        quest,  # lazy: combat is the low-level loop; the quest hook rides on top
    )

    quest_line = quest.on_event(session, "defeat", nid)  # a boss's fall may complete a story beat
    if quest_line:
        rewards = f"{rewards}\n{quest_line}"
    # A cull quest ('fell N of a kind HERE') advances on the foe's TYPE, scoped to the KILL's zone:
    # fire a cull event per keyword under this zone's key, so felling a grey-hound in Veridia counts
    # toward 'cull the canids in Veridia', never another region's board. Cheap: an unrouted key is a
    # single dict miss, and the mass wildlife kills flow through here.
    from kernel.world.cull import scope_key
    from kernel.world.zones import zone_of

    zone = zone_of(session.location)
    if zone:
        for kind in npc.get("keywords", []):
            cull_line = quest.on_event(session, "cull", scope_key(zone, kind))
            if cull_line:
                rewards = f"{rewards}\n{cull_line}"
    return (True, rewards)


def attack(session: Session, word: str) -> str:
    """One strike of the training loop."""
    if session.stats is None:
        return "You have no calling yet. Type JOBS before you pick a fight."
    from kernel.world.afflictions import is_dazed

    if is_dazed(session):
        return "You are dazed and cannot strike -- it will pass."
    try:
        nid = resolve_npc_target(word, session.location)  # "2-goblin" strikes the second of several
    except target_disambig.TargetError as exc:
        return f"There is no one like that here ({exc})."
    if nid is None:
        return "There is no one like that here."
    npc = NPCS[nid]
    if npc["hp"] <= 0:
        return f"{sentence_case(npc['name'])} is not something you can fight."
    dmg = strike_power(session)
    exposed = session.statuses.get("analyzed", 0) > 0
    if exposed:  # a Diagnostic Scan revealed the foe's weak point: +50% damage while it holds
        dmg += dmg // 2
    empowered = session.statuses.get("empowered", 0) > 0
    if empowered:  # a support's buff (the `buff` ability): +50% damage while it holds
        dmg += dmg // 2
    weak = " (weak point!)" if exposed else ""
    if empowered:
        weak += " (empowered!)"
    dmg, vnote = _apply_variance(dmg)  # the one die: a miss (0), a glance, a crit, or a normal hit
    if dmg > 0:
        announce(
            session.location,
            f"{display_name(session.player_id)} strikes {npc['name']} for {dmg}.",
            exclude=session.player_id,
        )
        struck = f"You strike {npc['name']} for {dmg}.{weak}{vnote}"
        # a landed strike dulls the blade (economy: durability -> repair); a whiff does not
        _wear_gear(session, "weapon")
    else:  # a miss: no damage and no wear, but still a spent beat -- the foe gets its counter
        announce(
            session.location,
            f"{display_name(session.player_id)} swings at {npc['name']} and misses.",
            exclude=session.player_id,
        )
        struck = f"You swing at {npc['name']} and miss."
    defeated, tail = land_hit(session, npc, nid, dmg)
    if not defeated:
        # An aggressive NPC's blow arrives on the world beat (kernel.world.aggression), never as a
        # counter, so it strikes exactly once per tick -- never both counter and open-strike.
        counter = "" if npc.get("aggressive") else _counter_attack(session, npc)
        return f"{struck} ({npc['hp_now']}/{npc['hp']}){counter}"
    from kernel.world import mortality

    return f"{struck} It {mortality.defeat_clause(npc)}.\n{tail}"


BURN_TICKS = 3  # how many world beats a `brand` burn lasts before it burns out


def apply_burn(npc: Npc, damage: int, ticks: int = BURN_TICKS) -> None:
    """Lay a burn damage-over-time on a foe (a `brand` ability). It saps `damage` HP each world beat
    for `ticks` beats. A fresh brand refreshes the burn rather than stacking."""
    npc["burn"] = {"damage": max(1, damage), "ticks": max(1, ticks)}


def apply_daze(npc: Npc, beats: int) -> None:
    """Daze a foe for `beats` world beats (a `daze` ability): it skips that many of its own beat
    strikes (crowd control, decremented by menace). A fresh daze refreshes, it does not stack."""
    npc["dazed"] = max(1, beats)


def apply_weaken(npc: Npc, blows: int) -> None:
    """Weaken a foe's next `blows` strikes (a `weaken` ability): each lands for half (floored 1) and
    decrements the counter in _resolve_npc_blow. A fresh weaken refreshes, it does not stack."""
    npc["weakened"] = max(1, blows)


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

    An EQUIPPABLE drop from a levelled foe runs through the affix factory (kernel.shelf.affixes): it
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
    # Shared combat, loot half: in a party, a drop is awarded to a co-located mate by round-robin
    # instead of dropping to the floor. Solo/unpartied loot is unchanged (falls to the ground).
    from kernel.world.party_loot import assign_drop

    awarded = assign_drop(session.player_id, session.location, iid)
    if awarded is not None:
        return awarded
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
