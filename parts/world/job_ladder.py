"""CARD: job_ladder -- the playable job roster and each calling's ability kit (the one job system).

The game has ONE job system: the playable CALLINGS a character binds with `job <calling>`, each
armed with a moveset. This module is the authoritative view of that roster for the ACTIVE seed:
each job is a real calling (jobs.yaml) carrying its real kit (abilities.yaml), so "pick a class and
fight with its kit" always holds. Jobs are freely pickable (no unlock gating); the shared job cap is
`MAX_JOB_LEVEL` (the JP curve tops out there, pinned by progression's checkpoint test).

Reconciled (finish-aethryn): an earlier stage carried a separate FFT-style tier/unlock ladder over a
DIFFERENT 30-job roster; that structure was never wired into play and contradicted the jobs you
actually pick, so it was reconciled away in favour of the callings. A tier/unlock progression is a
future design layer (Josh's balance call), not a shipped system -- this module describes what is
real today; its `validate()` guards the one invariant that must hold: no calling ships unarmed.
"""

from __future__ import annotations

from parts.world.seed import SEED_DIR, SeedError, load_abilities, load_jobs

# The per-job level cap. Progression's JP curve tops out here (Job Lvl 30 = 51,200 JP, pinned by the
# checkpoint test); job_ladder is the single source of the cap so the two never drift.
MAX_JOB_LEVEL = 30

# The playable roster: the active seed's callings (name/description/stats), each a job you can bind
# and level, and the moveset each may wield. Read once at import from the booted seed.
CALLINGS = load_jobs(SEED_DIR / "jobs.yaml")
_ABILITIES = load_abilities(SEED_DIR / "abilities.yaml")


def roster() -> list[str]:
    """Every playable calling (job) in the active world, sorted."""
    return sorted(CALLINGS)


def is_calling(job: str) -> bool:
    """Whether `job` is a playable calling in the active world."""
    return job in CALLINGS


def kit(calling: str) -> list[str]:
    """The ability labels a calling may wield -- its playable kit, sorted. Empty for a job that is
    not a calling (a character's subjob lends more; see abilities.abilities_for_session)."""
    return sorted(label for label, ability in _ABILITIES.items() if calling in ability["jobs"])


def is_armed(calling: str) -> bool:
    """Whether a calling ships with at least one ability (a real kit to fight with)."""
    return bool(kit(calling))


def validate() -> None:
    """The one job-system invariant: every playable calling is armed with at least one ability, so
    a new character can always pick a class and fight with it. Fails loud on an unarmed calling."""
    if not CALLINGS:
        return  # a seed may ship no callings (a non-combat world); nothing to arm
    unarmed = [c for c in CALLINGS if not is_armed(c)]
    if unarmed:
        raise SeedError(f"job system: callings shipped with no ability kit: {sorted(unarmed)}.")


validate()  # the roster is checked at import -- an unarmed calling never reaches a player
