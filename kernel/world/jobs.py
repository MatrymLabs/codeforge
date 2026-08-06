"""CARD: jobs -- callings born from seed, characters born from callings.

The chargen assembly point: seed data (jobs.yaml) meets the salvaged
mk1 kernel. Picking a job builds a validated StatBlock, births HP/MP
resources from the job's stats, opens a job_progress record, and stamps
the session. The score sheet itself lives in score_sheet/character_view --
this card only assembles the character; the sheet is its projection.
"""

from kernel.shelf.stats import Stat, StatBlock
from kernel.world.job_progress import JobProgress
from kernel.world.resources import Resource
from kernel.world.seed import SEED_DIR, SEED_NAME, load_jobs
from kernel.world.session import Session

JOBS = load_jobs(SEED_DIR / "jobs.yaml")

# Aethryn's first three callings are the authored starting layer. The rest of the current roster is
# real content, but it becomes a progression choice rather than a character-creation checklist.
STARTING_CALLINGS = ("vanguard", "pathfinder", "emberwright")

# The unlock graph is intentionally data-shaped and readable at the command boundary. Job levels
# are the teaching gate; every edge has a meaningful relationship in the job-family design. Direct
# First Forge compatibility keeps its historic free-pick behavior because its fixture roster is not
# Aethryn's progression graph.
JOB_REQUIREMENTS: dict[str, tuple[tuple[str, int], ...]] = {
    "duelist": (("vanguard", 3), ("pathfinder", 2)),
    "ranger": (("pathfinder", 3),),
    "arcanist": (("emberwright", 3),),
    "cleric": (("emberwright", 3),),
    "engineer": (("emberwright", 3),),
    "druid": (("pathfinder", 3),),
    "sentinel": (("vanguard", 5),),
    "scout": (("ranger", 3),),
    "elementalist": (("arcanist", 5),),
    "oracle": (("cleric", 3),),
    "artificer": (("emberwright", 5),),
    "beastmaster": (("pathfinder", 5),),
    "reaver": (("vanguard", 5), ("duelist", 3)),
    "shadowblade": (("duelist", 5),),
    "chronomancer": (("arcanist", 5), ("pathfinder", 3)),
    "templar": (("cleric", 5),),
    "gunsmith": (("ranger", 5),),
    "stormcaller": (("druid", 5),),
    "berserker": (("duelist", 5),),
    "saboteur": (("scout", 5),),
    "summoner": (("arcanist", 5), ("emberwright", 3)),
    "warden": (("sentinel", 5),),
    "mechanist": (("engineer", 5),),
    "geomancer": (("druid", 5),),
    "trickster": (("scout", 5),),
    "runesmith": (("emberwright", 5),),
    "hierophant": (("cleric", 8), ("oracle", 6), ("warden", 5)),
}

BASE_HP = 20  # starting HP is BASE_HP + stamina; leveling uses the progression card
BASE_MP = 5  # starting MP is BASE_MP + magic


def unlock_status(session: Session, label: str) -> tuple[bool, list[str]]:
    """Return whether ``label`` is available and the human-readable missing requirements."""
    if SEED_NAME != "aethryn" or label in STARTING_CALLINGS:
        return True, []
    requirements = JOB_REQUIREMENTS.get(label, ())
    missing = []
    for prerequisite, needed in requirements:
        progress = session.job_progress.get(prerequisite)
        current = progress.job_level if progress is not None else 0
        if current < needed:
            missing.append(f"{prerequisite} Lv {current}/{needed}")
    # A roster entry without a declared edge is visible but unavailable until the graph is completed
    # by content review; this prevents silently granting an unreviewed path.
    if label not in STARTING_CALLINGS and label not in JOB_REQUIREMENTS:
        missing.append("unlock path not yet filed")
    return not missing, missing


def calling_index(session: Session | None = None) -> str:
    """The list a new soul reads before choosing."""
    lines = ["Callings:"]
    # The world is data: a seed may name a calling of any length ('forgewright',
    # 'emberwright' are 11), so size the column to the widest label, never a fixed 10.
    width = max((len(label) for label in JOBS), default=0)
    for label, job in JOBS.items():
        if session is not None and SEED_NAME == "aethryn":
            available, missing = unlock_status(session, label)
            state = "AVAILABLE" if available else f"LOCKED ({'; '.join(missing)})"
            lines.append(f"  {label:<{width}} [{state}] {job['name']} -- {job['description']}")
        else:
            lines.append(f"  {label:<{width}} {job['name']} -- {job['description']}")
    lines.append("Choose with: job <calling>")
    return "\n".join(lines)


def character_creation_menu() -> str:
    """Render the first-time character menu from the active seed's calling pack."""
    lines = [
        "=== CHARACTER CREATION ===",
        "Choose your calling. This shapes your starting stats and abilities.",
        "",
    ]
    choices = [label for label in STARTING_CALLINGS if label in JOBS]
    width = max((len(label) for label in choices), default=0)
    for label in choices:
        job = JOBS[label]
        lines.append(f"  {label:<{width}}  {job['name']} -- {job['description']}")
    lines.extend(("", "Enter a calling name to continue (for example: vanguard)."))
    return "\n".join(lines)


def calling_label(word: str) -> str | None:
    """Return the canonical calling label for a creation-menu answer, or None if unknown."""
    label = word.strip().lower()
    return label if label in STARTING_CALLINGS and label in JOBS else None


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
    available, missing = unlock_status(session, label)
    if not available:
        return f"{JOBS[label]['name']} is locked. Requirements: {'; '.join(missing)}."
    if label == session.job:
        return "That is already your primary calling."
    session.secondary_job = label
    session.job_progress.setdefault(label, JobProgress(job_id=label))
    return f"You equip the {JOBS[label]['name']} as your secondary. Its kit is yours to borrow."
