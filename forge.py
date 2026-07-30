"""CodeForge entry point: the power switch. All parts live in parts/.

The engine tick is handle_command(session, text) -> str: one command
in, one response out, as a plain function. game_loop is just a thin
terminal driver around it -- a socket gateway will be another.
"""

import re
from collections.abc import Callable

from parts.addie import addie
from parts.arc import arc
from parts.calibrate import calibrate
from parts.chat_throttle import shout
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
from parts.commands import ADMIN, CORE, Command, CommandSet
from parts.complexity import complexity
from parts.features import features
from parts.harvest_lens import harvest
from parts.heralds import heralds
from parts.learning_record import learnings
from parts.logbook import journal
from parts.maintenance import maintenance
from parts.name_check import name_check
from parts.plugins import PluginLoad, load_plugins
from parts.registry import (
    registry_find,
    registry_list,
    registry_show,
    registry_status,
    registry_type,
)
from parts.relay import channel
from parts.save import awaken_snapshot, seal_snapshot
from parts.shelf.hourglass import WORLD_SANDS
from parts.store_index import store
from parts.telegraph import telegraph
from parts.titles import title
from parts.vitals import vitals
from parts.world import (
    allocate,
    artifact,
    creator_workshop,
    gather,
    maintenance_mode,
    presence,
    quest,
    scheduler,
)
from parts.world import auction as auction_mod
from parts.world import bank as bank_mod
from parts.world import chat as chat_mod
from parts.world import feats as feats_mod
from parts.world import friends as friends_mod
from parts.world import guild as guild_mod
from parts.world import inns as inns_mod
from parts.world import mail as mail_mod
from parts.world import trade as trade_mod
from parts.world import travel as travel_net
from parts.world.abilities import render_abilities, use_ability
from parts.world.accounts import (
    has_password,
    inspect_login,
    parse_handle,
    reforge_secret,
    set_password,
    verify_password,
)
from parts.world.accounts import register as register_account
from parts.world.afflictions import tick_afflictions
from parts.world.aggression import menace
from parts.world.character_view import sheet_from_session
from parts.world.characters import load_character, restore_character, save_character
from parts.world.chime import chime
from parts.world.climate import tick_climate, weather_view
from parts.world.coinage import purse
from parts.world.combat import attack, examine_foe, tick_burns
from parts.world.condition import render_condition
from parts.world.consumables import quaff
from parts.world.crafting import craft
from parts.world.doors import reclose, unlock
from parts.world.engineer import deploy_barrier, diagnostic_scan, field_repair
from parts.world.equipment import equip, unequip
from parts.world.events import (
    announce,
    announce_frame,
    bind_echo,
    broadcast,
    rename_echo,
    rename_gmcp,
    unbind_echo,
)
from parts.world.factions import render_factions
from parts.world.frames import SpeechFrame
from parts.world.items import (
    carrier,
    drop,
    inventory_text,
    prototype_of,
    read_item,
    room_items_text,
    take,
    trace_item,
)
from parts.world.jobs import JOBS, bind_calling, calling_index, set_secondary
from parts.world.npcs import ask, room_npcs_text, talk, trace_npc
from parts.world.orders import swear_order
from parts.world.party import (
    disband as party_disband,
)
from parts.world.party import (
    invite as party_invite,
)
from parts.world.party import (
    join as party_join,
)
from parts.world.party import (
    leave as party_leave,
)
from parts.world.party import (
    party_say,
    render_party,
)
from parts.world.professions import render_professions
from parts.world.quest import contracts_view, quest_view
from parts.world.ranks import wizard_command
from parts.world.reputation import render_standing
from parts.world.roaming import roam
from parts.world.score_sheet import render_score_sheet
from parts.world.seed import load_splash
from parts.world.session import SESSIONS, Session, display_name, roster
from parts.world.shop import buy, render_shop, sell
from parts.world.world import (
    DIRECTIONS,
    WAYSTONES,
    WORLD,
    dynamic_capability,
    render_room,
    resolve_move,
)
from parts.world.zone_story import region_view
from parts.world.zones import area_line, tick_zones
from parts.world_cert import certify

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,15}$")

HELP_TEXT = (
    "Commands: look, go <direction> (or n/s/e/w/u/d), "
    "take, drop, inventory, talk <npc>, ask <npc> about <topic>, say <msg>, name <yourname>, who, "
    "jobs, job <calling>, subjob <calling>, join <order>, wallet, quaff <item>, contracts, region, "
    "weather, factions, professions, standing, condition, "
    "party [invite|join|leave|disband], psay <msg>, "
    "trade <player> [accept|add <item>|coins <n>|confirm|cancel], "
    "guild [found <name>|invite|accept|promote|leave|disband], gsay <msg>, "
    "mail [send <player> <msg>|read <n>|delete <n>], friends [add|remove <player>], "
    "chat <message>, rest, bank [deposit|withdraw <item>], auction [list <item> <price>|buy <#>], "
    "route <room>, score, "
    "equip <item>, unequip <slot>, "
    "attack <target>, skills, use <ability> [on <foe>], repair, scan <target>, deploy, calibrate, "
    "channel, journal [text], vitals, "
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
    from parts.shelf.console import console_menu as run

    return run()


def diagnostics_view() -> str:
    from parts.shelf.console import diagnostics_view as run

    return run()


def run_view(name: str) -> str:
    from parts.shelf.console import run_view as run

    return run(name)


def after_action() -> str:
    from parts.world.encounter_log import render_recent

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
    rename_gmcp(old, char)
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
    rename_gmcp(old, wanted)
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


# The result of the plugin discovery pass at spine-build time (None until _build_commands runs).
# A `plugins` diagnostic reads it so a rejected plugin is visible, never silently dropped.
PLUGIN_LOAD: PluginLoad | None = None


def _script_command(session: Session, arg: str) -> str:
    """Owner-only sandboxed Lua console: run a snippet, show its emit() output + return value.

    The safety boundary is parts.scripting.LuaSandbox (no os/io/require; loops bounded), so even the
    owner's console cannot reach the host. When the [lua] extra is absent, it says so cleanly."""
    from parts.scripting import LuaSandbox, ScriptError, scripting_available

    code = arg.strip()
    if not code:
        return "Usage: @script <lua>. Runs sandboxed (no os/io/require; loops are bounded)."
    if not scripting_available():
        return "Lua scripting is not installed. Enable it with: pip install '.[lua]'"
    try:
        result = LuaSandbox().run(code)
    except ScriptError as exc:
        return f"[script error] {exc}"
    lines = list(result.output)
    if result.value is not None:
        lines.append(f"=> {result.value}")
    return "\n".join(lines) if lines else "(no output)"


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
    cs.add(
        Command(
            "@script",
            "CMD-10.025",
            "run a sandboxed Lua snippet (owner; no os/io/require, bounded loops)",
            _script_command,
            namespace=ADMIN,
            min_rank="owner",
        )
    )
    cs.add(
        Command(
            "@maintenance",
            "CMD-10.026",
            "close/open the forge to non-staff: @maintenance [on <reason>|off] (owner)",
            _maintenance_cmd,
            namespace=ADMIN,
            min_rank="owner",
        )
    )
    cs.add(
        Command(
            "@audit",
            "CMD-10.027",
            "the tamper-evident admin/economy log: @audit [verify] (owner)",
            _audit_cmd,
            namespace=ADMIN,
            min_rank="owner",
        )
    )
    cs.add(
        Command(
            "@metrics",
            "CMD-10.031",
            "a live-ops snapshot from storage: population + economy health (owner)",
            _metrics_cmd,
            namespace=ADMIN,
            min_rank="owner",
        )
    )
    cs.add(
        Command(
            "@ban",
            "CMD-10.028",
            "bar a character from the world: @ban <player> <reason> (wizard+)",
            _ban_cmd,
            namespace=ADMIN,
            min_rank="wizard",
        )
    )
    cs.add(
        Command(
            "@unban",
            "CMD-10.029",
            "lift a ban: @unban <player> (wizard+)",
            _unban_cmd,
            namespace=ADMIN,
            min_rank="wizard",
        )
    )
    cs.add(
        Command(
            "@bans",
            "CMD-10.030",
            "the roster of banned characters (wizard+)",
            _bans_cmd,
            namespace=ADMIN,
            min_rank="wizard",
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
            "survey",
            "CMD-04.081",
            "the Planning Table's world survey (owner, in the Creator's Workshop)",
            lambda s, _a: creator_workshop.plan_survey(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "activity",
            "CMD-04.082",
            "the Statistics Wall's live-play view (owner, in the Creator's Workshop)",
            lambda s, _a: creator_workshop.wall_activity(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "create",
            "CMD-04.083",
            "the Workshop create tool: stage a new npc or item (owner, in the Creator's Workshop)",
            lambda s, a: creator_workshop.create(s, a),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "preview",
            "CMD-04.084",
            "preview staged Creator Workshop changes (owner)",
            lambda s, _a: creator_workshop.preview_changes(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "publish",
            "CMD-04.085",
            "publish staged changes to the live world (owner, at the Publishing Portal)",
            lambda s, _a: creator_workshop.publish_changes(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "rollback",
            "CMD-04.086",
            "discard staged Creator Workshop changes (owner, at the Publishing Portal)",
            lambda s, _a: creator_workshop.rollback_changes(s),
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
            lambda s, _a: inventory_text(carrier(s.player_id)),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "i",
            "CMD-04.021",
            "what you carry",
            lambda s, _a: inventory_text(carrier(s.player_id)),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "inv",
            "CMD-04.021",
            "what you carry",
            lambda s, _a: inventory_text(carrier(s.player_id)),
            namespace=CORE,
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
            "examine",
            "CMD-04.078",
            "size up a creature: its HP and elemental nature (examine <target>)",
            lambda s, a: examine_foe(s, a),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "go",
            "CMD-04.035",
            "move a way (a dir n/s/e/w, ne/nw/se/sw, u/d; or a named exit: go gate)",
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
            "addie",
            "CMD-04.077",
            "the ADDIE continuous-improvement loop (addie status)",
            lambda _s, arg: addie(arg.lower()),
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
            "use",
            "CMD-04.067",
            "channel a combat ability (use <ability> [on <foe>])",
            lambda s, arg: use_ability(s, arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "skills",
            "CMD-04.068",
            "list the abilities your calling can wield",
            lambda s, _arg: render_abilities(s),
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
            "join",
            "CMD-04.069",
            "swear to an Order (join <order>)",
            lambda s, arg: swear_order(s, arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "wallet",
            "CMD-04.070",
            "check your purse",
            lambda s, _a: (
                "Your purse is empty." if not s.coins else f"Your purse holds {purse(s.coins)}."
            ),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "contracts",
            "CMD-04.076",
            "the bounty board (generated hunt-contracts)",
            lambda s, _a: contracts_view(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "region",
            "CMD-04.092",
            "the story of the zone you stand in (its tale, depths, and work)",
            lambda s, _a: region_view(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "weather",
            "CMD-04.093",
            "the season and sky over the world right now",
            lambda s, _a: weather_view(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "factions",
            "CMD-04.094",
            "the standing between the Orders: who is allied, who is rival",
            lambda s, _a: render_factions(getattr(s, "order", "") or ""),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "quaff",
            "CMD-04.074",
            "drink a consumable (quaff <item>)",
            lambda s, arg: quaff(s, arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "craft",
            "CMD-04.079",
            "forge gathered materials into goods (craft <recipe>)",
            lambda s, arg: craft(s, arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "professions",
            "CMD-04.095",
            "your maker's trades and their levels (gathering and crafting skills)",
            lambda s, _a: render_professions(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "standing",
            "CMD-04.096",
            "your reputation and tier with each Order (Hostile .. Revered)",
            lambda s, _a: render_standing(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "condition",
            "CMD-04.098",
            "how you are right now: vital pools, what ails you, your sworn standing",
            lambda s, _a: render_condition(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "party",
            "CMD-04.099",
            "form a fellowship: party [invite|join <player>|leave|disband]",
            _party_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "psay",
            "CMD-04.100",
            "speak on your party's private channel (psay <message>)",
            lambda s, arg: party_say(s.player_id, arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "trade",
            "CMD-04.101",
            "trade goods and coin with a hero (trade <player>, then add/coins/confirm/cancel)",
            _trade_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "guild",
            "CMD-04.102",
            "a persisted guild: guild [found <name>|invite <player>|accept|promote|leave|disband]",
            _guild_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "gsay",
            "CMD-04.103",
            "speak on your guild's channel (gsay <message>)",
            lambda s, arg: guild_mod.guild_say(s, arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "mail",
            "CMD-04.104",
            "async letters: mail | mail send <player> <msg> | mail read <n> | mail delete <n>",
            _mail_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "friend",
            "CMD-04.105",
            "your friends list: friend | friend add <player> | friend remove <player>",
            _friend_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "friends",
            "CMD-04.106",
            "show your friends list and who is online (alias of `friend`)",
            _friend_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "chat",
            "CMD-04.107",
            "speak on the world channel, heard by every hero online (chat <message>)",
            lambda s, arg: chat_mod.world_say(s, arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "rest",
            "CMD-04.108",
            "rest at an inn's hearth to restore HP/MP to full",
            lambda s, _a: inns_mod.rest(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "bank",
            "CMD-04.109",
            "your personal vault: bank | bank deposit <item> | bank withdraw <n>",
            _bank_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "auction",
            "CMD-04.110",
            "the marketplace: auction | auction list <item> <price> | auction buy <#>",
            _auction_cmd,
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "shop",
            "CMD-04.071",
            "list a merchant's wares",
            lambda s, _a: render_shop(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "buy",
            "CMD-04.072",
            "buy an item (buy <item>)",
            lambda s, arg: buy(s, arg),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "sell",
            "CMD-04.073",
            "sell a carried item (sell <item>)",
            lambda s, arg: sell(s, arg),
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
            "read",
            "CMD-04.080",
            "read an item's lore (read <item>)",
            lambda s, a: read_item(a, s.location, carrier(s.player_id)),
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
            "ask",
            "CMD-04.075",
            "ask about a topic (ask <npc> about <topic>)",
            _ask_cmd,
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
            "allocate",
            "CMD-04.087",
            "spend attribute points (allocate <stat> [n])",
            lambda s, a: allocate.allocate(s, a),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "signet",
            "CMD-04.088",
            "the Maker's Signet: the Creator Interface, borne anywhere (owner)",
            lambda s, a: artifact.signet(s, a),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "gather",
            "CMD-04.089",
            "harvest this room's crafting-material node",
            lambda s, _a: gather.gather(s),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "travel",
            "CMD-04.090",
            "the Waystone network: pay to cross the world (travel [where])",
            lambda s, a: travel_net.travel(s, a, WAYSTONES),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "route",
            "CMD-04.097",
            "the shortest on-foot path to a room, as directions (route <room>)",
            lambda s, a: travel_net.route(s, a),
            namespace=CORE,
        )
    )
    cs.add(
        Command(
            "feats",
            "CMD-04.091",
            "your deed ledger: the feats you have earned",
            lambda s, _a: feats_mod.feats(s),
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
    # Third-party command plugins register LAST (so collision checks see every built-in verb). The
    # plugins/ dir is absent by default, so this is a no-op until an operator adds one. The
    # kept for a diagnostic; a rejected plugin is recorded, never silently dropped.
    global PLUGIN_LOAD
    PLUGIN_LOAD = load_plugins(cs)
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
    area = area_line(location)  # the room's area banner, or '' if it belongs to no zone
    if area:
        scene.append(area)
    panel = _DYNAMIC_PANELS.get(dynamic_capability(location))
    if panel is not None:
        scene.append(panel())
    extra = room_items_text(location)
    if extra:
        scene.append(extra)
    node = gather.gather_hint(location)
    if node:
        scene.append(node)
    company = room_npcs_text(location)
    if company:
        scene.append(company)
    # Local players in the room, plus any the shared roster places here from another process
    # (Phase 5). The union dedupes; presence is empty in a single process, so this stays the
    # local list until a gateway feeds cross-process locations.
    local = {pid for pid, s in SESSIONS.items() if s.location == location}
    others = (local | presence.in_room(location)) - {viewer}
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


def _cross_workshop_barrier(session: Session, word: str) -> str | None:
    """The Creator's Door: if `word` names the concealed door out of this room, resolve the barrier;
    None if it names no door, so ordinary movement handles the word.

    Only the authenticated Seed Owner crosses; everyone else (including a player who guesses the
    door) meets the exact barrier refusal. The crossing is UNOBSERVABLE -- no leave/arrive is
    announced to the Library -- so players can never see the owner slip through
    (parts.world.workshop)."""
    dest = creator_workshop.door_destination(session.location, word)
    if dest is None:
        return None
    if not creator_workshop.is_seed_owner(session):
        return creator_workshop.barrier_refusal()
    session.location = dest  # silent crossing: the barrier lets no one witness it
    return render_scene(dest, viewer=session.player_id)


def _go_cmd(session: Session, arg: str) -> str:
    """`go <way>`: move one room, or a clear refusal for a non-way (or bare `go`).

    A way is a compass direction (`go north`, `go ne`) OR the noun a threshold is named for
    (`go gate`, `go market`, `go in`). Directions canonicalize through DIRECTIONS; a noun that is
    not a direction is resolved against the current room's own exits. Routes case-insensitively
    (the legacy ladder lowered it too)."""
    word = arg.strip().lower()
    crossed = _cross_workshop_barrier(session, word)
    if crossed is not None:
        return crossed
    if word in DIRECTIONS:
        return _resolve_move(session, DIRECTIONS[word])
    if word and word in WORLD[session.location]["exits"]:
        return _resolve_move(session, word)
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
    verdict = take(word, session.location, carrier(session.player_id))
    if verdict.startswith("You take"):
        announce(
            session.location,
            verdict.replace("You take", f"{display_name(session.player_id)} takes", 1),
            exclude=session.player_id,
        )
        if picked:
            # match the quest by prototype: picking up a cloned instance of a quest item still
            # fires its on_take (a seed item's prototype is its own label, so this is unchanged).
            hook = quest.on_event(
                session, "take", prototype_of(picked)
            )  # a pickup may advance the arc
            if hook:
                verdict = f"{verdict}\n{hook}"
    return verdict


def _drop_cmd(session: Session, arg: str) -> str:
    """Drop a carried item; announce it to the room."""
    word = arg.lower()
    verdict = drop(word, session.location, carrier(session.player_id))
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


def _ask_cmd(session: Session, arg: str) -> str:
    """`ask <npc> about <topic>` (or bare `ask <npc>` to list topics): topic-based conversation."""
    who, _, topic = arg.lower().partition(" about ")
    return ask(who.strip(), topic.strip(), session.location)


def _party_cmd(session: Session, arg: str) -> str:
    """The `party` verb: form and command a fellowship. The spine preserves argument case, so a
    player name arrives as typed and is lowered to its label inside `parts.world.party`. Bare
    `party` shows the roster; `party invite <player>`, `party join <player>`, `party leave`,
    `party disband`. Party chat is the separate `psay` verb (which keeps its message case)."""
    me = session.player_id
    parts_ = arg.split(maxsplit=1)
    sub = parts_[0].lower() if parts_ else ""
    rest = parts_[1] if len(parts_) > 1 else ""
    if sub == "":
        return render_party(me)
    if sub == "invite":
        return party_invite(me, rest)
    if sub == "join":
        return party_join(me, rest)
    if sub == "leave":
        return party_leave(me)
    if sub == "disband":
        return party_disband(me)
    return "Party: party, party invite <player>, party join <player>, party leave, party disband."


def _mail_cmd(session: Session, arg: str) -> str:
    """The `mail` verb: async letters. Bare `mail` shows the inbox; `mail send <player>
    <message>`, `mail read <n>`, `mail delete <n>`. The spine preserves the letter's case."""
    parts_ = arg.split(maxsplit=1)
    sub = parts_[0].lower() if parts_ else ""
    rest = parts_[1] if len(parts_) > 1 else ""
    if sub == "":
        return mail_mod.render_inbox(session)
    if sub == "send":
        return mail_mod.send(session, rest)
    if sub == "read":
        return mail_mod.read_mail(session, rest)
    if sub == "delete":
        return mail_mod.delete_mail(session, rest)
    if sub == "gift":
        return mail_mod.gift(session, rest)
    if sub == "claim":
        return mail_mod.claim(session, rest)
    return (
        "Mail: mail | mail send <player> <message> | mail read <n> | mail delete <n> "
        "| mail gift <player> <item> | mail claim <n>."
    )


def _ban_cmd(session: Session, arg: str) -> str:
    """`@ban <player> <reason>`: bar a character from the world (wizard+), audited. If online they
    drop on their next command. A ban outranks maintenance and even a wizard's rank."""
    from parts.world import audit, bans

    parts_ = arg.split(maxsplit=1)
    name = parts_[0].strip().lower() if parts_ else ""
    reason = parts_[1].strip() if len(parts_) > 1 else "no reason given"
    if not name:
        return "Ban whom? (@ban <player> <reason>)"
    bans.ban(name, reason, session.player_id)
    audit.record(session.player_id, "ban", f"{name}: {reason}")
    target = SESSIONS.get(name)
    if target is not None:
        target.alive = False  # drop them on their next command
    return f"{display_name(name)} is banned: {reason}"


def _unban_cmd(session: Session, arg: str) -> str:
    """`@unban <player>`: lift a ban (wizard+), audited."""
    from parts.world import audit, bans

    name = arg.strip().lower()
    if not name:
        return "Unban whom? (@unban <player>)"
    if not bans.unban(name):
        return f"{display_name(name)} is not banned."
    audit.record(session.player_id, "unban", name)
    return f"{display_name(name)} is no longer banned."


def _bans_cmd(_session: Session, _arg: str) -> str:
    """`@bans`: the moderation roster of banned characters (wizard+)."""
    from parts.world import bans

    rows = bans.all_bans()
    if not rows:
        return "No one is banned."
    lines = ["Banned characters:"]
    for name, reason, moderator in rows:
        lines.append(f"  {display_name(name)}: {reason} (by {display_name(moderator)})")
    return "\n".join(lines)


def _metrics_cmd(_session: Session, _arg: str) -> str:
    """`@metrics`: a live-ops snapshot from storage (population + economy health) (owner)."""
    from parts.world import metrics

    return metrics.render()


def _audit_cmd(_session: Session, arg: str) -> str:
    """`@audit [verify]`: the tamper-evident admin/economy log (owner). Bare shows recent entries;
    `@audit verify` checks the hash chain end to end."""
    from parts.world import audit

    if arg.strip().lower() == "verify":
        return "Audit log: chain intact." if audit.verify() else "Audit log: CHAIN BROKEN."
    entries = audit.tail(20)
    if not entries:
        return "The audit log is empty."
    lines = ["Audit log (recent):"]
    for entry in entries:
        detail = f" - {entry['detail']}" if entry.get("detail") else ""
        lines.append(f"  [{entry['ts']}] {entry['actor']}: {entry['action']}{detail}")
    return "\n".join(lines)


def _maintenance_cmd(session: Session, arg: str) -> str:
    """`@maintenance [on <reason>|off]`: close or open the forge to non-staff (owner). Bare shows
    the status. On/off broadcast to everyone online so players in the world can wrap up."""
    parts_ = arg.split(maxsplit=1)
    sub = parts_[0].lower() if parts_ else ""
    rest = parts_[1] if len(parts_) > 1 else ""
    if sub == "on":
        active = maintenance_mode.enable(rest)
        broadcast(f"\n** CodeForge is entering maintenance: {active}. Staff only from here. **")
        return f"Maintenance ON: {active}. Non-staff logins are now refused."
    if sub == "off":
        maintenance_mode.disable()
        broadcast("\n** Maintenance is over. CodeForge is open again. **")
        return "Maintenance OFF. The forge is open to everyone."
    state = f"ON ({maintenance_mode.reason()})" if maintenance_mode.is_on() else "OFF"
    return f"Maintenance is {state}. Usage: @maintenance on <reason> | @maintenance off"


def _auction_cmd(session: Session, arg: str) -> str:
    """The `auction` verb: the marketplace. Bare `auction` browses; `auction list <item> <price>`
    escrows an item for sale, `auction buy <#>` buys one. The spine preserves the item word."""
    parts_ = arg.split(maxsplit=1)
    sub = parts_[0].lower() if parts_ else ""
    rest = parts_[1] if len(parts_) > 1 else ""
    if sub in ("", "browse"):
        return auction_mod.browse(session)
    if sub == "list":
        return auction_mod.list_item(session, rest)
    if sub == "buy":
        return auction_mod.buy(session, rest)
    return "Auction: auction | auction list <item> <price> | auction buy <#>."


def _bank_cmd(session: Session, arg: str) -> str:
    """The `bank` verb: your personal vault. Bare `bank` lists it; `bank deposit <item>` puts a
    carried item away, `bank withdraw <n|item>` takes one back. The spine keeps the item word."""
    parts_ = arg.split(maxsplit=1)
    sub = parts_[0].lower() if parts_ else ""
    rest = parts_[1] if len(parts_) > 1 else ""
    if sub in ("", "list"):
        return bank_mod.render(session)
    if sub == "deposit":
        return bank_mod.deposit(session, rest)
    if sub == "withdraw":
        return bank_mod.withdraw(session, rest)
    return "Bank: bank | bank deposit <item> | bank withdraw <n>."


def _friend_cmd(session: Session, arg: str) -> str:
    """The `friend` verb: your personal friends list. Bare `friend`/`friends` shows the roster with
    who is online; `friend add <player>`, `friend remove <player>`."""
    parts_ = arg.split(maxsplit=1)
    sub = parts_[0].lower() if parts_ else ""
    rest = parts_[1] if len(parts_) > 1 else ""
    if sub in ("", "list"):
        return friends_mod.render(session)
    if sub == "add":
        return friends_mod.add(session, rest)
    if sub in ("remove", "rem", "del"):
        return friends_mod.remove(session, rest)
    return "Friends: friend | friend add <player> | friend remove <player>."


def _guild_cmd(session: Session, arg: str) -> str:
    """The `guild` verb: a persisted player organization. `guild found <name>`, `guild invite
    <player>`, `guild accept`, `guild promote <player>`, `guild leave`, `guild disband`; bare
    `guild` shows the roster. Guild chat is the separate `gsay` verb."""
    parts_ = arg.split(maxsplit=1)
    sub = parts_[0].lower() if parts_ else ""
    rest = parts_[1] if len(parts_) > 1 else ""
    if sub == "":
        return guild_mod.render_guild(session)
    if sub == "found":
        return guild_mod.found(session, rest)
    if sub == "invite":
        return guild_mod.invite(session, rest)
    if sub == "accept":
        return guild_mod.accept(session)
    if sub == "promote":
        return guild_mod.promote(session, rest)
    if sub == "leave":
        return guild_mod.leave(session)
    if sub == "disband":
        return guild_mod.disband(session)
    if sub == "bank":
        return guild_mod.bank_balance(session)
    if sub == "deposit":
        return guild_mod.bank_deposit(session, rest)
    if sub == "withdraw":
        return guild_mod.bank_withdraw(session, rest)
    if sub == "vault":  # the item vault: `guild vault [deposit <item>|withdraw <n>]`
        v_parts = rest.split(maxsplit=1)
        v_sub = v_parts[0].lower() if v_parts else ""
        v_rest = v_parts[1] if len(v_parts) > 1 else ""
        if v_sub == "deposit":
            return guild_mod.vault_deposit(session, v_rest)
        if v_sub == "withdraw":
            return guild_mod.vault_withdraw(session, v_rest)
        return guild_mod.vault_render(session)
    return (
        "Guild: guild [found <name>|invite <player>|accept|promote <player>|leave|disband"
        "|bank|deposit <n>|withdraw <n>|vault [deposit <item>|withdraw <n>]]."
    )


def _trade_cmd(session: Session, arg: str) -> str:
    """The `trade` verb: a safe atomic swap with a co-located hero. The spine preserves argument
    case, so a player name / item word arrives as typed; names lower to their label downstream.
    `trade <player>` proposes; `trade accept`; `trade add <item>`; `trade coins <n>`;
    `trade confirm`; `trade cancel`; bare `trade` shows the open trade."""
    me = session.player_id
    parts_ = arg.split(maxsplit=1)
    sub = parts_[0].lower() if parts_ else ""
    rest = parts_[1] if len(parts_) > 1 else ""
    if sub == "":
        return trade_mod.render(me)
    if sub == "accept":
        return trade_mod.accept(me)
    if sub == "add":
        return trade_mod.add_item(me, rest)
    if sub == "coins":
        return trade_mod.offer_coins(me, rest)
    if sub == "confirm":
        return trade_mod.confirm(me)
    if sub == "cancel":
        return trade_mod.cancel(me)
    return trade_mod.propose(me, arg)  # `trade <player>`: the whole arg is the target name


def _unlock_cmd(session: Session, arg: str) -> str:
    """Unlock a door with a key: `unlock <door> with <key>`."""
    rest = arg.lower()
    if " with " in rest:
        door_word, key_word = (p.strip() for p in rest.split(" with ", 1))
        # the actor context a door's optional `requires` condition is evaluated against
        actor = {"level": session.level, "rank": session.rank}
        return unlock(door_word, key_word, session.location, actor, carrier(session.player_id))
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


def _did_you_mean(session: Session, routed_signal: str) -> str:
    """A gentle nudge on an unknown command: the nearest reachable spine verb, but only on a genuine
    near-miss (edit distance <= 2), so a real typo gets help and pure nonsense just gets 'Huh?'.

    Uses the textmatch shelf part (parts.shelf.textmatch), C-accelerated when built (ADR-0010)."""
    from parts.shelf.textmatch import closest

    typed = routed_signal.split(" ", 1)[0]
    if not typed:
        return ""
    verbs = {c.verb.split(" ", 1)[0].lower() for c in COMMANDS.available_to(session)}
    hit = closest(typed, verbs, max_distance=2)
    return f" Did you mean `{hit}`?" if hit else ""


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
    # Noun exits ("nouns as rooms"): a lone unrecognized word that names a threshold out of this
    # room walks the player through it -- `market`, `gate`, `tavern`, `in`, `out`. Compass words
    # ("ne", "northwest") are already movement verbs; this catches the named thresholds a seed
    # keys by their destination. Real verbs win (the spine ran first), so an exit never shadows one.
    if " " not in routed_signal:
        # The concealed Creator's Door is named, never listed (parts.world.workshop): try it before
        # the visible exits, so a bare `door` in the Grand Library meets the barrier or crosses it.
        crossed = _cross_workshop_barrier(session, routed_signal)
        if crossed is not None:
            return crossed
        if routed_signal in WORLD[session.location]["exits"]:
            return _resolve_move(session, routed_signal)
    return "Huh? Type HELP for commands." + _did_you_mean(session, routed_signal)


def handle_command(session: Session, signal: str) -> str:
    """The engine tick: one player command in, one response out.

    Routing is case-insensitive, but SECRETS keep their case: the
    original text is preserved and password arguments are parsed
    from it. Lowercasing a password destroys it.

    After the player's command resolves, the world takes its beat: any aggressive
    NPC sharing the room strikes (parts.world.aggression.menace) and every area advances its
    reset clock (parts.world.zones.tick_zones). The player's command is the only clock the world
    has -- no background thread, the tick stays the one door."""
    true_signal = signal.strip()
    routed_signal = true_signal.lower()

    response = _route(session, true_signal, routed_signal)
    beat = (
        f"{tick_burns(session)}{tick_afflictions(session)}{menace(session)}{roam(session)}"
        f"{tick_zones(session)}{gather.tick_gather(session)}{tick_climate(session)}"
        f"{scheduler.tick(session)}{_sands_beat(session)}"
    )
    return f"{response}{beat}"


def _sands_beat(session: Session) -> str:
    """Advance the shared world timer one beat and apply any deferred effects that came due.

    The player's command is the only clock: this drains parts.shelf.hourglass.WORLD_SANDS as before
    menace and tick_zones ride the beat, with no background thread. Returns any line the acting
    player should see because they are in the affected room (else '')."""
    lines: list[str] = []
    for event in WORLD_SANDS.advance():
        if isinstance(event, tuple) and len(event) == 2 and event[0] == "reclose":
            closed = reclose(event[1])
            if closed is not None:
                room, name = closed
                slam = f"{name} slams shut."
                announce(room, slam, exclude=session.player_id)
                if session.location == room:
                    lines.append(f"\n{slam}")
    return "".join(lines)


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
