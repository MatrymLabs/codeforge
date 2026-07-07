"""CARD: world -- world graph, direction aliases, movement.

The world is data -- and now it lives in a seed file, not in Python.
try_move is the only function that changes a player's location.
"""

from parts.doors import DOORS, door_blocking
from parts.items import ITEMS
from parts.npcs import NPCS
from parts.seed import SEED_DIR, Room, load_rooms, validate_locations

SEED_PATH = SEED_DIR / "rooms.yaml"

WORLD: dict[str, Room] = load_rooms(SEED_PATH)
validate_locations(WORLD, ITEMS, NPCS)

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


def try_move(location: str, direction: str) -> tuple[str, str]:
    """Pure movement: returns (new_location, message).

    On success: (destination, ""). On failure: (same location, why).
    The world layer never prints -- rendering belongs to the caller."""
    blocked = door_blocking(location, direction)
    if blocked:
        return (location, f"{DOORS[blocked]['name'].capitalize()} is locked.")
    exits = WORLD[location]["exits"]
    if direction in exits:
        return (exits[direction], "")
    return (location, "You can't go that way.")
