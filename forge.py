"""CodeForge entry point: the power switch. All parts live in parts/."""

from parts.doors import unlock
from parts.items import drop, inventory_text, room_items_text, take
from parts.save import load_game, save_game
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
            print(
                "Commands: look, go <direction> (or n/s/e/w/u/d), "
                "take, drop, inventory, unlock <door> with <key>, save, load, quit"
            )
        elif raw == "look":
            print(render_room(location))
            extra = room_items_text(location)
            if extra:
                print(extra)
        elif raw in DIRECTIONS:
            location = try_move(location, DIRECTIONS[raw])
        elif raw.startswith("go "):
            word = raw.removeprefix("go ").strip()
            if word in DIRECTIONS:
                location = try_move(location, DIRECTIONS[word])
            else:
                print("You can't go that way.")
        elif raw in ("inventory", "i", "inv"):
            print(inventory_text())
        elif raw.startswith(("take ", "get ")):
            word = raw.split(" ", 1)[1].strip()
            print(take(word, location))
        elif raw.startswith("drop "):
            word = raw.split(" ", 1)[1].strip()
            print(drop(word, location))
        elif raw.startswith("unlock "):
            rest = raw.removeprefix("unlock ").strip()
            if " with " in rest:
                door_word, key_word = (p.strip() for p in rest.split(" with ", 1))
                print(unlock(door_word, key_word, location))
            else:
                print("Unlock what with what? Try: unlock door with key")
        elif raw == "save":
            print(save_game(location))
        elif raw == "load":
            location, msg = load_game()
            print(msg)
            print(render_room(location))
        elif raw == "":
            continue
        else:
            print("Huh? Type HELP for commands.")


if __name__ == "__main__":
    game_loop()
