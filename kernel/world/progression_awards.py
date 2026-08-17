"""CARD: progression_awards -- grant XP/JP/TP and climb the curves (the leveling engine).

Split from combat (the damage loop) so the leveling engine stands on its own: any source of
reward -- a felled NPC, a finished quest, a future achievement -- calls the same three grants
without pulling in strike math. Each award is monotonic (it never DRAINS progress), consults the
progression curves as law, ascends resources on a level-up, and persists a named character.

`award_xp` climbs player levels (and refills/grows HP/MP via `_ascend_resources`); `award_jp`
climbs the ACTIVE job's level; `award_tp` fills the active job's milestone track. Depends only on
progression/jobs/resources/session -- no combat internals -- so it composes cleanly.

The one deliberate exception to "never drains" is `apply_xp_debt` (K5): a LETHAL death sets a hero
back by a fraction of the progress they have earned INTO their current level -- never below the
level's floor, so a death costs progress but NEVER a level. It is the only path that reduces XP.
"""

from dataclasses import replace

from kernel.world.events import announce
from kernel.world.jobs import JOBS
from kernel.world.progression import (
    STAT_POINTS_PER_LEVEL,
    get_next_job_level_threshold,
    get_next_level_threshold,
    hp_gain_per_level,
    mp_gain_per_level,
)
from kernel.world.resources import Resource
from kernel.world.session import Session, display_name


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
    amount = max(0, amount)  # an award never DRAINS progress, whatever a caller passes
    session.xp += amount
    lines = [f"You gain {amount} XP."]
    while True:
        threshold = get_next_level_threshold(session.level)
        if threshold is None or session.xp < threshold:
            break
        session.level += 1
        _ascend_resources(session)
        lines.append(
            f"*** LEVEL UP! You are now level {session.level}. "
            f"(+{STAT_POINTS_PER_LEVEL} points -- type ALLOCATE to spend them.) ***"
        )
        from kernel.world.characters import save_character  # noqa: PLC0415

        save_character(session)
        announce(
            session.location,
            f"{display_name(session.player_id)} has reached level {session.level}!",
            exclude=session.player_id,
        )
    return "\n".join(lines)


# K5: a lethal death costs this fraction of the XP earned INTO the current level (a tuning knob).
XP_DEBT_FRACTION = 0.10


def apply_xp_debt(session: Session, fraction: float = XP_DEBT_FRACTION) -> int:
    """Set a hero back by `fraction` of the XP they have earned INTO their CURRENT level, floored at
    the level's threshold so a death NEVER drops a level -- only progress toward the next one. The
    single deliberate drain (see the card); returns the XP lost (0 at the floor or fraction 0).
    Reversible by design: what a death costs, play re-earns."""
    fraction = min(1.0, max(0.0, fraction))
    floor = 0 if session.level <= 1 else (get_next_level_threshold(session.level - 1) or 0)
    progress = max(0, session.xp - floor)
    lost = int(progress * fraction)
    session.xp -= lost
    return lost


def award_jp(session: Session, amount: int) -> str:
    """Add JP to the ACTIVE job; climb every job-level threshold crossed. The curves are law.

    JP here is cumulative earned progress toward the job's level (it mirrors XP -> PLvl).
    Changing jobs never touches another job's record. A seat with no active job earns nothing.
    """
    job = session.job
    if not job or job not in session.job_progress:
        return ""
    amount = max(0, amount)  # an award never DRAINS progress
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
        from kernel.world.characters import save_character  # noqa: PLC0415

        save_character(session)
    return "\n".join(lines)


def award_tp(session: Session, amount: int) -> str:
    """Accrue TP to the ACTIVE job (toward its milestone perks). No leveling; TP just fills."""
    job = session.job
    if not job or job not in session.job_progress:
        return ""
    amount = max(0, amount)  # an award never DRAINS progress
    prog = session.job_progress[job]
    session.job_progress[job] = replace(prog, tp=prog.tp + amount)
    if session.named:
        from kernel.world.characters import save_character  # noqa: PLC0415

        save_character(session)
    return f"You gain {amount} TP ({JOBS[job]['name']})."
