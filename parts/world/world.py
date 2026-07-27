"""CARD: world -- world graph, direction aliases, movement.

The world is data -- and now it lives in a seed file, not in Python.
resolve_move is the only function that changes a player's location.
"""

from parts.world.armory import arm_guardians
from parts.world.creator_workshop import install_workshop
from parts.world.doors import DOORS, barred_door_for
from parts.world.items import ITEMS, register_prototypes
from parts.world.npcs import NPCS
from parts.world.seed import SEED_DIR, Room, inspect_world_links, load_rooms
from parts.world.spiral import extend_world_with_road, load_spiral_config
from parts.world.townsfolk import load_settlements, populate_settlements
from parts.world.wildlands import (
    generate_wildlands,
    load_wildlands_config,
    wire_attach_exits,
)

SEED_PATH = SEED_DIR / "rooms.yaml"

WORLD: dict[str, Room] = load_rooms(SEED_PATH)
# Procedurally extend the Forgeward Road outward across the wilds if the seed opts in (spiral.yaml).
# The generated marches are seed-shaped data, merged BEFORE validation so the same loader gates
# check them, and the seed's attach room grows an `east` exit onto the first march (flat, no climb).
_spiral_config = load_spiral_config(SEED_DIR / "spiral.yaml")
if _spiral_config is not None:
    extend_world_with_road(WORLD, NPCS, _spiral_config)

# Procedurally grow wilderness REGIONS if the seed opts in (wildlands.yaml): a compact config per
# region expands into a connected, biome-varied trail-network with ambient life, through the
# loader gates. This is how the world reaches world-generation scale without hand-authoring every
# room (parts.world.wildlands, a sibling of the Spiral). Merged BEFORE validation, so a bad config
# fails loud; each region's attach room grows one exit onto its trail-head.
_wildlands_configs = load_wildlands_config(SEED_DIR / "wildlands.yaml")
if _wildlands_configs is not None:
    _wild_rooms, _wild_npcs = generate_wildlands(_wildlands_configs, set(WORLD))
    WORLD.update(_wild_rooms)
    NPCS.update(_wild_npcs)
    wire_attach_exits(WORLD, _wildlands_configs)
    # Forge a themed gear drop for every generated guardian (parts.world.armory), so felling a named
    # hunt target can drop something to wear; the affix factory rolls rarity on top at defeat.
    # Registered as prototypes (not just appended to ITEMS) before the link audit, so a guardian's
    # drop can be cloned and passes the same gate as authored gear.
    register_prototypes(arm_guardians(_wild_npcs))

# Populate the map's settlements (seeds/<world>/settlements.yaml) with townsfolk and a merchant at
# each town's level band (parts.world.townsfolk) -- the economy sink and the towns' life. Merged
# before the link audit, so each merchant's shop wares are cross-checked like an authored shop.
_settlements = load_settlements(SEED_DIR / "settlements.yaml")
if _settlements is not None:
    NPCS.update(populate_settlements(_settlements))

# Every generated world carries the Creator's Workshop: a Grand Library linked to the spawn, and a
# concealed Creator's Door onto an isolated administrative instance only the Seed Owner may cross
# (parts.world.workshop). Installed after the seed and generators, before the link audit, so the
# canonical rooms pass the same gates as authored ones.
install_workshop(WORLD)

inspect_world_links(WORLD, ITEMS, NPCS)

# With the full foe set assembled (seed + the procedural Spiral), generate a hunt-contract for
# every combatant foe -- side-content at volume, folded into the quest engine (parts.world.quest).
from parts.world.quest import register_bounties  # noqa: E402 -- after NPCS is complete

register_bounties(NPCS)

# The spawn point is seed-defined, not hardcoded: the FIRST room in rooms.yaml.
# (first-forge -> "forge"; spiral-ascent -> "spiral_landing".)
START_ROOM: str = next(iter(WORLD))

# The compass a Forger can walk: four cardinals, four diagonals, and the vertical pair, each with a
# one- or two-letter shorthand. A room's exit may also be keyed by a NOUN (`gate`, `market`, `in`,
# `out`) -- those are not listed here; they are typed literally and resolved against the room's own
# exits (see _go_cmd and the noun-exit fallback in forge._route). The metaphor: the compass is
# fixed, but a threshold can be named for the place it opens onto.
DIRECTIONS: dict[str, str] = {
    "north": "north",
    "n": "north",
    "south": "south",
    "s": "south",
    "east": "east",
    "e": "east",
    "west": "west",
    "w": "west",
    "northeast": "northeast",
    "ne": "northeast",
    "northwest": "northwest",
    "nw": "northwest",
    "southeast": "southeast",
    "se": "southeast",
    "southwest": "southwest",
    "sw": "southwest",
    "up": "up",
    "u": "up",
    "down": "down",
    "d": "down",
}


def render_room(room_id: str) -> str:
    room = WORLD[room_id]
    exits = ", ".join(room["exits"]) or "none"
    return f"\n== {room['name']} ==\n{room['desc']}\nExits: {exits}"


def dynamic_capability(room_id: str) -> str:
    """The live capability a room surfaces on look (seed-declared `dynamic`), or "" for none."""
    room = WORLD.get(room_id)
    return room.get("dynamic", "") if room is not None else ""


def resolve_move(location: str, direction: str) -> tuple[str, str]:
    """Pure movement: returns (new_location, message).

    On success: (destination, ""). On failure: (same location, why).
    The world layer never prints -- rendering belongs to the caller."""
    blocked = barred_door_for(location, direction)
    if blocked:
        return (location, f"{DOORS[blocked]['name'].capitalize()} is locked.")
    exits = WORLD[location]["exits"]
    if direction in exits:
        return (exits[direction], "")
    return (location, "You can't go that way.")
