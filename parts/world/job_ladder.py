# ruff: noqa: E501  (the 30 job-definition rows are inherently long data lines)
"""CARD: job_ladder -- the 30-job FFT-style progression backbone (tiers, roles, unlocks, schedule).

Stage 1 of the Job System campaign: the STRUCTURE every job hangs its abilities on, as validated
data. This is deliberately the backbone, not the 630 authored abilities (those are the later stages
that fill each of the 21 feature slots below). It answers, for the whole system:

  - which 30 jobs exist, in which of the three tiers (12 / 12 / 6);
  - each job's primary and secondary combat ROLES (from the role vocabulary);
  - each advanced job's UNLOCK requirements (prerequisite job levels), data-driven and acyclic;
  - the UNIVERSAL PROGRESSION schedule -- which feature type (active / passive / reaction / support /
    movement / signature) a job earns at each Job Level 1-30, identical for every job (21 features).

Kept as inspectable Python data (the job SYSTEM's shape, not player-editable seed content), so the
loader is these constants plus the validators below. Later stages author the named abilities that
occupy each (job, level, slot) and wire them into combat; this module is what those hang on and what
the unlock/progression tests gate.
"""

from __future__ import annotations

from typing import NamedTuple

# --- The universal progression schedule --------------------------------------------------------
# The prompt's fixed skeleton: at each listed Job Level a job earns the given feature type(s). Every
# job follows it, so all 30 jobs gain exactly 21 features: 1 core trait, 10 actives, 3 passives, 2
# reactions, 2 supports, 2 movements, 1 signature. "active_N" tracks which of the 10 actives this is.
UNIVERSAL_PROGRESSION: list[tuple[int, tuple[str, ...]]] = [
    (1, ("core_trait", "active_1")),
    (2, ("active_2",)),
    (4, ("active_3",)),
    (6, ("passive_1",)),
    (8, ("active_4",)),
    (10, ("reaction_1",)),
    (12, ("active_5",)),
    (15, ("support_1",)),
    (17, ("active_6",)),
    (20, ("movement_1",)),
    (21, ("active_7",)),
    (23, ("passive_2",)),
    (24, ("active_8",)),
    (26, ("reaction_2",)),
    (27, ("active_9",)),
    (28, ("support_2",)),
    (29, ("movement_2", "passive_3")),
    (30, ("active_10", "signature")),
]

MAX_JOB_LEVEL = 30

# The count of each feature type a completed job carries (derived from the schedule; pinned by test).
FEATURE_COUNTS = {
    "core_trait": 1,
    "active": 10,
    "passive": 3,
    "reaction": 2,
    "support": 2,
    "movement": 2,
    "signature": 1,
}
FEATURES_PER_JOB = 21  # 1 + 10 + 3 + 2 + 2 + 2 + 1

# The role vocabulary a job may claim (the prompt's role tags). Every job role must be one of these.
ROLES = {
    "Main Tank",
    "Off-Tank",
    "Mitigation Tank",
    "Evasion Tank",
    "Drain Tank",
    "Pet Tank",
    "Melee Burst DPS",
    "Melee Sustained DPS",
    "Ranged Physical DPS",
    "Magical Burst DPS",
    "Magical Sustained DPS",
    "Area DPS",
    "Damage-over-Time DPS",
    "Direct Healer",
    "Heal-over-Time Healer",
    "Barrier Healer",
    "Drain Healer",
    "Pet Healer",
    "Party Support",
    "Battlefield Controller",
    "Debuffer",
    "Summoner",
    "Construct Specialist",
    "Resource Support",
    "Tactical Specialist",
}


class Job(NamedTuple):
    id: str
    name: str
    tier: int  # 1, 2, or 3
    primary: tuple[str, ...]  # 1-2 primary roles
    secondary: tuple[str, ...]  # 0-2 secondary roles
    unlock: tuple[tuple[str, int], ...]  # prerequisite (job_id, job_level) pairs; empty for Tier I


# --- The 30 jobs -------------------------------------------------------------------------------
_JOBS: list[Job] = [
    # Tier I -- 12 foundational jobs, no prerequisites.
    Job(
        "guardian",
        "Guardian",
        1,
        ("Main Tank", "Mitigation Tank"),
        ("Party Support", "Battlefield Controller"),
        (),
    ),
    Job(
        "vanguard",
        "Vanguard",
        1,
        ("Off-Tank", "Melee Sustained DPS"),
        ("Battlefield Controller",),
        (),
    ),
    Job("rogue", "Rogue", 1, ("Melee Burst DPS", "Debuffer"), ("Tactical Specialist",), ()),
    Job(
        "ranger",
        "Ranger",
        1,
        ("Ranged Physical DPS", "Tactical Specialist"),
        ("Battlefield Controller",),
        (),
    ),
    Job("mage", "Mage", 1, ("Magical Burst DPS", "Area DPS"), ("Battlefield Controller",), ()),
    Job("cleric", "Cleric", 1, ("Direct Healer", "Barrier Healer"), ("Party Support",), ()),
    Job(
        "druid",
        "Druid",
        1,
        ("Heal-over-Time Healer", "Battlefield Controller"),
        ("Off-Tank", "Magical Sustained DPS"),
        (),
    ),
    Job(
        "bard", "Bard", 1, ("Party Support", "Resource Support"), ("Debuffer", "Direct Healer"), ()
    ),
    Job("monk", "Monk", 1, ("Melee Sustained DPS", "Evasion Tank"), ("Direct Healer",), ()),
    Job(
        "engineer",
        "Engineer",
        1,
        ("Construct Specialist", "Battlefield Controller"),
        ("Ranged Physical DPS", "Party Support"),
        (),
    ),
    Job(
        "beastmaster",
        "Beastmaster",
        1,
        ("Summoner", "Pet Tank"),
        ("Ranged Physical DPS", "Pet Healer"),
        (),
    ),
    Job(
        "alchemist",
        "Alchemist",
        1,
        ("Tactical Specialist", "Direct Healer"),
        ("Damage-over-Time DPS", "Battlefield Controller"),
        (),
    ),
    # Tier II -- 12 advanced jobs, each gated by Tier I job levels.
    Job(
        "duelist",
        "Duelist",
        2,
        ("Melee Burst DPS", "Evasion Tank"),
        ("Debuffer",),
        (("rogue", 15), ("vanguard", 10)),
    ),
    Job(
        "berserker",
        "Berserker",
        2,
        ("Melee Sustained DPS", "Drain Tank"),
        ("Area DPS",),
        (("vanguard", 15), ("monk", 10)),
    ),
    Job(
        "warlord",
        "Warlord",
        2,
        ("Party Support", "Off-Tank"),
        ("Battlefield Controller",),
        (("guardian", 15), ("bard", 10)),
    ),
    Job(
        "assassin",
        "Assassin",
        2,
        ("Melee Burst DPS", "Damage-over-Time DPS"),
        ("Debuffer",),
        (("rogue", 15), ("ranger", 10)),
    ),
    Job(
        "gunslinger",
        "Gunslinger",
        2,
        ("Ranged Physical DPS", "Melee Burst DPS"),
        ("Tactical Specialist",),
        (("ranger", 15), ("engineer", 10)),
    ),
    Job(
        "arcanist",
        "Arcanist",
        2,
        ("Magical Sustained DPS", "Resource Support"),
        ("Battlefield Controller",),
        (("mage", 15), ("alchemist", 10)),
    ),
    Job(
        "elementalist",
        "Elementalist",
        2,
        ("Magical Burst DPS", "Area DPS"),
        ("Battlefield Controller",),
        (("mage", 15), ("druid", 10)),
    ),
    Job(
        "spellblade",
        "Spellblade",
        2,
        ("Melee Burst DPS", "Magical Sustained DPS"),
        ("Off-Tank",),
        (("mage", 12), ("vanguard", 12)),
    ),
    Job(
        "oracle",
        "Oracle",
        2,
        ("Barrier Healer", "Party Support"),
        ("Tactical Specialist",),
        (("cleric", 15), ("bard", 10)),
    ),
    Job(
        "templar",
        "Templar",
        2,
        ("Main Tank", "Barrier Healer"),
        ("Party Support",),
        (("guardian", 12), ("cleric", 12)),
    ),
    Job(
        "summoner",
        "Summoner",
        2,
        ("Summoner", "Magical Sustained DPS"),
        ("Pet Tank", "Pet Healer"),
        (("mage", 12), ("beastmaster", 12)),
    ),
    Job(
        "runesmith",
        "Runesmith",
        2,
        ("Party Support", "Construct Specialist"),
        ("Barrier Healer", "Magical Sustained DPS"),
        (("engineer", 12), ("cleric", 10), ("mage", 10)),
    ),
    # Tier III -- 6 master jobs, deep multi-discipline prerequisites.
    Job(
        "shadowdancer",
        "Shadowdancer",
        3,
        ("Evasion Tank", "Melee Burst DPS"),
        ("Battlefield Controller",),
        (("assassin", 20), ("duelist", 15), ("bard", 10)),
    ),
    Job(
        "chronomancer",
        "Chronomancer",
        3,
        ("Battlefield Controller", "Party Support"),
        ("Magical Burst DPS", "Tactical Specialist"),
        (("arcanist", 20), ("oracle", 15), ("mage", 20)),
    ),
    Job(
        "necromancer",
        "Necromancer",
        3,
        ("Summoner", "Damage-over-Time DPS"),
        ("Drain Healer", "Debuffer"),
        (("summoner", 20), ("cleric", 15), ("arcanist", 10)),
    ),
    Job(
        "blood_mage",
        "Blood Mage",
        3,
        ("Drain Healer", "Magical Burst DPS"),
        ("Drain Tank",),
        (("alchemist", 20), ("berserker", 15), ("cleric", 10)),
    ),
    Job(
        "warlock",
        "Warlock",
        3,
        ("Damage-over-Time DPS", "Debuffer"),
        ("Summoner", "Resource Support"),
        (("summoner", 15), ("arcanist", 15), ("alchemist", 10)),
    ),
    Job(
        "hexblade",
        "Hexblade",
        3,
        ("Melee Burst DPS", "Debuffer"),
        ("Drain Tank", "Magical Sustained DPS"),
        (("spellblade", 20), ("warlock", 15), ("duelist", 10)),
    ),
]

JOBS: dict[str, Job] = {j.id: j for j in _JOBS}


def tier(n: int) -> list[Job]:
    """The jobs in a given tier (1, 2, or 3)."""
    return [j for j in _JOBS if j.tier == n]


def is_unlocked(job_id: str, job_levels: dict[str, int]) -> bool:
    """Whether a character with the given per-job levels meets a job's unlock requirements. Tier I
    jobs are always available; advanced jobs need every prerequisite job at or above its level."""
    job = JOBS[job_id]
    return all(job_levels.get(req_id, 0) >= req_lvl for req_id, req_lvl in job.unlock)


def missing_requirements(job_id: str, job_levels: dict[str, int]) -> list[tuple[str, int]]:
    """The unmet (job_id, level) prerequisites for a job, for a clear player-facing progress display."""
    job = JOBS[job_id]
    return [(rid, rl) for rid, rl in job.unlock if job_levels.get(rid, 0) < rl]


def feature_slots() -> list[tuple[int, str]]:
    """Every (job_level, feature_slot) a job earns across levels 1-30, in order -- the 21 features."""
    return [(lvl, slot) for lvl, slots in UNIVERSAL_PROGRESSION for slot in slots]


def _assert_acyclic() -> None:
    """DFS the unlock graph; raise if any job transitively requires itself (an impossible unlock)."""
    from parts.world.seed import SeedError

    WHITE, GREY, BLACK = 0, 1, 2
    colour = dict.fromkeys(JOBS, WHITE)

    def visit(node: str, path: list[str]) -> None:
        colour[node] = GREY
        for req_id, _lvl in JOBS[node].unlock:
            if colour[req_id] == GREY:
                cycle = " -> ".join([*path, node, req_id])
                raise SeedError(f"job ladder: circular unlock prerequisite: {cycle}")
            if colour[req_id] == WHITE:
                visit(req_id, [*path, node])
        colour[node] = BLACK

    for job_id in JOBS:
        if colour[job_id] == WHITE:
            visit(job_id, [])


def validate() -> None:
    """Fail loud if the ladder is malformed: tier counts, role vocabulary, unlock prerequisites
    resolving to real jobs at sane levels, no circular prerequisites, and a 21-slot schedule."""
    from parts.world.seed import SeedError

    if [len(tier(n)) for n in (1, 2, 3)] != [12, 12, 6]:
        raise SeedError("job ladder: tiers must hold 12 / 12 / 6 jobs.")
    if len(JOBS) != 30:
        raise SeedError(f"job ladder: expected 30 jobs, got {len(JOBS)}.")
    for job in _JOBS:
        for role in (*job.primary, *job.secondary):
            if role not in ROLES:
                raise SeedError(f"job {job.id!r}: unknown role {role!r}.")
        if not job.primary:
            raise SeedError(f"job {job.id!r}: must declare at least one primary role.")
        for req_id, req_lvl in job.unlock:
            if req_id not in JOBS:
                raise SeedError(f"job {job.id!r}: unlock names unknown job {req_id!r}.")
            if req_id == job.id:
                raise SeedError(f"job {job.id!r}: cannot require itself.")
            if not 1 <= req_lvl <= MAX_JOB_LEVEL:
                raise SeedError(f"job {job.id!r}: unlock level {req_lvl} out of 1-{MAX_JOB_LEVEL}.")
    # The unlock graph must be acyclic (a job can never, transitively, require itself). Same-tier
    # prerequisites are allowed (Hexblade needs Warlock, both Tier III); only cycles are forbidden.
    _assert_acyclic()
    slots = feature_slots()
    if len(slots) != FEATURES_PER_JOB:
        raise SeedError(f"job ladder: expected {FEATURES_PER_JOB} feature slots, got {len(slots)}.")


validate()  # the ladder is validated at import -- a malformed table never reaches the game
