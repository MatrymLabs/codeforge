"""CARD: session -- one player's connection state.

A Session is everything that belongs to ONE player: identity,
position, liveness. World state stays canonical and SHARED;
sessions are each player's lens onto it.

This card deletes the engine's single-player assumption -- the
prerequisite for gateways. Tomorrow, every connected socket gets
its own Session pointed at the same world.
"""

from dataclasses import dataclass, field

from parts.job_progress import JobProgress
from parts.resources import Resource
from parts.stats import StatBlock


def _spawn() -> str:
    """The seed's first room. Imported lazily so `codeforge grant` (which touches
    Session but not the world) doesn't pay to load the whole seed."""
    from parts.world import START_ROOM

    return START_ROOM


@dataclass
class Session:
    """One player's seat at the world."""

    player_id: str
    location: str = field(default_factory=_spawn)
    alive: bool = True
    named: bool = False
    rank: str = "player"
    account: str = ""
    job: str = ""
    secondary_job: str = ""  # the equipped subjob label, or "" for none
    level: int = 1
    xp: int = 0
    stats: StatBlock | None = None
    resources: dict[str, Resource] = field(default_factory=dict)
    # Transient combat state (not persisted): ability cooldowns and active statuses,
    # each a name -> remaining-ticks countdown. A fresh session starts with a clear board.
    cooldowns: dict[str, int] = field(default_factory=dict)
    statuses: dict[str, int] = field(default_factory=dict)
    # Per-job progression, keyed by job id. A character keeps a record per job they take up,
    # so switching jobs never erases a prior job's level. Persisted via the job_progress card.
    job_progress: dict[str, JobProgress] = field(default_factory=dict)
    # Equipped gear, keyed by slot (weapon/body/head/...). Values are item ids. Runtime state.
    equipped: dict[str, str] = field(default_factory=dict)


# The registry of connected sessions. Gateways and game_loop register
# here; 'who' reads it. One world, many seats.
SESSIONS: dict[str, Session] = {}


def roster() -> list[str]:
    """Names of everyone currently seated, alphabetized."""
    return sorted(SESSIONS)


def display_name(player_id: str) -> str:
    """Proper-noun projection: identity stays lowercase; display is
    capitalized at the last moment ('matrym' -> 'Matrym',
    'iron_fist' -> 'Iron Fist'). Never stored, always derived."""
    return player_id.replace("_", " ").title()
