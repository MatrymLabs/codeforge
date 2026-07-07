"""CARD: world -- world graph, direction aliases, movement.

The world is data. Rooms are nodes, exits are edges.
try_move is the only function that changes a player's location.
"""

from typing import TypedDict

from parts.doors import DOORS, door_blocking


class Room(TypedDict):
    """The shape every room must have. Structure, checked by machine."""

    name: str
    desc: str
    exits: dict[str, str]


WORLD: dict[str, Room] = {
    "forge": {
        "name": "The Cold Forge",
        "desc": "You stand beside a cold forge beneath unfamiliar stars.\n"
        'A brass plaque on the anvil reads: "Every world begins as a spark."',
        "exits": {"north": "courtyard", "down": "cellar"},
    },
    "courtyard": {
        "name": "Broken Courtyard",
        "desc": "Cracked flagstones stretch under a violet sky. Wind hums through the ruins.",
        "exits": {"south": "forge", "east": "library"},
    },
    "library": {
        "name": "The Old Library",
        "desc": "Dust drifts between towering shelves. An oak door in the back is sealed shut.",
        "exits": {"west": "courtyard", "north": "archive"},
    },
    "archive": {
        "name": "The Sealed Archive",
        "desc": "Forbidden shelves climb into darkness. The air tastes of secrets and old ink.",
        "exits": {"south": "library"},
    },
    "cellar": {
        "name": "The Forge Cellar",
        "desc": "Cool darkness. Crates of unworked ore line the walls, waiting for a purpose.",
        "exits": {"up": "forge"},
    },
}

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
