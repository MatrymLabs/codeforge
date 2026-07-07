"""CodeForge entry point: the power switch. All parts live in parts/."""

from parts.world import DIRECTIONS, render_room, try_move


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
