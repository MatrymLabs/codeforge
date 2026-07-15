"""CARD: combat -- the training loop: strike, defeat, hand off to the leveling engine.

Assembly card: npcs (targets) + stats (damage). Damage is deterministic in v0: no dice
yet, so every number in the test twin is exact. The dummy reassembles on defeat -- it is a
training dummy; collapsing is its job. When a foe falls, combat hands the reward to the
leveling engine (`progression_awards`) rather than climbing the curves itself: damage and
progression are separate responsibilities.

An NPC that carries a seed `atk` stat strikes back when it survives a
blow (the training dummy carries none, so it stays passive). If a
counter-strike would fell the player, a training-ground failsafe
restores them in place -- a fight never leaves anyone in a broken state.
"""

from parts.events import announce
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


def _counter_attack(session: Session, npc: Npc) -> str:
    """A surviving NPC with an atk stat strikes back. Passive NPCs return ''; text is projection."""
    power = npc_strike_power(npc)
    if power <= 0:
        return ""  # the training dummy and every peaceful NPC: no counter
    session.resources["hp"] = session.resources["hp"].damage(power)
    name = npc["name"].capitalize()
    announce(
        session.location,
        f"{name} strikes back at {display_name(session.player_id)} for {power}.",
        exclude=session.player_id,
    )
    hp = session.resources["hp"]
    line = f"\n{name} strikes back for {power}. (HP {hp.current}/{hp.maximum})"
    if hp.is_depleted:
        return f"{line}\n{_fall_and_recover(session, npc)}"
    return line


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
    announce(
        session.location,
        f"{display_name(session.player_id)} strikes {npc['name']} for {dmg}.",
        exclude=session.player_id,
    )
    if npc["hp_now"] > 0:
        hit = f"You strike {npc['name']} for {dmg}. ({npc['hp_now']}/{npc['hp']})"
        return f"{hit}{_counter_attack(session, npc)}"
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
