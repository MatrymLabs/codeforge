"""CARD: combat -- the training loop: strike, defeat, hand off to the leveling engine.

Assembly card: npcs (targets) + stats (damage). Damage is deterministic in v0: no dice
yet, so every number in the test twin is exact. The dummy reassembles on defeat -- it is a
training dummy; collapsing is its job. A landed strike advances the combat clock
(`combat_clock`), so cooldowns thaw and statuses age as rounds pass. When a foe falls,
combat hands the reward to the leveling engine (`progression_awards`) rather than climbing
the curves itself: damage, timing, and progression are separate responsibilities.

An NPC that carries a seed `atk` stat strikes back when it survives a
blow (the training dummy carries none, so it stays passive). If a
counter-strike would fell the player, a training-ground failsafe
restores them in place -- a fight never leaves anyone in a broken state.
"""

from parts.combat_clock import advance as advance_clock
from parts.engineer import emergency_repair
from parts.events import announce, announce_frame
from parts.frames import StrikeFrame
from parts.npcs import NPCS, trace_npc
from parts.progression_awards import award_jp, award_tp, award_xp
from parts.seed import Npc
from parts.session import Session, display_name

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
    name = npc["name"].capitalize()
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
    Driven by parts.aggression on the tick, not by a player's blow. Passive NPCs return ''."""
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
        return f"{npc['name'].capitalize()} is not something you can fight."
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
        # An aggressive NPC's blow arrives on the world beat (parts.aggression), never as a
        # counter, so it strikes exactly once per tick -- never both counter and open-strike.
        counter = "" if npc.get("aggressive") else _counter_attack(session, npc)
        return f"{hit}{counter}"
    npc["hp_now"] = npc["hp"]  # the dummy reassembles at full health
    announce(
        session.location,
        f"{npc['name'].capitalize()} collapses -- then reassembles itself.",
        exclude=session.player_id,
    )
    defeat = f"You strike {npc['name']} for {dmg}. It collapses -- then reassembles itself."
    rewards = award_xp(session, npc["xp"])
    for extra in (award_jp(session, npc["xp"]), award_tp(session, npc["xp"])):
        if extra:
            rewards = f"{rewards}\n{extra}"
    result = f"{defeat}\n{rewards}"
    from parts import quest  # lazy: combat is the low-level loop; the quest hook rides on top

    quest_line = quest.on_event(session, "defeat", nid)  # a boss's fall may complete a story beat
    return f"{result}\n{quest_line}" if quest_line else result
