"""CodeForge entry point: the power switch. All parts live in parts/.

The engine tick is handle_command(session, text) -> str: one command
in, one response out, as a plain function. game_loop is just a thin
terminal driver around it -- a socket gateway will be another.
"""

import re

from parts.accounts import (
    has_password,
    inspect_login,
    parse_handle,
    reforge_secret,
    set_password,
    verify_password,
)
from parts.accounts import register as register_account
from parts.architect import consult
from parts.career import career
from parts.characters import load_character, restore_character, save_character
from parts.classroom import (
    ask_question,
    hint,
    lesson_list,
    lesson_start,
    progress,
    submit_answer,
    talk_to_codex,
)
from parts.combat import attack
from parts.commands import ADMIN, CORE, Command, CommandSet
from parts.console import console_menu, diagnostics_view, run_view
from parts.doors import unlock
from parts.events import announce, bind_echo, rename_echo, unbind_echo
from parts.generate import system_generate
from parts.items import drop, inventory_text, room_items_text, take
from parts.jobs import JOBS, bind_calling, calling_index, render_sheet
from parts.law import law
from parts.library import library
from parts.npcs import room_npcs_text, talk, trace_npc
from parts.pioneer import pioneer
from parts.pm import pm_metrics, pm_status
from parts.qualitygate import docs_check, render_gate, render_gate_all, render_safety
from parts.ranks import wizard_command
from parts.registry import (
    registry_find,
    registry_list,
    registry_show,
    registry_status,
    registry_type,
)
from parts.regulations import regs
from parts.save import awaken_snapshot, seal_snapshot
from parts.session import SESSIONS, Session, display_name, roster
from parts.veritas import render_truth
from parts.workshop import catalog_view, reuse_search, workshop_menu
from parts.world import DIRECTIONS, render_room, resolve_move

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,15}$")

HELP_TEXT = (
    "Commands: look, go <direction> (or n/s/e/w/u/d), "
    "take, drop, inventory, talk <npc>, say <msg>, name <yourname>, who, "
    "jobs, job <calling>, score, attack <target>, "
    "unlock <door> with <key>, regs [topic|id], library [id], law [id], "
    "registry [show|find|type|status], "
    "qa gate [all|<id>], safety review <id>, docs check, pm status, pm metrics, "
    "truth check, career, pioneer, "
    "workshop, catalog, reuse <term>, console, run <check>, diagnostics, "
    "security, ai <prompt>, lesson list, question, answer <A-D>, hint, progress, "
    "passwd, save, load, quit"
)


def _build_commands() -> CommandSet:
    """The registry command family, filed as CMD-* designations. First family on the
    command spine; the legacy tick still handles everything else via fall-through."""
    cs = CommandSet()
    cs.add(
        Command(
            "registry",
            "CMD-UM10-S01-N001-001-R0",
            "list the collective",
            lambda _s, _a: registry_list(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "registry show",
            "CMD-UM10-S01-N001-002-R0",
            "show one record",
            lambda _s, arg: registry_show(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "registry find",
            "CMD-UM10-S01-N001-003-R0",
            "search the registry",
            lambda _s, arg: registry_find(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "registry type",
            "CMD-UM10-S01-N001-004-R0",
            "filter by type",
            lambda _s, arg: registry_type(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "registry status",
            "CMD-UM10-S01-N001-005-R0",
            "filter by status",
            lambda _s, arg: registry_status(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "@sg",
            "CMD-UM04-S01-N001-001-R0",
            "system-generate a filed item pattern (wizard+)",
            system_generate,
            namespace=ADMIN,
            min_rank="wizard",
        )
    )
    # --- Safety + QA spine (read-only; composes with the registry) ---
    cs.add(
        Command(
            "qa gate all",
            "CMD-UM10-S01-N001-007-R0",
            "grade every filed object for readiness",
            lambda _s, _a: render_gate_all(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "qa gate",
            "CMD-UM10-S01-N001-006-R0",
            "grade one object against the readiness checklist",
            lambda _s, arg: render_gate(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "safety review",
            "CMD-UM10-S01-N001-008-R0",
            "rate one object's risk (readiness, not compliance)",
            lambda _s, arg: render_safety(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "docs check",
            "CMD-UM10-S01-N001-009-R0",
            "sweep the key docs for gaps",
            lambda _s, _a: docs_check(),
            namespace=CORE,
        )
    )
    # --- PM control panel (read-only; computes state from registry + QualityGate) ---
    cs.add(
        Command(
            "pm status",
            "CMD-UM10-S01-N001-010-R0",
            "project status dashboard (computed, not stored)",
            lambda _s, _a: pm_status(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "pm metrics",
            "CMD-UM10-S01-N001-011-R0",
            "project metrics (objects, QA readiness, docs gaps)",
            lambda _s, _a: pm_metrics(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "law",
            "CMD-UM06-S01-N001-001-R0",
            "legal/policy awareness over tracked sources (not legal advice)",
            lambda _s, arg: law(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "truth check",
            "CMD-UM10-S01-N001-012-R0",
            "VeritasGate: check that the project's claims match reality",
            lambda _s, _a: render_truth(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "career",
            "CMD-UM10-S01-N001-013-R0",
            "Career Evidence Sign: map CodeForge work to job-ready skills, with repo proof",
            lambda _s, arg: career(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "pioneer",
            "CMD-UM10-S01-N001-014-R0",
            "Pioneer Mode: bold-but-honest engineering (doctrine, risk ladder, experiments)",
            lambda _s, arg: pioneer(arg),
            namespace=CORE,
        )
    )
    return cs


COMMANDS = _build_commands()


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
        scene.append(f"{display_name(pid)} is here.")
    return "\n".join(scene)


def _resolve_move(session: Session, direction: str) -> str:
    arrived, message = resolve_move(session.location, direction)
    if arrived != session.location:
        me = display_name(session.player_id)
        announce(session.location, f"{me} leaves {direction}.", exclude=session.player_id)
        session.location = arrived
        announce(arrived, f"{me} arrives.", exclude=session.player_id)
        return render_scene(arrived, viewer=session.player_id)
    return message


def handle_command(session: Session, signal: str) -> str:
    """The engine tick: one player command in, one response out.

    Routing is case-insensitive, but SECRETS keep their case: the
    original text is preserved and password arguments are parsed
    from it. Lowercasing a password destroys it."""
    true_signal = signal.strip()
    routed_signal = true_signal.lower()

    # The command spine is tried first; it returns None for anything it doesn't own,
    # so the legacy tick below still handles the rest (authorization before capability).
    handled = COMMANDS.dispatch(session, true_signal)
    if handled is not None:
        return handled

    if routed_signal in ("quit", "q"):
        save_character(session)
        session.alive = False
        return "The world dims. See you next spark."
    if routed_signal == "help":
        return HELP_TEXT
    if routed_signal in ("look", "l"):
        return render_scene(session.location, viewer=session.player_id)
    if routed_signal in DIRECTIONS:
        return _resolve_move(session, DIRECTIONS[routed_signal])
    if routed_signal.startswith("go "):
        word = routed_signal.removeprefix("go ").strip()
        if word in DIRECTIONS:
            return _resolve_move(session, DIRECTIONS[word])
        return "You can't go that way."
    if routed_signal.startswith("say "):
        message = routed_signal.removeprefix("say ").strip()
        if not message:
            return "Say what?"
        announce(
            session.location,
            f'{display_name(session.player_id)} says, "{message}"',
            exclude=session.player_id,
        )
        return f'You say, "{message}"'
    if routed_signal.startswith(("register ", "login ")):
        verb, _, rest = true_signal.partition(" ")
        verb = verb.lower()
        words = rest.split()
        handle = parse_handle(words[0].lower()) if words else None
        secret = words[1] if len(words) > 1 else ""  # TRUE case: secrets are never lowered
        if handle is None or len(words) != 2:
            return f"Usage: {verb} <character>@<account> <password>"
        char, account = handle
        if not NAME_RE.match(char) or not NAME_RE.match(account):
            return (
                "Character and account names are 2-16 characters: lowercase "
                "letters, digits, underscores, starting with a letter."
            )
        if char in SESSIONS:
            return f"Someone here is already {display_name(char)}."
        if verb == "register":
            problem = register_account(char, account, secret)
            if problem:
                return problem
        elif not inspect_login(char, account, secret):
            return "That character, account, and password do not align."
        old = session.player_id
        SESSIONS.pop(old, None)
        session.player_id = char
        session.account = account
        SESSIONS[char] = session
        rename_echo(old, char)
        casefile = load_character(char)
        if casefile is not None:
            announce(session.location, f"{display_name(old)} leaves.", exclude=char)
            restore_character(session, casefile)
            session.account = account
            announce(session.location, f"{display_name(char)} arrives.", exclude=char)
            return (
                f"Welcome back, {display_name(char)}@{account}.\n"
                f"{render_scene(session.location, viewer=char)}"
            )
        session.named = True
        save_character(session)
        announce(
            session.location,
            f"{display_name(old)} is now known as {display_name(char)}.",
            exclude=char,
        )
        return f"Welcome, {display_name(char)}@{account}. Your legend begins. Type JOBS."
    if routed_signal == "passwd" or routed_signal.startswith("passwd "):
        if not session.account:
            return (
                "Only account logins can change a password. "
                "Try: login <character>@<account> <password>"
            )
        words = true_signal.split()  # TRUE case: secrets are never lowered
        if len(words) != 4:
            return "Usage: passwd <old> <new> <new-again>"
        _, old, new, again = words
        if new != again:
            return "Those new passwords do not match. Nothing changed."
        problem = reforge_secret(session.account, old, new)
        if problem:
            return problem
        return "Password changed. Use it the next time you log in."
    if routed_signal.startswith("password "):
        if not session.named:
            return "Claim a name first: name <yourname>"
        return set_password(session.player_id, true_signal.split(" ", 1)[1].strip())
    if routed_signal.startswith("name "):
        words = true_signal.split(" ", 1)[1].split() if " " in true_signal else []
        wanted = words[0].lower() if words else ""
        casefile = load_character(wanted) if wanted else None
        protected = casefile is not None and has_password(casefile)
        bad_shape = len(words) > 2 or (len(words) == 2 and not protected)
        if not wanted or not NAME_RE.match(wanted) or bad_shape:
            return (
                "Names are 2-16 characters: lowercase letters, digits, underscores, "
                "starting with a letter. Try: name matrym"
            )
        if wanted in SESSIONS:
            return f"Someone here is already called {display_name(wanted)}."
        secret = words[1] if len(words) == 2 else ""
        if protected and not verify_password(wanted, secret):
            return f"That name is protected. Prove it is yours: name {wanted} <password>"
        old = session.player_id
        SESSIONS.pop(old, None)
        session.player_id = wanted
        SESSIONS[wanted] = session
        rename_echo(old, wanted)
        if casefile is not None:
            announce(session.location, f"{display_name(old)} leaves.", exclude=wanted)
            restore_character(session, casefile)
            announce(session.location, f"{display_name(wanted)} arrives.", exclude=wanted)
            nag = (
                ""
                if has_password(casefile)
                else "\n(This name has no password. Protect it: password <secret>)"
            )
            # fmt: off
            return (
                f"Welcome back, {display_name(wanted)}.{nag}\n"
                f"{render_scene(session.location, viewer=wanted)}"
            )
        # fmt: on
        session.named = True
        save_character(session)
        announce(
            session.location,
            f"{display_name(old)} is now known as {display_name(wanted)}.",
            exclude=wanted,
        )
        return f"You are now known as {display_name(wanted)}."
    if routed_signal.startswith("@"):
        return wizard_command(session, routed_signal)
    if routed_signal.startswith(("attack ", "kill ")):
        word = routed_signal.split(" ", 1)[1].strip()
        return attack(session, word)
    if routed_signal == "jobs":
        return calling_index()
    if routed_signal.startswith("job "):
        verdict = bind_calling(session, routed_signal.removeprefix("job "))
        if verdict.startswith("You take up"):
            announce(
                session.location,
                f"{display_name(session.player_id)} takes up the way "
                f"of the {JOBS[session.job]['name']}.",
                exclude=session.player_id,
            )
        return verdict
    if routed_signal == "score":
        return render_sheet(session)
    if routed_signal == "who":
        names = roster() or [session.player_id]
        return "Players online: " + ", ".join(display_name(n) for n in names)
    if routed_signal == "regs" or routed_signal.startswith("regs "):
        return regs(routed_signal[len("regs ") :] if routed_signal.startswith("regs ") else "")
    if routed_signal == "library" or routed_signal.startswith("library "):
        return library(
            routed_signal[len("library ") :] if routed_signal.startswith("library ") else ""
        )
    if routed_signal == "workshop":
        return workshop_menu()
    if routed_signal in ("catalog", "hardware", "parts"):
        return catalog_view()
    if routed_signal == "reuse" or routed_signal.startswith("reuse "):
        return reuse_search(
            routed_signal[len("reuse ") :] if routed_signal.startswith("reuse ") else ""
        )
    if routed_signal == "console":
        return console_menu()
    if routed_signal == "diagnostics":
        return diagnostics_view()
    if routed_signal == "security":
        return run_view("security")
    if routed_signal == "run" or routed_signal.startswith("run "):
        return run_view(routed_signal[len("run ") :] if routed_signal.startswith("run ") else "")
    if routed_signal == "ai" or routed_signal.startswith("ai "):
        return consult(true_signal[len("ai ") :].strip() if routed_signal.startswith("ai ") else "")
    if routed_signal == "lesson" or routed_signal.startswith("lesson "):
        rest = (
            routed_signal[len("lesson ") :].strip() if routed_signal.startswith("lesson ") else ""
        )
        if rest in ("", "list"):
            return lesson_list()
        if rest.startswith("start "):
            return lesson_start(session.player_id, rest[len("start ") :])
        return "Try: lesson list, or lesson start <subject>"
    if routed_signal == "question":
        return ask_question(session.player_id)
    if routed_signal == "answer" or routed_signal.startswith("answer "):
        arg = routed_signal[len("answer ") :] if routed_signal.startswith("answer ") else ""
        return submit_answer(session.player_id, arg)
    if routed_signal == "hint":
        return hint(session.player_id)
    if routed_signal == "progress":
        return progress(session.player_id)
    if routed_signal in ("inventory", "i", "inv"):
        return inventory_text()
    if routed_signal.startswith(("take ", "get ")):
        word = routed_signal.split(" ", 1)[1].strip()
        verdict = take(word, session.location)
        if verdict.startswith("You take"):
            announce(
                session.location,
                verdict.replace("You take", f"{display_name(session.player_id)} takes", 1),
                exclude=session.player_id,
            )
        return verdict
    if routed_signal.startswith("drop "):
        word = routed_signal.split(" ", 1)[1].strip()
        verdict = drop(word, session.location)
        if verdict.startswith("You drop"):
            announce(
                session.location,
                verdict.replace("You drop", f"{display_name(session.player_id)} drops", 1),
                exclude=session.player_id,
            )
        return verdict
    if routed_signal == "talk codex":
        if trace_npc("codex", session.location) is not None:
            return talk_to_codex()
        return "There is no one like that here."
    if routed_signal.startswith("talk "):
        word = routed_signal.split(" ", 1)[1].strip()
        return talk(word, session.location)
    if routed_signal.startswith("unlock "):
        rest = routed_signal.removeprefix("unlock ").strip()
        if " with " in rest:
            door_word, key_word = (p.strip() for p in rest.split(" with ", 1))
            return unlock(door_word, key_word, session.location)
        return "Unlock what with what? Try: unlock door with key"
    if routed_signal == "save":
        return seal_snapshot(session.location)
    if routed_signal == "load":
        session.location, msg = awaken_snapshot()
        return f"{msg}\n{render_scene(session.location, viewer=session.player_id)}"
    if routed_signal == "":
        return ""
    return "Huh? Type HELP for commands."


def game_loop() -> None:
    """Terminal driver: reads a keyboard, prints a screen. That's all."""
    session = Session(player_id="player")
    SESSIONS[session.player_id] = session
    bind_echo(session.player_id, print)
    print("Welcome. Type HELP to begin.")
    print(render_scene(session.location, viewer=session.player_id))

    try:
        while session.alive:
            response = handle_command(session, input("\n> "))
            if response:
                print(response)
    finally:
        save_character(session)
        unbind_echo(session.player_id)
        SESSIONS.pop(session.player_id, None)


if __name__ == "__main__":
    game_loop()
