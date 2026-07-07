"""CodeForge entry point: the power switch. All parts live in parts/.

The engine tick is handle_command(session, text) -> str: one command
in, one response out, as a plain function. game_loop is just a thin
terminal driver around it -- a socket gateway will be another.
"""

from parts.doors import unlock
from parts.items import drop, inventory_text, room_items_text, take
from parts.npcs import room_npcs_text, talk
from parts.save import load_game, save_game
from parts.session import Session
from parts.world import DIRECTIONS, render_room, try_move

HELP_TEXT = (
    "Commands: look, go <direction> (or n/s/e/w/u/d), "
    "take, drop, inventory, talk <name>, unlock <door> with <key>, save, load, quit"
)


def render_scene(location: str) -> str:
    """The full projection of a room: place, things, people."""
    scene = [render_room(location)]
    extra = room_items_text(location)
    if extra:
        scene.append(extra)
    company = room_npcs_text(location)
    if company:
        scene.append(company)
    return "\n".join(scene)


def _move(session: Session, direction: str) -> str:
    arrived, message = try_move(session.location, direction)
    if arrived != session.location:
        session.location = arrived
        return render_scene(arrived)
    return message


def handle_command(session: Session, raw: str) -> str:
    """The engine tick: one player command in, one response out."""
    raw = raw.strip().lower()

    if raw in ("quit", "q"):
        session.alive = False
        return "The world dims. See you next spark."
    if raw == "help":
        return HELP_TEXT
    if raw == "look":
        return render_scene(session.location)
    if raw in DIRECTIONS:
        return _move(session, DIRECTIONS[raw])
    if raw.startswith("go "):
        word = raw.removeprefix("go ").strip()
        if word in DIRECTIONS:
            return _move(session, DIRECTIONS[word])
        return "You can't go that way."
    if raw in ("inventory", "i", "inv"):
        return inventory_text()
    if raw.startswith(("take ", "get ")):
        word = raw.split(" ", 1)[1].strip()
        return take(word, session.location)
    if raw.startswith("drop "):
        word = raw.split(" ", 1)[1].strip()
        return drop(word, session.location)
    if raw.startswith("talk "):
        word = raw.split(" ", 1)[1].strip()
        return talk(word, session.location)
    if raw.startswith("unlock "):
        rest = raw.removeprefix("unlock ").strip()
        if " with " in rest:
            door_word, key_word = (p.strip() for p in rest.split(" with ", 1))
            return unlock(door_word, key_word, session.location)
        return "Unlock what with what? Try: unlock door with key"
    if raw == "save":
        return save_game(session.location)
    if raw == "load":
        session.location, msg = load_game()
        return f"{msg}\n{render_scene(session.location)}"
    if raw == "":
        return ""
    return "Huh? Type HELP for commands."


def game_loop() -> None:
    """Terminal driver: reads a keyboard, prints a screen. That's all."""
    session = Session(player_id="player")
    print("Welcome to The First Forge. Type HELP to begin.")
    print(render_scene(session.location))

    while session.alive:
        response = handle_command(session, input("\n> "))
        if response:
            print(response)


if __name__ == "__main__":
    game_loop()
