"""CodeForge entry point: the power switch. All parts live in parts/.

The engine tick is handle_command(session, text) -> str: one command
in, one response out, as a plain function. game_loop is just a thin
terminal driver around it -- a socket gateway will be another.
"""

import re
from collections.abc import Callable

from parts import quest
from parts.accounts import (
    has_password,
    inspect_login,
    parse_handle,
    reforge_secret,
    set_password,
    verify_password,
)
from parts.accounts import register as register_account
from parts.aggression import menace
from parts.arc import arc
from parts.calibrate import calibrate
from parts.character_view import sheet_from_session
from parts.characters import load_character, restore_character, save_character
from parts.chat_throttle import shout
from parts.chime import chime
from parts.classroom import (
    ask_question,
    demonstrated,
    hint,
    lesson_list,
    lesson_start,
    progress,
    render_achievements,
    submit_answer,
    talk_to_codex,
)
from parts.clone_scan import clones
from parts.combat import attack
from parts.commands import ADMIN, CORE, Command, CommandSet
from parts.complexity import complexity
from parts.doors import unlock
from parts.engineer import deploy_barrier, diagnostic_scan, field_repair
from parts.equipment import equip, unequip
from parts.events import announce, announce_frame, bind_echo, rename_echo, unbind_echo
from parts.features import features
from parts.frames import SpeechFrame
from parts.harvest_lens import harvest
from parts.heralds import heralds
from parts.items import drop, inventory_text, room_items_text, take, trace_item
from parts.jobs import JOBS, bind_calling, calling_index, set_secondary
from parts.learning_record import learnings
from parts.logbook import journal
from parts.maintenance import maintenance
from parts.name_check import name_check
from parts.npcs import room_npcs_text, talk, trace_npc
from parts.quest import quest_view
from parts.ranks import wizard_command
from parts.registry import (
    registry_find,
    registry_list,
    registry_show,
    registry_status,
    registry_type,
)
from parts.relay import channel
from parts.save import awaken_snapshot, seal_snapshot
from parts.score_sheet import render_score_sheet
from parts.seed import load_splash
from parts.session import SESSIONS, Session, display_name, roster
from parts.store_index import store
from parts.telegraph import telegraph
from parts.titles import title
from parts.vitals import vitals
from parts.world import DIRECTIONS, dynamic_capability, render_room, resolve_move
from parts.world_cert import certify

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,15}$")

HELP_TEXT = (
    "Commands: look, go <direction> (or n/s/e/w/u/d), "
    "take, drop, inventory, talk <npc>, say <msg>, shout <msg>, name <yourname>, who, "
    "jobs, job <calling>, subjob <calling>, score, equip <item>, unequip <slot>, "
    "attack <target>, repair, scan <target>, deploy, calibrate, channel, journal [text], vitals, "
    "namecheck <name>, features, certify, heralds, title [text], maintenance, arc [status], "
    "telegraph, chime, harvest, store [find <query>], learnings [show <id>], "
    "complexity [threshold], clones [min-nodes], "
    "unlock <door> with <key>, regs [topic|id], library [id], law [id], "
    "registry [show|find|type|status], loop trace <part-id>, "
    "qa gate [all|<id>], safety review <id>, docs check, pm status, pm metrics, "
    "truth check, career, pioneer, evolution, chronicle, retention, coupling, inspect, functions, "
    "terminal, "
    "workshop, catalog, reuse <term>, console, run <check>, diagnostics, "
    "security, ai <prompt>, lesson list, question, answer <A-D>, hint, progress, achievements, "
    "passwd, save, load, quit"
)


# --- Lazy command seams (EXP-004) -------------------------------------------
# These verbs run at most once per player command, but their modules were paying
# import cost on EVERY engine start. Command lambdas resolve module globals at
# CALL time, so each wrapper below defers its module until the verb is first
# used. Measured on the five-journey harness (docs/performance.md); the tick's
# hot path (look/move/combat/session) keeps its eager imports.


def ask_architect(session: Session, prompt: str) -> str:
    from parts.ai_throttle import ask_architect as run

    return run(session, prompt)


def blueprint(arg: str = "") -> str:
    from parts.blueprint import blueprint as run

    return run(arg)


def career(arg: str = "", demonstrated: dict[str, int] | None = None) -> str:
    from parts.career import career as run

    return run(arg, demonstrated=demonstrated)


def console_menu() -> str:
    from parts.console import console_menu as run

    return run()


def diagnostics_view() -> str:
    from parts.console import diagnostics_view as run

    return run()


def run_view(name: str) -> str:
    from parts.console import run_view as run

    return run(name)


def after_action() -> str:
    from parts.encounter_log import render_recent

    return render_recent()


def flush_encounters(arg: str) -> str:
    """The trusted boundary, run IN the server process by an owner: aggregate the after-action
    tallies into the Chronicle. Owner-gated on the spine, so only a trusted actor reaches it -- the
    tick never does. An optional arg supplies the commit for provenance (default 'runtime')."""
    from parts.encounter_flush import flush

    return flush(arg.strip() or "runtime")


def evolution(arg: str = "") -> str:
    from parts.evolution.command import evolution as run

    return run(arg)


def chronicle(arg: str = "") -> str:
    from parts.chronicle import chronicle as run

    return run(arg)


def retention(arg: str = "") -> str:
    from parts.retention import retention as run

    return run(arg)


def coupling(arg: str = "") -> str:
    from parts.coupling import coupling as run

    return run(arg)


def forge_command(session: Session, arg: str) -> str:
    from parts.foundry import forge_command as run

    return run(session, arg)


def arch_command(session: Session, arg: str) -> str:
    from parts.foundry import arch_command as run

    return run(session, arg)


def inspect(arg: str = "") -> str:
    from parts.frameup import inspect as run

    return run(arg)


def functions(arg: str = "") -> str:
    from parts.functions import functions as run

    return run(arg)


def system_generate(session: Session, arg: str) -> str:
    from parts.generate import system_generate as run

    return run(session, arg)


def law(arg: str = "") -> str:
    from parts.law import law as run

    return run(arg)


def library(arg: str = "") -> str:
    from parts.library import library as run

    return run(arg)


def pioneer(arg: str = "") -> str:
    from parts.pioneer import pioneer as run

    return run(arg)


def pm_metrics() -> str:
    from parts.pm import pm_metrics as run

    return run()


def pm_status() -> str:
    from parts.pm import pm_status as run

    return run()


def docs_check() -> str:
    from parts.qualitygate import docs_check as run

    return run()


def render_gate(arg: str) -> str:
    from parts.qualitygate import render_gate as run

    return run(arg)


def render_gate_all() -> str:
    from parts.qualitygate import render_gate_all as run

    return run()


def render_safety(arg: str) -> str:
    from parts.qualitygate import render_safety as run

    return run(arg)


def regs(arg: str = "") -> str:
    from parts.regulations import regs as run

    return run(arg)


def terminal(arg: str = "") -> str:
    from parts.terminal import terminal as run

    return run(arg)


def render_truth() -> str:
    from parts.veritas import render_truth as run

    return run()


def catalog_view() -> str:
    from parts.workshop import catalog_view as run

    return run()


def reuse_search(term: str = "") -> str:
    from parts.workshop import reuse_search as run

    return run(term)


def workshop_menu() -> str:
    from parts.workshop import workshop_menu as run

    return run()


# --- account & identity command handlers (filed on the spine; the tick only routes) ---
# Extracted verbatim from the legacy if-ladder. The command spine preserves the argument's
# case (parts/commands.py), so a password parsed from `arg` survives -- Architecture Law 7.


def _authenticate(session: Session, verb: str, arg: str) -> str:
    """Register or log in, binding an account to this session and restoring a returning hero.

    `verb` is "register" or "login". A brand-new character is welcomed; a known casefile is
    restored to its saved scene.
    """
    words = arg.split()
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


def _register_cmd(session: Session, arg: str) -> str:
    return _authenticate(session, "register", arg)


def _login_cmd(session: Session, arg: str) -> str:
    return _authenticate(session, "login", arg)


def _passwd_cmd(session: Session, arg: str) -> str:
    """Rotate an account password: old, new, new-again (secrets keep their case)."""
    if not session.account:
        return (
            "Only account logins can change a password. Try: login <character>@<account> <password>"
        )
    words = arg.split()  # TRUE case: secrets are never lowered
    if len(words) != 3:
        return "Usage: passwd <old> <new> <new-again>"
    old, new, again = words
    if new != again:
        return "Those new passwords do not match. Nothing changed."
    problem = reforge_secret(session.account, old, new)
    if problem:
        return problem
    return "Password changed. Use it the next time you log in."


def _password_cmd(session: Session, arg: str) -> str:
    """Protect a bare (accountless) claimed name with a password."""
    if not session.named:
        return "Claim a name first: name <yourname>"
    return set_password(session.player_id, arg.strip())


def _name_cmd(session: Session, arg: str) -> str:
    """Claim or reclaim a bare name, proving a protected one with its password."""
    words = arg.split()
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


def _say_cmd(session: Session, message: str) -> str:
    """CORE `say`: broadcast a said line to the room, keeping the player's ORIGINAL case (the
    message is prose, not a label). The spine already preserves the argument's case."""
    message = message.strip()
    if not message:
        return "Say what?"
    announce_frame(
        session.location,
        SpeechFrame(speaker_id=session.player_id, words=message),
        exclude=session.player_id,
    )
    return f'You say, "{message}"'


def _build_commands() -> CommandSet:
    """The registry command family, filed as CMD-* designations. First family on the
    command spine; the legacy tick still handles everything else via fall-through."""
    cs = CommandSet()
    cs.add(
        Command(
            "registry",
            "CMD-10.001",
            "list the collective",
            lambda _s, _a: registry_list(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "registry show",
            "CMD-10.002",
            "show one record",
            lambda _s, arg: registry_show(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "registry find",
            "CMD-10.003",
            "search the registry",
            lambda _s, arg: registry_find(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "registry type",
            "CMD-10.004",
            "filter by type",
            lambda _s, arg: registry_type(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "registry status",
            "CMD-10.005",
            "filter by status",
            lambda _s, arg: registry_status(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "@sg",
            "CMD-04.001",
            "system-generate a filed item pattern (wizard+)",
            system_generate,
            namespace=ADMIN,
            min_rank="wizard",
        )
    )
    cs.add(
        Command(
            "@forge",
            "CMD-10.020",
            "the Foundry: propose a part skeleton, approve, generate into the sandbox (owner)",
            lambda s, arg: forge_command(s, arg),
            namespace=ADMIN,
            min_rank="owner",
        )
    )
    cs.add(
        Command(
            "@arch",
            "CMD-10.021",
            "step to the arch: review forged candidates, or preview <seed> a built game (owner)",
            lambda s, arg: arch_command(s, arg),
            namespace=ADMIN,
            min_rank="owner",
        )
    )
    cs.add(
        Command(
            "@flush-encounters",
            "CMD-10.024",
            "flush the after-action tallies into the Chronicle as metrics (owner)",
            lambda _s, arg: flush_encounters(arg),
            namespace=ADMIN,
            min_rank="owner",
        )
    )
    # --- Safety + QA spine (read-only; composes with the registry) ---
    cs.add(
        Command(
            "qa gate all",
            "CMD-10.007",
            "grade every filed object for readiness",
            lambda _s, _a: render_gate_all(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "qa gate",
            "CMD-10.006",
            "grade one object against the readiness checklist",
            lambda _s, arg: render_gate(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "safety review",
            "CMD-10.008",
            "rate one object's risk (readiness, not compliance)",
            lambda _s, arg: render_safety(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "docs check",
            "CMD-10.009",
            "sweep the key docs for gaps",
            lambda _s, _a: docs_check(),
            namespace=CORE,
        )
    )
    # --- PM control panel (read-only; computes state from registry + QualityGate) ---
    cs.add(
        Command(
            "pm status",
            "CMD-10.010",
            "project status dashboard (computed, not stored)",
            lambda _s, _a: pm_status(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "pm metrics",
            "CMD-10.011",
            "project metrics (objects, QA readiness, docs gaps)",
            lambda _s, _a: pm_metrics(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "law",
            "CMD-06.001",
            "legal/policy awareness over tracked sources (not legal advice)",
            lambda _s, arg: law(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "truth check",
            "CMD-10.012",
            "VeritasGate: check that the project's claims match reality",
            lambda _s, _a: render_truth(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "career",
            "CMD-10.013",
            "Career Evidence Sign: map CodeForge work to job-ready skills, with repo proof",
            lambda s, arg: career(arg, demonstrated=demonstrated(s.player_id)),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "pioneer",
            "CMD-10.014",
            "Pioneer Mode: bold-but-honest engineering (doctrine, risk ladder, experiments)",
            lambda _s, arg: pioneer(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "evolution",
            "CMD-10.022",
            "Blueprint Evolution Lab (read-only): show recorded candidate bake-off runs",
            lambda _s, arg: evolution(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "chronicle",
            "CMD-10.023",
            "The Chronicle (read-only): show the ship's filed memory, newest first",
            lambda _s, arg: chronicle(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "retention",
            "CMD-10.017",
            "Retention doctor (read-only): what the Chronicle keeps, what a hold protects",
            lambda _s, arg: retention(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "coupling",
            "CMD-10.018",
            "Engine coupling report (read-only): what a runtime cast could shed (detachment D1)",
            lambda _s, arg: coupling(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "inspect",
            "CMD-10.015",
            "Inspect the forge: an on-demand green/yellow/red frame-up of every system",
            lambda _s, arg: inspect(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "functions",
            "CMD-05.002",
            "Hardware Store functions check: run a live demo of each reusable part",
            lambda _s, arg: functions(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "terminal",
            "CMD-01.001",
            "The in-game computer: one console to run every diagnostic program",
            lambda _s, arg: terminal(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "blueprint",
            "CMD-10.016",
            "Blueprint: browse, read, or render a forged plan (idea -> spec -> HTML)",
            lambda _s, arg: blueprint(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "loop trace",
            "CMD-05.023",
            "trace a part through every manufacturing stage",
            lambda _s, arg: _loop_trace_handler(arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "loop",
            "CMD-05.024",
            "manufacturing loop commands (try: loop trace <part-id>)",
            lambda _s, _a: (
                "Usage: loop trace <part-id>\n"
                "  Trace a part through every manufacturing stage and file evidence."
            ),
            namespace=CORE,
        )
    )
    # Account & identity verbs (moved off the legacy if-ladder onto the spine).
    cs.add(
        Command(
            "register", "CMD-04.002", "create an account and enter", _register_cmd, namespace=CORE
        )
    )
    cs.add(
        Command("login", "CMD-04.003", "log into an account and enter", _login_cmd, namespace=CORE)
    )
    cs.add(
        Command("passwd", "CMD-04.004", "change your account password", _passwd_cmd, namespace=CORE)
    )
    cs.add(
        Command(
            "password",
            "CMD-04.005",
            "protect a claimed name with a password",
            _password_cmd,
            namespace=CORE,
        )
    )
    cs.add(Command("name", "CMD-04.006", "claim or reclaim a bare name", _name_cmd, namespace=CORE))
    # Read-only status/info verbs (moved off the legacy if-ladder onto the spine).
    cs.add(
        Command(
            "vitals", "CMD-04.007", "your current vitals", lambda s, _a: vitals(s), namespace=CORE
        )
    )
    cs.add(
        Command(
            "features",
            "CMD-04.008",
            "the feature flags in effect",
            lambda s, _a: features(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "certify",
            "CMD-04.009",
            "the world-readiness certificate",
            lambda s, _a: certify(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "heralds", "CMD-04.010", "the startup banners", lambda s, _a: heralds(s), namespace=CORE
        )
    )
    cs.add(
        Command(
            "maintenance",
            "CMD-04.011",
            "the maintenance status",
            lambda s, _a: maintenance(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "telegraph",
            "CMD-04.012",
            "the bursty-delivery telegraph",
            lambda s, _a: telegraph(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command("chime", "CMD-04.013", "the event chime", lambda s, _a: chime(s), namespace=CORE)
    )
    cs.add(
        Command(
            "harvest",
            "CMD-04.014",
            "harvest-lens reusable-pattern candidates",
            lambda _s, _a: harvest(),
            namespace=CORE,
        )
    )
    # Read-only query/panel verbs (stage 2 slice A, moved off the legacy if-ladder). Each is a
    # pure projection: it reads state and renders, never mutates. Aliases share one designation.
    cs.add(
        Command(
            "jobs",
            "CMD-04.015",
            "the callings on offer",
            lambda _s, _a: calling_index(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "who",
            "CMD-04.016",
            "who is online",
            lambda s, _a: (
                "Players online: " + ", ".join(display_name(n) for n in (roster() or [s.player_id]))
            ),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "workshop",
            "CMD-04.017",
            "the workshop menu",
            lambda _s, _a: workshop_menu(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "catalog",
            "CMD-04.018",
            "the Hardware Store catalog",
            lambda _s, _a: catalog_view(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "hardware",
            "CMD-04.018",
            "the Hardware Store catalog",
            lambda _s, _a: catalog_view(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "parts",
            "CMD-04.018",
            "the Hardware Store catalog",
            lambda _s, _a: catalog_view(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "console",
            "CMD-04.019",
            "the failsafe console menu",
            lambda _s, _a: console_menu(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "diagnostics",
            "CMD-04.020",
            "the diagnostics lens",
            lambda _s, _a: diagnostics_view(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "inventory",
            "CMD-04.021",
            "what you carry",
            lambda _s, _a: inventory_text(),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "i", "CMD-04.021", "what you carry", lambda _s, _a: inventory_text(), namespace=CORE
        )
    )
    cs.add(
        Command(
            "inv", "CMD-04.021", "what you carry", lambda _s, _a: inventory_text(), namespace=CORE
        )
    )
    cs.add(
        Command(
            "achievements",
            "CMD-04.022",
            "your unlocked achievements",
            lambda s, _a: render_achievements(s.player_id),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "progress",
            "CMD-04.023",
            "your classroom progress",
            lambda s, _a: progress(s.player_id),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "hint",
            "CMD-04.024",
            "a hint for the current question",
            lambda s, _a: hint(s.player_id),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "question",
            "CMD-04.025",
            "the current classroom question",
            lambda s, _a: ask_question(s.player_id),
            namespace=CORE,
        )
    )
    # Arg-forwarding reference/query verbs (stage 2 slice B). regs/library/reuse/run forwarded a
    # LOWERCASED arg on the legacy ladder; the spine preserves case, so `.lower()` here keeps the
    # old behavior exactly. `ai` keeps its ORIGINAL-case prompt (a prompt is prose, not a label).
    cs.add(
        Command(
            "regs",
            "CMD-04.026",
            "cite tracked federal guidance",
            lambda _s, arg: regs(arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "library",
            "CMD-04.027",
            "read the Guidance Library's documents",
            lambda _s, arg: library(arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "reuse",
            "CMD-04.028",
            "search the Hardware Store for a reusable part",
            lambda _s, arg: reuse_search(arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "run",
            "CMD-04.029",
            "a named readiness-check view",
            lambda _s, arg: run_view(arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "security",
            "CMD-04.030",
            "the security check view",
            lambda _s, _a: run_view("security"),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "ai",
            "CMD-04.031",
            "consult the Architect (advisory AI)",
            lambda s, arg: ask_architect(s, arg),
            namespace=CORE,
        )
    )
    # Communication verbs (stage 2 slice C). Both broadcast a TRUE-case message (prose, not a
    # label); the spine preserves the argument's case, so the old true_signal behavior is kept.
    cs.add(Command("say", "CMD-04.032", "say a line to the room", _say_cmd, namespace=CORE))
    cs.add(
        Command(
            "shout",
            "CMD-04.033",
            "shout a line to everyone",
            lambda s, arg: shout(s, arg),
            namespace=CORE,
        )
    )
    # Movement verbs (stage 2 slice D). `look` is a pure projection (no arg). The direction
    # shorthands and `go <dir>` are one action (move a room) sharing one designation: a bare
    # direction ("n") resolves itself; `go north` forwards the word. Registered via a loop over
    # DIRECTIONS to avoid twelve near-identical entries; `d=canonical` captures per-verb.
    cs.add(
        Command(
            "look",
            "CMD-04.034",
            "look at your surroundings",
            lambda s, _a: render_scene(s.location, viewer=s.player_id),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "l",
            "CMD-04.034",
            "look at your surroundings",
            lambda s, _a: render_scene(s.location, viewer=s.player_id),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "go",
            "CMD-04.035",
            "move in a direction (go <dir>, or n/s/e/w/u/d)",
            _go_cmd,
            namespace=CORE,
        )
    )
    for _verb, _canonical in DIRECTIONS.items():
        cs.add(
            Command(
                _verb,
                "CMD-04.035",
                "move in a direction",
                _mover(_canonical),
                namespace=CORE,
            )
        )
    # Console/diagnostic verbs (stage 2 slice E). Each forwards a LOWERCASED argument to a pure
    # reader (the legacy ladder routed on `routed_signal`, i.e. lowercased); the spine preserves
    # arg case, so `.lower()` here keeps the old behavior exactly. Bare verb -> empty arg -> the
    # reader's default view.
    cs.add(
        Command(
            "arc",
            "CMD-04.036",
            "the ARC assurance roll-up (arc <system>)",
            lambda _s, arg: arc(arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "store",
            "CMD-04.037",
            "the Hardware Store index (store <part-id>)",
            lambda _s, arg: store(arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "learnings",
            "CMD-04.038",
            "the filed Learning Records (learnings <id>)",
            lambda _s, arg: learnings(arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "complexity",
            "CMD-04.039",
            "the complexity lens (complexity <target>)",
            lambda _s, arg: complexity(arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "clones",
            "CMD-04.040",
            "the clone-detection lens (clones <target>)",
            lambda _s, arg: clones(arg.lower()),
            namespace=CORE,
        )
    )
    # Player action & ability verbs (stage 2 slice F). Each forwards a LOWERCASED argument to its
    # handler (the legacy ladder routed on routed_signal; the spine preserves case, so `.lower()`
    # keeps it exact). The four no-arg-in-legacy verbs (scan/equip/unequip/subjob) become bare-
    # tolerant: a bare verb now reaches its handler with an empty arg (a clear refusal), where the
    # ladder let it fall through to "Huh?". The two ability verbs take no argument.
    cs.add(
        Command(
            "quest",
            "CMD-04.041",
            "your quest log (quest <id>)",
            lambda s, arg: quest_view(s, arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "calibrate",
            "CMD-04.042",
            "calibrate an instrument (calibrate <target>)",
            lambda s, arg: calibrate(s, arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "channel",
            "CMD-04.043",
            "tune a relay channel (channel <name>)",
            lambda s, arg: channel(s, arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "namecheck",
            "CMD-04.044",
            "check whether a name is free (namecheck <name>)",
            lambda s, arg: name_check(s, arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "scan",
            "CMD-04.045",
            "run a diagnostic scan (scan <target>)",
            lambda s, arg: diagnostic_scan(s, arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "equip",
            "CMD-04.046",
            "equip an item (equip <item>)",
            lambda s, arg: equip(s, arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "unequip",
            "CMD-04.047",
            "unequip a slot (unequip <slot>)",
            lambda s, arg: unequip(s, arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "subjob",
            "CMD-04.048",
            "take a secondary calling (subjob <job>)",
            lambda s, arg: set_secondary(s, arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "secondary",
            "CMD-04.048",
            "take a secondary calling (secondary <job>)",
            lambda s, arg: set_secondary(s, arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "answer",
            "CMD-04.049",
            "answer the current classroom question (answer <choice>)",
            lambda s, arg: submit_answer(s.player_id, arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "repair",
            "CMD-04.050",
            "the Engineer's field repair",
            lambda s, _a: field_repair(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "field repair",
            "CMD-04.050",
            "the Engineer's field repair",
            lambda s, _a: field_repair(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "deploy",
            "CMD-04.051",
            "the Engineer's barrier deployment",
            lambda s, _a: deploy_barrier(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "deploy barrier",
            "CMD-04.051",
            "the Engineer's barrier deployment",
            lambda s, _a: deploy_barrier(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "barrier",
            "CMD-04.051",
            "the Engineer's barrier deployment",
            lambda s, _a: deploy_barrier(s),
            namespace=CORE,
        )
    )
    # World-interaction verbs (stage 2 slice G). These mutate the world and broadcast to the room;
    # their logic lives in named handlers above. attack/kill is a plain arg-forwarder. All were
    # startswith-only on the ladder, so a bare verb is now a clear refusal instead of "Huh?".
    cs.add(
        Command(
            "attack",
            "CMD-04.052",
            "strike a target (attack <foe>)",
            lambda s, arg: attack(s, arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "kill",
            "CMD-04.052",
            "strike a target (kill <foe>)",
            lambda s, arg: attack(s, arg.lower()),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "job",
            "CMD-04.053",
            "take up a calling (job <name>)",
            _job_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "take",
            "CMD-04.054",
            "pick up an item (take <item>)",
            _take_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "get",
            "CMD-04.054",
            "pick up an item (get <item>)",
            _take_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "drop",
            "CMD-04.055",
            "drop a carried item (drop <item>)",
            _drop_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "talk",
            "CMD-04.056",
            "speak with someone (talk <name>)",
            _talk_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "unlock",
            "CMD-04.057",
            "unlock a door with a key (unlock <door> with <key>)",
            _unlock_cmd,
            namespace=CORE,
        )
    )
    # Progression, classroom, and lifecycle verbs (stage 2 slice H, the finale). journal and title
    # carry PROSE, so they keep the argument's original case (like say/ai); the rest take a label or
    # no argument. This empties the legacy if-ladder of real verbs: only the reserved router cases
    # (the '@' admin catch-all, the empty-input guard, and the "Huh?" fall-through) remain below.
    cs.add(
        Command(
            "journal",
            "CMD-04.058",
            "write or read your journal (journal <entry>)",
            lambda s, arg: journal(s, arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "title",
            "CMD-04.059",
            "set your displayed title (title <text>)",
            lambda s, arg: title(s, arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "score",
            "CMD-04.060",
            "your character sheet (score <mode>)",
            _score_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "lesson",
            "CMD-04.061",
            "the classroom menu (lesson list | lesson start <subject>)",
            _lesson_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "save",
            "CMD-04.062",
            "seal a snapshot of the world",
            lambda s, _a: seal_snapshot(s.location),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "load",
            "CMD-04.063",
            "restore the world snapshot",
            _load_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "quit",
            "CMD-04.064",
            "save and leave the world",
            _quit_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "q",
            "CMD-04.064",
            "save and leave the world",
            _quit_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "help",
            "CMD-04.065",
            "the command help text",
            lambda _s, _a: HELP_TEXT,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "encounters",
            "CMD-04.066",
            "the after-action log: recent combat encounters and their tallies",
            lambda _s, _a: after_action(),
            namespace=CORE,
        )
    )
    return cs


def _loop_trace_handler(arg: str) -> str:
    """Handle the `loop trace <part-id>` command."""
    part_id = arg.strip()
    if not part_id:
        return "Usage: loop trace <part-id>\n  Example: loop trace workflow-engine"
    from parts.loop import render_trace, trace

    return render_trace(trace(part_id))


# A room may declare (in its seed) a live capability to surface on look. The engine renders the
# declared capability; it never hard-codes a room label (the world stays data).
_DYNAMIC_PANELS = {"arc": lambda: arc("status")}


def render_scene(location: str, viewer: str = "") -> str:
    """The full projection of a room: place, things, people, players."""
    scene = [render_room(location)]
    panel = _DYNAMIC_PANELS.get(dynamic_capability(location))
    if panel is not None:
        scene.append(panel())
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
        scene = render_scene(arrived, viewer=session.player_id)
        hook = quest.on_event(session, "enter", arrived)  # entering a room may advance the arc
        return f"{scene}\n\n{hook}" if hook else scene
    return message


def _go_cmd(session: Session, arg: str) -> str:
    """`go <direction>`: move one room, or a clear refusal for a non-direction (or bare `go`).

    A direction is a label, so it routes case-insensitively (the legacy ladder lowered it too)."""
    word = arg.strip().lower()
    if word in DIRECTIONS:
        return _resolve_move(session, DIRECTIONS[word])
    return "You can't go that way."


def _mover(direction: str) -> Callable[[Session, str], str]:
    """Bind one canonical direction into a bare-verb move handler (e.g. `n` -> north)."""
    return lambda session, _arg: _resolve_move(session, direction)


# --- world-interaction handlers (stage 2 slice G) ----------------------------
# These verbs mutate the world and broadcast to the room, so they are named handlers (not lambdas):
# the announce/quest-hook/parsing logic is more than one expression. Each lowercases its argument
# (a label), matching the legacy ladder's routed_signal behavior; the spine preserves case.


def _job_cmd(session: Session, arg: str) -> str:
    """Take up a calling; announce it to the room when it is newly bound."""
    verdict = bind_calling(session, arg.lower())
    if verdict.startswith("You take up"):
        announce(
            session.location,
            f"{display_name(session.player_id)} takes up the way "
            f"of the {JOBS[session.job]['name']}.",
            exclude=session.player_id,
        )
    return verdict


def _take_cmd(session: Session, arg: str) -> str:
    """Pick up an item; announce it, and let a pickup advance the arc."""
    word = arg.lower()
    picked = trace_item(word, f"room:{session.location}")  # label, captured before it moves
    verdict = take(word, session.location)
    if verdict.startswith("You take"):
        announce(
            session.location,
            verdict.replace("You take", f"{display_name(session.player_id)} takes", 1),
            exclude=session.player_id,
        )
        if picked:
            hook = quest.on_event(session, "take", picked)  # a pickup may advance the arc
            if hook:
                verdict = f"{verdict}\n{hook}"
    return verdict


def _drop_cmd(session: Session, arg: str) -> str:
    """Drop a carried item; announce it to the room."""
    word = arg.lower()
    verdict = drop(word, session.location)
    if verdict.startswith("You drop"):
        announce(
            session.location,
            verdict.replace("You drop", f"{display_name(session.player_id)} drops", 1),
            exclude=session.player_id,
        )
    return verdict


def _talk_cmd(session: Session, arg: str) -> str:
    """Speak with an NPC. `talk codex` reaches Professor Codex (the classroom guide)."""
    word = arg.lower()
    if word == "codex":
        if trace_npc("codex", session.location) is not None:
            return talk_to_codex()
        return "There is no one like that here."
    return talk(word, session.location)


def _unlock_cmd(session: Session, arg: str) -> str:
    """Unlock a door with a key: `unlock <door> with <key>`."""
    rest = arg.lower()
    if " with " in rest:
        door_word, key_word = (p.strip() for p in rest.split(" with ", 1))
        return unlock(door_word, key_word, session.location)
    return "Unlock what with what? Try: unlock door with key"


# --- progression, classroom, and lifecycle handlers (stage 2 slice H) --------


def _score_cmd(session: Session, arg: str) -> str:
    """Render the character sheet in a chosen display mode (a label, so lowercased)."""
    sheet = sheet_from_session(session)
    if sheet is None:
        return "You have no calling yet. Type JOBS to see the paths."
    mode = arg.strip().lower() or "standard"
    try:
        return render_score_sheet(sheet, mode)
    except ValueError as err:
        return str(err)


def _lesson_cmd(session: Session, arg: str) -> str:
    """The classroom menu: `lesson list` or `lesson start <subject>`."""
    rest = arg.strip().lower()
    if rest in ("", "list"):
        return lesson_list()
    if rest.startswith("start "):
        return lesson_start(session.player_id, rest[len("start ") :])
    return "Try: lesson list, or lesson start <subject>"


def _load_cmd(session: Session, _arg: str) -> str:
    """Restore the world snapshot and show the arrival scene."""
    session.location, msg = awaken_snapshot()
    return f"{msg}\n{render_scene(session.location, viewer=session.player_id)}"


def _quit_cmd(session: Session, _arg: str) -> str:
    """Save and leave: the driver's loop ends when the session is no longer alive."""
    save_character(session)
    session.alive = False
    return "The world dims. See you next spark."


# Built after the movement + world + lifecycle handlers above (referenced at build time).
COMMANDS = _build_commands()


def _route(session: Session, true_signal: str, routed_signal: str) -> str:
    """Resolve one player command to its response, before the world takes its beat."""
    # The command spine is tried first; it returns None for anything it doesn't own,
    # so the legacy tick below still handles the rest (authorization before capability).
    handled = COMMANDS.dispatch(session, true_signal)
    if handled is not None:
        return handled

    if routed_signal.startswith("@"):
        return wizard_command(session, routed_signal, COMMANDS.admin_verbs())
    if routed_signal == "":
        return ""
    return "Huh? Type HELP for commands."


def handle_command(session: Session, signal: str) -> str:
    """The engine tick: one player command in, one response out.

    Routing is case-insensitive, but SECRETS keep their case: the
    original text is preserved and password arguments are parsed
    from it. Lowercasing a password destroys it.

    After the player's command resolves, the world takes its beat: any aggressive
    NPC sharing the room strikes (parts.aggression.menace). The player's command is
    the only clock the world has -- no background thread, the tick stays the one door."""
    true_signal = signal.strip()
    routed_signal = true_signal.lower()

    response = _route(session, true_signal, routed_signal)
    return f"{response}{menace(session)}"


def render_opening(session: Session) -> str:
    """The solo player's first screen: the world's own splash, then the room they wake in.

    The gateways greet a connection with the seed's splash before login; solo play skipped
    it and showed a generic line. Now every door onto the world opens with the world's face."""
    splash = load_splash()
    scene = render_scene(session.location, viewer=session.player_id)
    return f"{splash}\n\n{scene}\n\nType HELP for commands."


def game_loop() -> None:
    """Terminal driver: reads a keyboard, prints a screen. That's all."""
    session = Session(player_id="player")
    SESSIONS[session.player_id] = session
    bind_echo(session.player_id, print)
    print(render_opening(session))

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
