"""CARD: jobs -- callings born from seed, characters born from callings.

The chargen assembly point: seed data (jobs.yaml) meets the salvaged
mk1 kernel. Picking a job builds a validated StatBlock, births HP/MP
resources from the job's stats, and stamps the session. The score
command renders the sheet -- projection, never authority.
"""

from parts.progression import get_next_level_threshold
from parts.resources import Resource
from parts.seed import SEED_DIR, load_jobs
from parts.session import Session, display_name
from parts.stats import Stat, StatBlock

JOBS = load_jobs(SEED_DIR / "jobs.yaml")

BASE_HP = 20  # starting HP is BASE_HP + stamina; leveling uses the progression card
BASE_MP = 5  # starting MP is BASE_MP + magic


def jobs_text() -> str:
    """The list a new soul reads before choosing."""
    lines = ["Callings of The First Forge:"]
    for label, job in JOBS.items():
        lines.append(f"  {label:<10} {job['name']} -- {job['description']}")
    lines.append("Choose with: job <calling>")
    return "\n".join(lines)


def assign_job(session: Session, word: str) -> str:
    """Stamp a calling onto a session: stats and resources are born here."""
    label = word.strip().lower()
    if label not in JOBS:
        return f"There is no calling named '{word}'. Type JOBS to see the paths."
    job = JOBS[label]
    session.job = label
    session.stats = StatBlock(
        stats=tuple(Stat(name=n, base=v) for n, v in sorted(job["stats"].items()))
    )
    max_hp = BASE_HP + job["stats"]["stamina"]
    max_mp = BASE_MP + job["stats"]["magic"]
    session.resources = {
        "hp": Resource(name="hp", current=max_hp, maximum=max_hp),
        "mp": Resource(name="mp", current=max_mp, maximum=max_mp),
    }
    return f"You take up the way of the {job['name']}. Type SCORE to see your sheet."


def score_text(session: Session) -> str:
    """The classic character sheet. Pure projection of session state."""
    if not session.job or session.stats is None:
        return "You have no calling yet. Type JOBS to see the paths."
    job = JOBS[session.job]
    hp, mp = session.resources["hp"], session.resources["mp"]
    threshold = get_next_level_threshold(session.level)
    xp_line = f"XP {session.xp} / {threshold}" if threshold else "XP at cap"
    stat_line = "   ".join(f"{s.name} {s.base}" for s in session.stats.stats)
    return "\n".join(
        [
            f"== {display_name(session.player_id)}, the {job['name']} ==",
            f"Level {session.level}   {xp_line}",
            f"HP {hp.current}/{hp.maximum}   MP {mp.current}/{mp.maximum}",
            stat_line,
        ]
    )
