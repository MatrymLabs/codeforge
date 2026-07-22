"""CARD: jobs -- callings born from seed, characters born from callings.

The chargen assembly point: seed data (jobs.yaml) meets the salvaged
mk1 kernel. Picking a job builds a validated StatBlock, births HP/MP
resources from the job's stats, opens a job_progress record, and stamps
the session. The score sheet itself lives in score_sheet/character_view --
this card only assembles the character; the sheet is its projection.
"""

from parts.job_progress import JobProgress
from parts.resources import Resource
from parts.seed import SEED_DIR, load_jobs
from parts.session import Session
from parts.shelf.stats import Stat, StatBlock

JOBS = load_jobs(SEED_DIR / "jobs.yaml")

BASE_HP = 20  # starting HP is BASE_HP + stamina; leveling uses the progression card
BASE_MP = 5  # starting MP is BASE_MP + magic


def calling_index() -> str:
    """The list a new soul reads before choosing."""
    lines = ["Callings:"]
    # The world is data: a seed may name a calling of any length ('forgewright',
    # 'emberwright' are 11), so size the column to the widest label, never a fixed 10.
    width = max((len(label) for label in JOBS), default=0)
    for label, job in JOBS.items():
        lines.append(f"  {label:<{width}} {job['name']} -- {job['description']}")
    lines.append("Choose with: job <calling>")
    return "\n".join(lines)


def bind_calling(session: Session, word: str) -> str:
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
    cells = job["power_cells"]  # a custom resource pool, if the job declares one (0 = none)
    if cells > 0:
        session.resources["power"] = Resource(name="power", current=cells, maximum=cells)
    # First time in this job? Open a progress record at level 1. A prior record is preserved.
    session.job_progress.setdefault(label, JobProgress(job_id=label))
    return f"You take up the way of the {job['name']}. Type SCORE to see your sheet."


def set_secondary(session: Session, word: str) -> str:
    """Equip a secondary job: it lends its ability kit, and keeps its own level/JP record."""
    label = word.strip().lower()
    if not session.job:
        return "Take up a primary calling first. Type JOBS."
    if label not in JOBS:
        return f"There is no calling named '{word}'. Type JOBS to see the paths."
    if label == session.job:
        return "That is already your primary calling."
    session.secondary_job = label
    session.job_progress.setdefault(label, JobProgress(job_id=label))
    return f"You equip the {JOBS[label]['name']} as your secondary. Its kit is yours to borrow."
