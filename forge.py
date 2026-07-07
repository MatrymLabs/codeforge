"""CodeForge: smallest playable loop.

Current skills baked in:
- world as data (WORLD dict = proto world graph)
- render/state separation (render_room is a projection)
- direction normalization (DIRECTIONS = proto MUD-IL alias table)
- movement isolated in try_move (recognition vs execution seam)
"""

# --- World data (this becomes the world graph, then Seed YAML, then DB rows) ---
WORLD = {
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
        "exits": {"west": "courtyard"},
    },
    "cellar": {
        "name": "The Forge Cellar",
        "desc": "Cool darkness. Crates of unworked ore line the walls, waiting for a purpose.",
        "exits": {"up": "forge"},
    },
}

# --- Normalization layer: many surface forms -> one canonical direction ---
DIRECTIONS = {
    "north": "north", "n": "north",
    "south": "south", "s": "south",
    "east": "east",  "e": "east",
    "west": "west",  "w": "west",
    "up": "up",      "u": "up",
    "down": "down",  "d": "down",
}


def render_room(room_id: str) -> str:
    room = WORLD[room_id]
    exits = ", ".join(room["exits"]) or "none"
    return f"\n== {room['name']} ==\n{room['desc']}\nExits: {exits}"


def try_move(location: str, direction: str) -> str:
    """Return the new room id, or the old one if movement fails."""
    exits = WORLD[location]["exits"]
    if direction in exits:
        new_location = exits[direction]
        print(render_room(new_location))
        return new_location
    print("You can't go that way.")
    return location


def game_loop() -> None:
    location = "forge"
    print("Welcome to The First Forge. Type HELP to begin.")
    print(render_room(location))

    while True:
        raw = input("\n> ").strip().lower()

        if raw in ("quit", "q"):
            print("The world dims. See you next spark.")
            break
        elif raw == "help":
            print("Commands: look, go <direction> (or just n/s/e/w/u/d), quit")
        elif raw == "look":
            print(render_room(location))
        elif raw in DIRECTIONS:
            location = try_move(location, DIRECTIONS[raw])
        elif raw.startswith("go "):
            word = raw.removeprefix("go ").strip()
            if word in DIRECTIONS:
                location = try_move(location, DIRECTIONS[word])
            else:
                print("You can't go that way.")
        elif raw == "":
            continue
        else:
            print("Huh? Type HELP for commands.")


if __name__ == "__main__":
    game_loop()