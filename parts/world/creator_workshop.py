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

import re
from typing import NamedTuple

from parts.world.seed import Item, Npc, Room
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
        "This is where the people of your world are made. Type `create npc <name> at <room>` to "
        "make one.",
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
        "the things a hero finds. Type `create item <name> at <room>` to make one.",
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
        "A shimmering archway where a change becomes real. Type `preview` to review what you have "
        "made, `publish` to send it to the living world, or `rollback` to discard it.",
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
    """The Planning Table's live tool: the owner's overview of their world (station-gated). The
    report is `world_survey`, so the Creator Artifact can channel the same view remotely."""
    if session.location != PLANNING_TABLE or not is_seed_owner(session):
        return "You see nothing here to survey."
    return world_survey(session)


def world_survey(session: Session) -> str:
    """The world-shape report: the LIVE world (rooms, zones, inhabitants, wild creatures) read
    against the Seed Package deployment tiers. Owner-only; read-only (Architecture Law 1). The
    Planning Table shows it in place; the Creator Artifact channels it from anywhere."""
    if not is_seed_owner(session):
        return "You see nothing here to survey."

    # Lazy imports: this module is loaded during world assembly, so it must not import the world,
    # NPC, or Seed Package modules at import time (a cycle / premature read). At call time they are
    # fully built.
    from kernel import seed_package as sp
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
    """The Statistics Wall's live tool (station-gated). The report is `live_activity`, so the
    Creator Artifact can channel the same live-play view remotely."""
    if session.location != STATISTICS_WALL or not is_seed_owner(session):
        return "The wall shows you nothing here."
    return live_activity(session)


def live_activity(session: Session) -> str:
    """The live-play report itself: who is playing the owner's world and where (room/zone each
    stands in). Owner-only; read-only. `survey` reads the SHAPE, `activity` reads the LIFE."""
    if not is_seed_owner(session):
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


# --- The change buffer + the first MUTATING tool -------------------------------------------------
# The Creator Experience's LIVE PREVIEW loop, live-only by design (Josh's keel call): the owner
# STAGES edits into a per-session buffer, PREVIEWS them, then PUBLISHES them to the LIVE world, or
# ROLLS them back. Publish writes to the in-memory world only, never to the seed files, so a change
# is reversible and vanishes on restart (persistence to the seed is a separate, later decision).
# This keeps Architecture Law 1 intact: a staged change is inert data; the ONE validated apply-path
# (`_apply`) is the only thing that mutates canonical state, and only at the owner's explicit
# `publish`. Each editable KIND (create_npc, create_item, ...) is one station tool + one apply-path.
NPC_STUDIO = "npc_studio"
ITEM_FORGE = "item_forge"
PUBLISHING_PORTAL = "publishing_portal"


class StagedChange(NamedTuple):
    """One inert, previewable edit waiting in a draft. `kind` selects the apply-path; `summary` is
    the plain-language line the owner reads in a preview; `payload` carries the apply data."""

    kind: str
    summary: str
    payload: dict[str, str]


# Per-session drafts, keyed by player_id. Ephemeral (never persisted): a draft is the owner's
# unpublished work, cleared on publish or rollback.
_DRAFTS: dict[str, list[StagedChange]] = {}


def _draft(session: Session) -> list[StagedChange]:
    """The owner's current draft (created empty on first use)."""
    return _DRAFTS.setdefault(session.player_id, [])


def _owner_at(session: Session, room: str) -> bool:
    """Whether the Seed Owner is standing at a specific station."""
    return is_seed_owner(session) and session.location == room


def _owner_in_workshop(session: Session) -> bool:
    """Whether the Seed Owner is anywhere inside the Workshop (hall or any station)."""
    return is_seed_owner(session) and session.location in WORKSHOP_ROOMS


def _unique_label(name: str, taken: set[str], fallback: str) -> str:
    """A unique lowercase_snake_case label from a display name (never collides with `taken`)."""
    base = "_".join(re.findall(r"[a-z0-9]+", name.lower())) or fallback
    label, n = base, 2
    while label in taken:
        label, n = f"{base}_{n}", n + 1
    return label


# One placeable KIND the owner can create: its subject word, its station, and the plain noun used in
# messages. Both create_npc and create_item are the same staging move (name a thing, name a room),
# so they share `_stage`; only the apply-path (`_apply`) differs.
class _Creatable(NamedTuple):
    subject: str  # the word after `create` (npc / item)
    kind: str  # the StagedChange kind
    station: str  # the station room where it may be created
    station_name: str  # the display name of that station
    thing: str  # the plain noun for messages (person / thing)


_CREATABLES: dict[str, _Creatable] = {
    "npc": _Creatable("npc", "create_npc", NPC_STUDIO, "NPC Studio", "person"),
    "item": _Creatable("item", "create_item", ITEM_FORGE, "Item Forge", "thing"),
}


def create(session: Session, arg: str) -> str:
    """The `create` verb: route `create <npc|item> <name> at <room>` to the right station tool.

    Owner-gated AND station-gated (each kind to its own station). The thing is not made live here,
    only staged into the draft after the room is validated; `preview`/`publish` finish the loop."""
    subject, _, rest = arg.strip().partition(" ")
    spec = _CREATABLES.get(subject.lower())
    if spec is None:
        return "You can create an npc or an item. Try: create npc <name> at <room>"
    return _stage(session, rest, spec)


def _stage(session: Session, rest: str, spec: _Creatable) -> str:
    """Validate and stage a `<name> at <room>` creation for one creatable kind. Fails loud early on
    a bad station, a missing name/room, or an unreal room; nothing is staged unless it is valid."""
    if not _owner_at(session, spec.station):
        return f"You cannot make a {spec.thing} here. Do it at the {spec.station_name}."
    rest = rest.strip()
    usage = f"create {spec.subject} <name> at <room>"
    if not rest:
        return f"To make one, type: {usage}"
    if " at " not in rest:
        return f"Say where it goes: {usage}"
    name, _, room = rest.rpartition(" at ")
    name, room = name.strip(), room.strip().lower()
    if not name:
        return f"Give it a name: {usage}"

    from parts.world.world import WORLD

    if room not in WORLD:
        return f"There is no room labelled '{room}'. Name a real room to place it in."

    live = _live_labels(spec.kind)
    taken = live | {c.payload["label"] for c in _draft(session) if c.kind == spec.kind}
    label = _unique_label(name, taken, fallback=spec.subject)
    summary = f"create the {spec.thing} '{name}' in {WORLD[room]['name']}"
    _draft(session).append(
        StagedChange(spec.kind, summary, {"label": label, "name": name, "room": room})
    )
    return (
        f"Staged: {summary}.\n"
        f"{len(_draft(session))} change(s) waiting. Type `preview` to review, then bring them to "
        f"the Publishing Portal to `publish` (or `rollback` to discard)."
    )


def _live_labels(kind: str) -> set[str]:
    """The labels already taken in the live world for a creatable kind (so a new one is unique)."""
    if kind == "create_npc":
        from parts.world.npcs import NPCS

        return set(NPCS)
    if kind == "create_item":
        from parts.world.items import ITEMS

        return set(ITEMS)
    return set()


def preview_changes(session: Session) -> str:
    """List the owner's staged, not-yet-live changes. Available anywhere in the Workshop."""
    if not _owner_in_workshop(session):
        return "There is nothing to preview here."
    draft = _draft(session)
    if not draft:
        return "Nothing is staged. Your world is unchanged."
    lines = ["== Pending changes (preview, not yet live) =="]
    lines += [f"  {i}. {change.summary}" for i, change in enumerate(draft, 1)]
    lines.append(
        "At the Publishing Portal: `publish` to make these live, or `rollback` to discard."
    )
    return "\n".join(lines)


def publish_changes(session: Session) -> str:
    """Apply every staged change to the LIVE world, then clear the draft. Publishing Portal only.

    This is the single sanctioned mutation point: each staged change flows through `_apply`, the one
    validated apply-path, so canonical state changes only here and only at the owner's word. Writes
    the in-memory world only (live-only); nothing touches the seed files."""
    if not is_seed_owner(session):
        return "There is nothing to publish here."
    if session.location != PUBLISHING_PORTAL:
        return "Bring your changes to the Publishing Portal to publish them."
    draft = _draft(session)
    if not draft:
        return "Nothing is staged to publish."
    applied = [_apply(change) for change in draft]
    _DRAFTS[session.player_id] = []
    return "Published to the living world:\n" + "\n".join(f"  - {line}" for line in applied)


def rollback_changes(session: Session) -> str:
    """Discard the owner's staged changes without publishing. The Publishing Portal only."""
    if not is_seed_owner(session):
        return "There is nothing to roll back here."
    if session.location != PUBLISHING_PORTAL:
        return "Bring your changes to the Publishing Portal to roll them back."
    count = len(_draft(session))
    _DRAFTS[session.player_id] = []
    if not count:
        return "Nothing was staged. Your world is unchanged."
    return f"Rolled back {count} staged change(s). Nothing was published; your world is unchanged."


def _apply(change: StagedChange) -> str:
    """The one validated apply-path: turn a staged change into a live world mutation. Fails loud on
    an unknown kind (a staged change the buffer never should have held)."""
    if change.kind == "create_npc":
        return _apply_create_npc(change.payload)
    if change.kind == "create_item":
        return _apply_create_item(change.payload)
    raise WorkshopError(f"unknown staged change kind: {change.kind!r}")


def _apply_create_item(payload: dict[str, str]) -> str:
    """Add a fresh, plain item to the live world, lying in its room. It is its own prototype (no
    equipment slot, no modifiers): a created object a hero can find and pick up."""
    from parts.world.items import ITEMS

    name, room, label = payload["name"], payload["room"], payload["label"]
    keywords = list(dict.fromkeys([*re.findall(r"[a-z0-9]+", name.lower()), label]))
    ITEMS[label] = Item(
        name=name,
        keywords=keywords,
        location=f"room:{room}",
        slot="",
        mods={},
    )
    return f"'{name}' now lies in {room}"


def _apply_create_npc(payload: dict[str, str]) -> str:
    """Add a fresh, peaceful NPC to the live world and re-index its room so it appears at once. The
    NPC is peaceful (hp 0, atk 0): a created townsperson, never a hidden weapon."""
    from parts.world.npcs import NPCS, reindex_npcs

    name, room, label = payload["name"], payload["room"], payload["label"]
    keywords = list(dict.fromkeys([*re.findall(r"[a-z0-9]+", name.lower()), label]))
    NPCS[label] = Npc(
        name=name,
        keywords=keywords,
        location=room,
        dialogue=[f"{name} nods to you."],
        next_line=0,
        hp=0,
        hp_now=0,
        xp=0,
        atk=0,
    )
    reindex_npcs()
    return f"'{name}' now stands in {room}"
