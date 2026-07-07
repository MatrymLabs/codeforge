"""CARD: world -- world graph, direction aliases, movement.

The world is data -- and now it lives in a seed file, not in Python.
try_move is the only function that changes a player's location.
"""

from pathlib import Path

from parts.doors import DOORS, door_blocking
from parts.seed import Room, load_rooms

SEED_PATH = Path(__file__).resolve().parent.parent / "seeds" / "first-forge" / "rooms.yaml"

WORLD: dict[str, Room] = load_rooms(SEED_PATH)

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


def try_move(location: str, direction: str) -> str:
    """Return the new room id, or the old one if movement fails."""
    blocked = door_blocking(location, direction)
    if blocked:
        print(f"{DOORS[blocked]['name'].capitalize()} is locked.")
        return location
    exits = WORLD[location]["exits"]
    if direction in exits:
        new_location = exits[direction]
        print(render_room(new_location))
        return new_location
    print("You can't go that way.")
    return location
