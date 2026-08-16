"""CARD: jobs -- callings born from seed, characters born from callings.

The chargen assembly point: seed data (jobs.yaml) meets the salvaged
mk1 kernel. Picking a job builds a validated StatBlock, births HP/MP
resources from the job's stats, opens a job_progress record, and stamps
the session. The score sheet itself lives in score_sheet/character_view --
this card only assembles the character; the sheet is its projection.
"""

from kernel.shelf.stats import Stat, StatBlock
from kernel.world.callings import gate_calling
from kernel.world.job_progress import JobProgress
from kernel.world.resources import Resource
from kernel.world.seed import BLUEPRINT_DIR, load_jobs
from kernel.world.session import Session

JOBS = load_jobs(BLUEPRINT_DIR / "jobs.yaml")

BASE_HP = 20  # starting HP is BASE_HP + stamina; leveling uses the progression card
BASE_MP = 5  # starting MP is BASE_MP + magic


def calling_index(held: dict | None = None) -> str:
    """The list a new soul reads before choosing.

    Given a character's standing, a locked calling still LISTS, marked with what it asks for. A
    road you cannot see is not a goal, and the player is owed the road as much as the gate.
    """
    lines = ["Callings:"]
    # The world is data: a seed may name a calling of any length ('forgewright',
    # 'emberwright' are 11), so size the column to the widest label, never a fixed 10.
    width = max((len(label) for label in JOBS), default=0)
    names = {lbl: j["name"] for lbl, j in JOBS.items()}
    for label, job in JOBS.items():
        line = f"  {label:<{width}} {job['name']} -- {job['description']}"
        verdict = gate_calling(label, job, held or {})
        if not verdict.open:
            asks = ", ".join(need.phrase(names.get(need.calling)) for need in verdict.unmet)
            line += f"  [LOCKED: needs {asks}]"
        lines.append(line)
    lines.append("Choose with: job <calling>")
    return "\n".join(lines)


def character_creation_menu() -> str:
    """Render the first-time character menu from the active seed's calling pack."""
    lines = [
        "=== CHARACTER CREATION ===",
        "Choose your calling. This shapes your starting stats and abilities.",
        "",
    ]
    width = max((len(label) for label in JOBS), default=0)
    for label, job in JOBS.items():
        lines.append(f"  {label:<{width}}  {job['name']} -- {job['description']}")
    lines.extend(("", "Enter a calling name to continue (for example: vanguard)."))
    return "\n".join(lines)


def calling_label(word: str) -> str | None:
    """Return the canonical calling label for a creation-menu answer, or None if unknown."""
    label = word.strip().lower()
    return label if label in JOBS else None


def build_stats(job_label: str, allocated: dict[str, int]) -> StatBlock:
    """A job's StatBlock with the character's ALLOCATED attribute points folded onto the base. The
    allocation is character-level, so it applies whatever job is worn; an empty allocation gives the
    job's plain base stats (chargen). The one place stats are built, so bind and restore agree."""
    base = JOBS[job_label]["stats"]
    return StatBlock(
        stats=tuple(Stat(name=n, base=v + allocated.get(n, 0)) for n, v in sorted(base.items()))
    )


def bind_calling(session: Session, word: str) -> str:
    """Stamp a calling onto a session: stats and resources are born here."""
    label = word.strip().lower()
    if label not in JOBS:
        return f"There is no calling named '{word}'. Type JOBS to see the paths."
    job = JOBS[label]
    # Authority before capability: an advanced calling is refused before any state is touched,
    # so a locked path cannot half-bind and leave a character wearing stats it never earned.
    verdict = gate_calling(label, job, session.job_progress)
    if not verdict.open:
        return verdict.reason({lbl: j["name"] for lbl, j in JOBS.items()})
    session.job = label
    session.stats = build_stats(label, session.allocated)
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
    verdict = gate_calling(label, JOBS[label], session.job_progress)
    if not verdict.open:
        return verdict.reason({lbl: j["name"] for lbl, j in JOBS.items()})
    session.secondary_job = label
    session.job_progress.setdefault(label, JobProgress(job_id=label))
    return f"You equip the {JOBS[label]['name']} as your secondary. Its kit is yours to borrow."
