"""CARD: combat -- the training loop: strike, defeat, XP, LEVEL UP.

Assembly card: npcs (targets) + stats (damage) + resources (growth)
+ progression (the salvaged mk1 curves decide when you level).
Damage is deterministic in v0: no dice yet, so every number in the
test twin is exact. The dummy reassembles on defeat -- it is a
training dummy; collapsing is its job.
"""

from dataclasses import replace

from parts.events import announce
from parts.jobs import JOBS
from parts.npcs import NPCS, trace_npc
from parts.progression import (
    get_next_job_level_threshold,
    get_next_level_threshold,
    hp_gain_per_level,
    mp_gain_per_level,
)
from parts.resources import Resource
from parts.session import Session, display_name

DAMAGE_BASE = 3  # damage dealt = DAMAGE_BASE + strength // 3


def strike_power(session: Session) -> int:
    assert session.stats is not None
    return DAMAGE_BASE + session.stats.get("strength").base // 3


def _ascend_resources(session: Session) -> None:
    """Level-up growth uses the mk1 formulas; resources refill in full."""
    assert session.stats is not None
    sta = session.stats.get("stamina").base
    mag = session.stats.get("magic").base
    new_hp_max = session.resources["hp"].maximum + hp_gain_per_level(sta)
    new_mp_max = session.resources["mp"].maximum + mp_gain_per_level(mag)
    session.resources["hp"] = Resource(name="hp", current=new_hp_max, maximum=new_hp_max)
    session.resources["mp"] = Resource(name="mp", current=new_mp_max, maximum=new_mp_max)


def award_xp(session: Session, amount: int) -> str:
    """Add XP; climb every threshold crossed. The curves are law."""
    session.xp += amount
    lines = [f"You gain {amount} XP."]
    while True:
        threshold = get_next_level_threshold(session.level)
        if threshold is None or session.xp < threshold:
            break
        session.level += 1
        _ascend_resources(session)
        lines.append(f"*** LEVEL UP! You are now level {session.level}. ***")
        from parts.characters import save_character

        save_character(session)
        announce(
            session.location,
            f"{display_name(session.player_id)} has reached level {session.level}!",
            exclude=session.player_id,
        )
    return "\n".join(lines)


def award_jp(session: Session, amount: int) -> str:
    """Add JP to the ACTIVE job; climb every job-level threshold crossed. The curves are law.

    JP here is cumulative earned progress toward the job's level (it mirrors XP -> PLvl).
    Changing jobs never touches another job's record. A seat with no active job earns nothing.
    """
    job = session.job
    if not job or job not in session.job_progress:
        return ""
    prog = session.job_progress[job]
    new_jp = prog.jp + amount
    new_level = prog.job_level
    lines = [f"You gain {amount} JP ({JOBS[job]['name']})."]
    while True:
        threshold = get_next_job_level_threshold(new_level)
        if threshold is None or new_jp < threshold:
            break
        new_level += 1
        lines.append(f"*** {JOBS[job]['name']} advances to job level {new_level}! ***")
    session.job_progress[job] = replace(prog, jp=new_jp, job_level=new_level)
    if session.named:
        from parts.characters import save_character

        save_character(session)
    return "\n".join(lines)


def award_tp(session: Session, amount: int) -> str:
    """Accrue TP to the ACTIVE job (toward its milestone perks). No leveling; TP just fills."""
    job = session.job
    if not job or job not in session.job_progress:
        return ""
    prog = session.job_progress[job]
    session.job_progress[job] = replace(prog, tp=prog.tp + amount)
    if session.named:
        from parts.characters import save_character

        save_character(session)
    return f"You gain {amount} TP ({JOBS[job]['name']})."


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
        return f"You strike {npc['name']} for {dmg}. ({npc['hp_now']}/{npc['hp']})"
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
    return f"{defeat}\n{rewards}"
