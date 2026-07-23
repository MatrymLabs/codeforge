"""CARD: world -- world graph, direction aliases, movement.

The world is data -- and now it lives in a seed file, not in Python.
resolve_move is the only function that changes a player's location.
"""

from parts.world.doors import DOORS, barred_door_for
from parts.world.items import ITEMS
from parts.world.npcs import NPCS
from parts.world.seed import SEED_DIR, Room, inspect_world_links, load_rooms

SEED_PATH = SEED_DIR / "rooms.yaml"

WORLD: dict[str, Room] = load_rooms(SEED_PATH)
inspect_world_links(WORLD, ITEMS, NPCS)

# The spawn point is seed-defined, not hardcoded: the FIRST room in rooms.yaml.
# (first-forge -> "forge"; spiral-ascent -> "spiral_landing".)
START_ROOM: str = next(iter(WORLD))

DIRECTIONS: dict[str, str] = {
    "north": "north",
    "n": "north",
    "south": "south",
    "s": "south",
    "east": "east",
    "e": "east",
    "west": "west",
    "w": "west",
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
