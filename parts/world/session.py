"""CARD: session -- one player's connection state.

A Session is everything that belongs to ONE player: identity,
position, liveness. World state stays canonical and SHARED;
sessions are each player's lens onto it.

This card deletes the engine's single-player assumption -- the
prerequisite for gateways. Tomorrow, every connected socket gets
its own Session pointed at the same world.
"""

from dataclasses import dataclass, field

from kernel.shelf.stats import StatBlock
from parts.world.job_progress import JobProgress
from parts.world.resources import Resource


def _spawn() -> str:
    """The seed's first room. Imported lazily so `codeforge grant` (which touches
    Session but not the world) doesn't pay to load the whole seed."""
    from parts.world.world import START_ROOM

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
    order: str = ""  # the sworn Order (guild-allegiance) label, or "" for none; persisted
    guild: str = ""  # the player guild this hero belongs to (a name), or "" for none; persisted
    guild_rank: str = ""  # rank in that guild: leader | officer | member (or "" when guildless)
    coins: int = 0  # the purse: earned from kills, spent at shops; persisted
    level: int = 1
    xp: int = 0
    stats: StatBlock | None = None
    resources: dict[str, Resource] = field(default_factory=dict)
    # Transient combat state (not persisted): ability cooldowns and active statuses,
    # each a name -> remaining-ticks countdown. A fresh session starts with a clear board.
    cooldowns: dict[str, int] = field(default_factory=dict)
    statuses: dict[str, int] = field(default_factory=dict)
    # Heal-over-time boons (a `regen` ability): name -> {heal, ticks}. Beneficial, so `cleanse`
    # never touches these (harmful afflictions live separately). Transient, not persisted.
    regens: dict[str, dict[str, int]] = field(default_factory=dict)
    # Harmful statuses the player SUFFERS (the mirror of the foe-side burn/daze): damage-over-time
    # afflictions (name -> {damage, ticks}) and a daze countdown. Aged on the world beat
    # (parts.world.afflictions.tick_afflictions), transient, never persisted.
    afflictions: dict[str, dict[str, int]] = field(default_factory=dict)
    dazed: int = 0
    # Aggression leash: unanswered world-beats per aggressive NPC sharing the room. A player's
    # strike resets that NPC's count; after LEASH beats with no answer the foe breaks off, so a
    # player who cannot win but stops fighting is never soft-locked. Transient, not persisted.
    aggro_beats: dict[str, int] = field(default_factory=dict)
    # Per-job progression, keyed by job id. A character keeps a record per job they take up,
    # so switching jobs never erases a prior job's level. Persisted via the job_progress card.
    job_progress: dict[str, JobProgress] = field(default_factory=dict)
    # Daily lockouts: a key (a boss, a daily) -> the UTC date its bonus was last claimed. Persisted,
    # so the once-a-day cap survives logout (parts.world.lockouts).
    lockouts: dict[str, str] = field(default_factory=dict)
    # Equipped gear, keyed by slot (weapon/body/head/...). Values are item ids. Runtime state.
    equipped: dict[str, str] = field(default_factory=dict)
    # Allocated attribute points: attribute -> points spent (build agency). A level-up grants points
    # (parts.world.allocate); `allocate` spends them into an attribute, capped per level. Persisted,
    # and folded onto the job's base stats when the StatBlock is built (jobs.bind_calling).
    allocated: dict[str, int] = field(default_factory=dict)
    # Gather-node cooldowns: room -> world-beats until this player may `gather` there again. A node
    # renews per player (an MMO node is not contested). Transient combat/world state, not persisted.
    gather_cooldowns: dict[str, int] = field(default_factory=dict)
    # Shrine cooldowns: room -> world-beats until this player may `pray` at that shrine again. Per
    # player, like a gather node; transient, not persisted (parts.world.shrine).
    shrine_cooldowns: dict[str, int] = field(default_factory=dict)
    # Maker's trades: profession id -> units of practice earned by gathering/crafting what the trade
    # governs. Level derives from practice (parts.world.professions.level_for); persisted per hero.
    professions: dict[str, int] = field(default_factory=dict)
    # Standing with each Order: order id -> reputation, earned through deeds. The named tier derives
    # from the number (parts.world.reputation). Persisted per hero.
    reputation: dict[str, int] = field(default_factory=dict)
    # This hero's personal friends list: lowercase labels of heroes worth tracking. One-directional
    # (yours alone); `friends` shows who is online. Persisted per hero (parts.world.friends).
    friends: list[str] = field(default_factory=list)


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


def sentence_case(name: str) -> str:
    """Start a sentence with an already-authored name, preserving its internal casing.
    str.capitalize() lower-cases the rest ('the Cinder-Wight' -> 'The cinder-wight') and
    str.title() re-cases every word ('Wren the Smith' -> 'Wren The Smith'); both mangle a proper
    noun a seed spelled out on purpose. This only lifts the first character, so 'the Cinder-Wight'
    -> 'The Cinder-Wight' and 'Professor Codex' stays 'Professor Codex'."""
    return name[:1].upper() + name[1:]
