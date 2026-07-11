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
from parts.jobs import BASE_HP, BASE_MP, JOBS
from parts.progression import get_next_level_threshold
from parts.score_sheet import CharacterSheet, EquipmentLoadout

# Sheet attribute code -> engine stat name.
_ATTR_CODES = {
    "STR": "strength",
    "SPD": "speed",
    "MAG": "magic",
    "STA": "stamina",
    "WIS": "wisdom",
    "LUCK": "luck",
}


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
