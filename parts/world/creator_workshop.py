"""CARD: creator_workshop -- the Creator's Workshop: a protected admin dimension, owner-only.

Every generated CodeForge world carries one canonical, private place the players never see: the
Creator's Workshop, reached through the Creator's Door inside the Grand Library. It is the in-game
half of the Creator Experience (its outside-the-game twin is the Creator Console): an administrative
space represented THROUGH the game itself, where the world's owner shapes NPCs, quests, items, and
difficulty without editing files or touching a terminal.

This module is the foundation the workshop's stations will later hang on: it PLACES the canonical
rooms into any world and it GUARDS the barrier. The rules the prompt makes absolute:

  - The Grand Library is a normal, discoverable room (every world links it to the spawn).
  - The Creator's Door is CONCEALED: it is not one of the Library's listed exits, so players cannot
    discover, observe, or reveal it. The owner crosses by naming it (`go door`), not by chance.
  - Only the authenticated Seed Owner (the `owner` crown) may cross. Everyone else, whether they
    guess the door or try to teleport past it, receives exactly:
        "The barrier does not acknowledge your presence."
  - The Workshop is an isolated instance: its only tie to the world is the concealed door and a
    plain `out` exit back to the Library, so no ordinary movement or teleport reaches it.

State is data and text is a projection (Architecture Law 1): this module only assembles rooms and
answers the barrier question; the tick performs the crossing. The barrier check reads `session.rank`
directly (the Seed Owner holds the top crown) rather than importing `ranks`, which would form an
import cycle -- `ranks` may guard teleport by importing THIS module instead.
"""

from __future__ import annotations

from typing import NamedTuple

from parts.world.seed import Room
from parts.world.session import Session

# --- Canonical labels (frozen identity strings; never restyle -- persisted contract) ------------
GRAND_LIBRARY = "grand_library"
CREATOR_WORKSHOP = "creator_workshop"

# The exact refusal the barrier gives everyone who is not the Seed Owner. Frozen by the prompt.
_BARRIER_REFUSAL = "The barrier does not acknowledge your presence."

# The words that name the concealed Creator's Door out of the Grand Library. Kept OUT of the room's
# `exits` so the door never renders; a player cannot discover it, only the owner (who is told) names
# it. "door" is safe here because door_destination only fires while standing in the Grand Library.
_DOOR_WORDS = frozenset({"door"})


# --- The creation stations -----------------------------------------------------------------------
# The Workshop is a welcoming creative space, not a developer menu: each subsystem of CodeForge is a
# room the owner can WALK into, off the central hall. A station is data (a hall-noun, a room label,
# name, and a plain-language description of what a creator shapes there); install_workshop builds
# the rooms and wires the hall's exits from this table. The create-TOOLS (Create NPC, Build Quest,
# adjust difficulty) are fitted into these rooms in later stages; today each room honestly describes
# its purpose without claiming a command it does not yet carry.
class Station(NamedTuple):
    noun: str  # the hall exit that leads here (e.g. `npc`), and the way back is always `hall`/`out`
    label: str  # the room's frozen lowercase_snake_case label
    name: str  # the display name
    desc: str  # a welcoming, plain-language description of what a creator does here


STATIONS: tuple[Station, ...] = (
    Station(
        "planning",
        "planning_table",
        "The Planning Table",
        "A broad oak table strewn with maps, notes, and a design journal. Stand here to see your "
        "world whole. Type `survey` to read it: rooms, zones, inhabitants, and its scale.",
    ),
    Station(
        "npc",
        "npc_studio",
        "The NPC Studio",
        "Portrait frames and character sheets line the walls, each waiting for a face and a voice. "
        "This is where the people of your world are made: who they are, what they say, where they "
        "stand.",
    ),
    Station(
        "quests",
        "quest_archive",
        "The Quest Archive",
        "A tall cabinet of story-threads, each a task a hero might take up. Here you weave the "
        "quests that give your world its purpose, step by step, reward and all.",
    ),
    Station(
        "items",
        "item_forge",
        "The Item Forge",
        "An anvil and a wall of labelled drawers: blades, charms, potions, keys. Here you shape "
        "the things a hero finds, wears, and wields.",
    ),
    Station(
        "creatures",
        "creature_forge",
        "The Creature Forge",
        "Cages of light hold half-formed beasts, from field-mice to world-eaters. Here you breed "
        "the monsters and bosses that will test everyone who plays.",
    ),
    Station(
        "difficulty",
        "difficulty_desk",
        "The Difficulty Desk",
        "A console of gentle dials, each labelled in plain words: how hard the foes hit, how often "
        "they come, how generous the loot. Turn a dial to make your world kinder or crueller.",
    ),
    Station(
        "blueprints",
        "blueprint_repository",
        "The Blueprint Repository",
        "Flat drawers of rolled schematics, every system in the engine drawn out. For makers who "
        "want to read the deeper plans and draft their own.",
    ),
    Station(
        "stats",
        "statistics_wall",
        "The Statistics Wall",
        "A living wall of charts: who is playing and where they roam, an honest mirror of how your "
        "world is really being played. Type `activity` to read it.",
    ),
    Station(
        "publish",
        "publishing_portal",
        "The Publishing Portal",
        "A shimmering archway where a change becomes real. Preview what you have made, and when it "
        "is ready, publish it to the living world, or roll it back if it went wrong.",
    ),
)

# The rooms that live behind the barrier: the Workshop hall and every station. Membership is what
# teleport and any future reveal-vector must refuse for non-owners (the whole dimension is sealed).
WORKSHOP_ROOMS = frozenset({CREATOR_WORKSHOP, *(s.label for s in STATIONS)})


def is_workshop_room(room_id: str) -> bool:
    """Whether a room lives behind the barrier (the isolated administrative instance)."""
    return room_id in WORKSHOP_ROOMS


def is_seed_owner(session: Session) -> bool:
    """Whether this session is the authenticated Seed Owner: the authority the barrier honours.

    The Seed Owner holds the `owner` crown (the top rank); a wizard is not enough, by design."""
    return session.rank == "owner"


def barrier_refusal() -> str:
    """The exact message the barrier gives anyone who is not the Seed Owner."""
    return _BARRIER_REFUSAL


def door_destination(location: str, word: str) -> str | None:
    """The room the Creator's Door opens onto if `word` names it from `location`, else None.

    Returns the Workshop only when standing in the Grand Library and naming the concealed door; None
    everywhere else, so normal movement handles every other word. This never checks authority -- the
    caller consults `is_seed_owner` and either crosses or returns `barrier_refusal()`; the door is
    NAMEABLE by anyone, but CROSSABLE only by the owner (a guessing player still meets the wall)."""
    if location == GRAND_LIBRARY and word in _DOOR_WORDS:
        return CREATOR_WORKSHOP
    return None


def install_workshop(world: dict[str, Room]) -> None:
    """Place the canonical Grand Library and Workshop into `world`, in place and idempotent.

    The Grand Library links to the world's spawn (its first room) with a `library` noun exit both
    ways, so every world -- whatever its geography -- makes the Library reachable ("walk into the
    Grand Library"). The Workshop is added as an isolated instance: reachable ONLY across the
    concealed door (never wired into `exits`) with a plain `out` exit back to the Library so the
    owner can leave. Called during world assembly, after the seed and generators, before the link
    audit -- so the new rooms pass the same gates as authored ones."""
    if GRAND_LIBRARY in world:  # idempotent: never place the Library twice
        return
    if not world:  # a world with no rooms has no spawn to anchor the Library to
        raise WorkshopError("cannot install the Creator's Workshop into an empty world")
    spawn = next(iter(world))

    world[GRAND_LIBRARY] = Room(
        name="The Grand Library",
        desc=(
            "Ten thousand shelves spiral up into shadow, every ledger the world has ever kept "
            "waiting to be read. The air is warm with lamp oil and old paper. A quiet place; the "
            "world hums somewhere below."
        ),
        exits={"library": spawn, "out": spawn},
    )
    # The central hall opens onto every station (a listed noun exit each) and back to the Library.
    hall_exits = {station.noun: station.label for station in STATIONS}
    hall_exits["out"] = GRAND_LIBRARY
    world[CREATOR_WORKSHOP] = Room(
        name="The Creator's Workshop",
        desc=(
            "A wide, bright hall that answers to no map, ringed with doorways. Each leads to a "
            "station where a part of your world is shaped: the people, the quests, the creatures, "
            "the difficulty, and more. Step through any doorway to begin. The Grand Library lies "
            "back through the door (`out`)."
        ),
        exits=hall_exits,
    )
    # Each station is a room off the hall; `hall`/`out` both return to the central Workshop.
    for station in STATIONS:
        world[station.label] = Room(
            name=station.name,
            desc=station.desc,
            exits={"hall": CREATOR_WORKSHOP, "out": CREATOR_WORKSHOP},
        )
    # Make the Library discoverable from spawn (a plain, listed noun exit both ways).
    world[spawn]["exits"].setdefault("library", GRAND_LIBRARY)


class WorkshopError(ValueError):
    """The Creator's Workshop could not be installed (e.g. into an empty world). Fails loud."""


# --- Station tools -------------------------------------------------------------------------------
# The first LIVE station tool. Each tool is owner-gated AND station-gated: it works only for the
# Seed Owner standing in the right station room, and returns a plain "nothing here" to anyone else,
# so a station leaks nothing about the workshop. The Planning Table is read-only (no mutation, no
# persistence), the safest first tool; the mutating tools (NPC Studio, Difficulty Desk) come next.
PLANNING_TABLE = "planning_table"


def plan_survey(session: Session) -> str:
    """The Planning Table's live tool: the owner's honest, plain-language overview of their world.

    Composes the two Creator campaigns: it measures the LIVE world (rooms, zones, inhabitants, wild
    creatures) and reads its scale against the Seed Package deployment tiers (the nearest tier by
    room count). Only the Seed Owner standing at the Planning Table sees it; everyone else is told
    there is nothing to survey. Read-only: it never mutates world state (Architecture Law 1)."""
    if session.location != PLANNING_TABLE or not is_seed_owner(session):
        return "You see nothing here to survey."

    # Lazy imports: this module is loaded during world assembly, so it must not import the world,
    # NPC, or Seed Package modules at import time (a cycle / premature read). At call time they are
    # fully built.
    from parts import seed_package as sp
    from parts.world.npcs import NPCS
    from parts.world.world import WORLD
    from parts.world.zones import ZONES

    rooms = len(WORLD)
    zones = len(ZONES)
    wild = sum(1 for npc in NPCS.values() if npc.get("ambient"))
    inhabitants = len(NPCS) - wild
    scale = _nearest_tier_name(rooms, sp)

    return (
        "== The Planning Table ==\n"
        "Your world at a glance:\n"
        f"  Rooms:        {rooms:,}\n"
        f"  Zones:        {zones:,}\n"
        f"  Inhabitants:  {inhabitants:,}   (the people who populate it)\n"
        f"  Wild things:  {wild:,}   (creatures roaming the wilds)\n"
        f"This is roughly a {scale} world (measured by its room count)."
    )


def _nearest_tier_name(rooms: int, sp: object) -> str:
    """The deployment tier whose derived room count sits closest to `rooms`, named for a human.
    `sp` is the seed_package module (passed in to keep this helper import-free)."""
    tiers = sp.DEPLOYMENT_TIERS  # type: ignore[attr-defined]
    nearest = min(tiers, key=lambda t: abs(sp.derive_sizing(t).rooms - rooms))  # type: ignore[attr-defined]
    return f"{nearest.name} ({nearest.summary})"


STATISTICS_WALL = "statistics_wall"


def wall_activity(session: Session) -> str:
    """The Statistics Wall's live tool: who is playing the owner's world, and where.

    Owner-gated AND station-gated like every station tool. Read-only: it reflects the live session
    roster (players online and the room/zone each stands in) without touching world state. This is
    the operational mirror the Planning Table's `survey` is not: `survey` reads the world's SHAPE,
    `activity` reads its LIFE."""
    if session.location != STATISTICS_WALL or not is_seed_owner(session):
        return "The wall shows you nothing here."

    from parts.world.session import SESSIONS, display_name, roster
    from parts.world.world import WORLD
    from parts.world.zones import zone_of

    online = roster()
    lines = ["== The Statistics Wall ==", f"Players online: {len(online)}"]
    for name in online:
        seat = SESSIONS[name]
        room_data = WORLD.get(seat.location)
        room = room_data["name"] if room_data else seat.location
        zone = zone_of(seat.location)
        where = f"{room}, {zone}" if zone else room
        lines.append(f"  {display_name(name)} -- {where}")
    if not online:
        lines.append("  (no one is exploring your world right now)")
    return "\n".join(lines)
