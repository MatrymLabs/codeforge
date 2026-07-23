"""CARD: character_view -- build a score-sheet view model from a live job definition.

This is the seam ADR-0005 promised: the renderer stays engine-free (it only reads a
`CharacterSheet`), and the engine-coupled construction lives here. Given a loaded job and a
character's progression, `build_job_sheet` assembles the view model -- attributes from the
job's stat block, resources from the calling's HP/MP rule, derived stats from the prototype
calculator, and the ability loadout from the job data.

What is not modeled yet renders honestly: no equipment (bare slots), unknown resistances
("?"), no secondary job ("Unassigned"). Those await their own batches; the sheet does not
pretend they exist.
"""

from __future__ import annotations

from parts.derived import derived_stats
from parts.equipment import apply_equipment, apply_stat_modifiers, equipped_loadout
from parts.jobs import BASE_HP, BASE_MP, JOBS
from parts.progression import get_next_level_threshold
from parts.score_sheet_model import (
    RESIST_ORDER,
    CharacterSheet,
    EquipmentLoadout,
    JobLine,
    JobTP,
)
from parts.seed import Job
from parts.session import Session, display_name
from parts.shelf.stats import StatModifier

# Sheet attribute code -> engine stat name.
_ATTR_CODES = {
    "STR": "strength",
    "SPD": "speed",
    "MAG": "magic",
    "STA": "stamina",
    "WIS": "wisdom",
    "LUCK": "luck",
}

TP_MILESTONE = 500  # prototype: TP required per milestone; each milestone unlocks the next perk


def perks_unlocked(job: Job, tp: int) -> list[dict]:
    """The milestone perks a job has earned at this TP: one per full milestone, in order."""
    count = min(tp // TP_MILESTONE, len(job["milestone_perks"]))
    return list(job["milestone_perks"][:count])


def _perk_modifiers(job: Job, tp: int) -> dict[str, list[StatModifier]]:
    """Unlocked perks as modifiers grouped by the stat they raise (fed through the stack)."""
    mods: dict[str, list[StatModifier]] = {}
    for perk in perks_unlocked(job, tp):
        mods.setdefault(perk["target"], []).append(
            StatModifier(source=perk["name"], flat=perk["amount"])
        )
    return mods


def build_job_sheet(
    job_label: str,
    display_name: str,
    player_level: int = 1,
    current_xp: int = 0,
    job_level: int = 1,
    jp: int = 0,
    race: str = "Human",
) -> CharacterSheet:
    """Assemble a CharacterSheet for a character of the given job at the given progression.

    Raises KeyError for an unknown job label -- a caller asking for a job that was never
    seeded is a bug, not a renderable state.
    """
    if job_label not in JOBS:
        raise KeyError(f"no job named {job_label!r}; seeded jobs: {sorted(JOBS)}")
    job = JOBS[job_label]
    stats = job["stats"]
    hp_max = BASE_HP + stats["stamina"]
    mp_max = BASE_MP + stats["magic"]

    return CharacterSheet(
        display_name=display_name,
        player_level=player_level,
        current_xp=current_xp,
        next_level_xp=get_next_level_threshold(player_level),
        hp=(hp_max, hp_max),
        mp=(mp_max, mp_max),
        jp=jp,
        race=race,
        primary_job=job["name"],
        primary_job_level=job_level,
        counter=job["counter"],
        movement=job["movement"],
        inherent=job["inherent"],
        signature=job["signature"],
        secondary_job=None,
        attributes={code: stats.get(name, 0) for code, name in _ATTR_CODES.items()},
        derived=derived_stats(stats, player_level),
        tp_rows=(),
        equipment=EquipmentLoadout(),
        resistances={},
    )


def sheet_from_session(session: Session) -> CharacterSheet | None:
    """Build the score sheet from a LIVE character. None when they have no calling yet.

    Reads real state: attributes from the stat block, resources from the pools, per-job level
    and TP from the persisted job_progress record. What is not modeled yet renders honestly
    (bare equipment, unknown resistances, no secondary job)."""
    if not session.job or session.stats is None:
        return None
    job = JOBS[session.job]
    attrs = {name: session.stats.get(name).base for name in _ATTR_CODES.values()}
    hp, mp = session.resources["hp"], session.resources["mp"]
    power = session.resources.get("power")
    progress = session.job_progress.get(session.job)
    job_level = progress.job_level if progress else 1
    jp = progress.jp if progress else 0
    tp_rows = (JobTP(job["name"], progress.tp, TP_MILESTONE),) if progress else ()
    secondary = None
    if session.secondary_job and session.secondary_job in JOBS:
        sec = session.job_progress.get(session.secondary_job)
        sec_level = sec.job_level if sec else 1
        secondary = f"{JOBS[session.secondary_job]['name']} (Lv {sec_level})"
    return CharacterSheet(
        display_name=display_name(session.player_id),
        player_level=session.level,
        current_xp=session.xp,
        next_level_xp=get_next_level_threshold(session.level),
        hp=(hp.current, hp.maximum),
        mp=(mp.current, mp.maximum),
        power=(power.current, power.maximum) if power is not None else None,
        jp=jp,
        race="Human",
        primary_job=job["name"],
        primary_job_level=job_level,
        counter=job["counter"],
        movement=job["movement"],
        inherent=job["inherent"],
        signature=job["signature"],
        secondary_job=secondary,
        attributes={code: attrs[name] for code, name in _ATTR_CODES.items()},
        # Base formulas, then equipped gear, then unlocked job perks -- all through the stack.
        derived=apply_stat_modifiers(
            apply_equipment(derived_stats(attrs, session.level), session),
            _perk_modifiers(job, progress.tp if progress else 0),
        ),
        tp_rows=tp_rows,
        equipment=equipped_loadout(session),
        # A character knows their own resistances: declared levels shown, the rest Normal.
        resistances={code: job["resistances"].get(code, "Normal") for code in RESIST_ORDER},
        jobs=tuple(
            JobLine(JOBS[jid]["name"], p.job_level, p.jp, p.tp)
            for jid, p in sorted(session.job_progress.items())
        ),
    )
