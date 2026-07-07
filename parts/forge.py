"""CodeForge entry point: the power switch. All parts live in parts/.

The engine tick is handle_command(session, text) -> str: one command
in, one response out, as a plain function. game_loop is just a thin
terminal driver around it -- a socket gateway will be another.
"""

from parts.doors import unlock
from parts.events import announce, register, unregister
from parts.items import drop, inventory_text, room_items_text, take
from parts.npcs import room_npcs_text, talk
from parts.save import load_game, save_game
from parts.session import SESSIONS, Session, roster
from parts.world import DIRECTIONS, render_room, try_move

HELP_TEXT = (
    "Commands: look, go <direction> (or n/s/e/w/u/d), "
    "take, drop, inventory, talk <name>, say <msg>, who, unlock <door> with <key>, save, load, quit"
)


def render_scene(location: str, viewer: str = "") -> str:
    """The full projection of a room: place, things, people, players."""
    scene = [render_room(location)]
    extra = room_items_text(location)
    if extra:
        scene.append(extra)
    company = room_npcs_text(location)
    if company:
        scene.append(company)
    others = [pid for pid, s in SESSIONS.items() if s.location == location and pid != viewer]
    for pid in sorted(others):
        scene.append(f"{pid} is here.")
    return "\n".join(scene)


def _move(session: Session, direction: str) -> str:
    arrived, message = try_move(session.location, direction)
    if arrived != session.location:
        announce(
            session.location, f"{session.player_id} leaves {direction}.", exclude=session.player_id
        )
        session.location = arrived
        announce(arrived, f"{session.player_id} arrives.", exclude=session.player_id)
        return render_scene(arrived, viewer=session.player_id)
    return message


def handle_command(session: Session, raw: str) -> str:
    """The engine tick: one player command in, one response out."""
    raw = raw.strip().lower()

    if raw in ("quit", "q"):
        session.alive = False
        return "The world dims. See you next spark."
    if raw == "help":
        return HELP_TEXT
    if raw in ("look", "l"):
        return render_scene(session.location, viewer=session.player_id)
    if raw in DIRECTIONS:
        return _move(session, DIRECTIONS[raw])
    if raw.startswith("go "):
        word = raw.removeprefix("go ").strip()
        if word in DIRECTIONS:
            return _move(session, DIRECTIONS[word])
        return "You can't go that way."
    if raw.startswith("say "):
        message = raw.removeprefix("say ").strip()
        if not message:
            return "Say what?"
        announce(
            session.location, f'{session.player_id} says, "{message}"', exclude=session.player_id
        )
        return f'You say, "{message}"'
    if raw == "who":
        names = roster() or [session.player_id]
        return "Players online: " + ", ".join(names)
    if raw in ("inventory", "i", "inv"):
        return inventory_text()
    if raw.startswith(("take ", "get ")):
        word = raw.split(" ", 1)[1].strip()
        result = take(word, session.location)
        if result.startswith("You take"):
            announce(
                session.location,
                result.replace("You take", f"{session.player_id} takes", 1),
                exclude=session.player_id,
            )
        return result
    if raw.startswith("drop "):
        word = raw.split(" ", 1)[1].strip()
        result = drop(word, session.location)
        if result.startswith("You drop"):
            announce(
                session.location,
                result.replace("You drop", f"{session.player_id} drops", 1),
                exclude=session.player_id,
            )
        return result
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
        return f"{msg}\n{render_scene(session.location, viewer=session.player_id)}"
    if raw == "":
        return ""
    return "Huh? Type HELP for commands."


def game_loop() -> None:
    """Terminal driver: reads a keyboard, prints a screen. That's all."""
    session = Session(player_id="player")
    SESSIONS[session.player_id] = session
    register(session.player_id, print)
    print("Welcome to The First Forge. Type HELP to begin.")
    print(render_scene(session.location, viewer=session.player_id))

    try:
        while session.alive:
            response = handle_command(session, input("\n> "))
            if response:
                print(response)
    finally:
        unregister(session.player_id)
        SESSIONS.pop(session.player_id, None)


if __name__ == "__main__":
    game_loop()
