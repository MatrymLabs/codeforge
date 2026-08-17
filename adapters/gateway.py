"""CARD: gateway -- a line-based TCP server sharing one world.

Each connection gets its own Session; every command runs through the
same engine tick under one lock -- the classic MUD 'one command at a
time' model. Plain lines in, plain text out: connect with nc or any
telnet client.

Security: plaintext by default (the compatibility transport for a home
LAN). Set CODEFORGE_TLS_CERT + CODEFORGE_TLS_KEY to serve over TLS for an
internet-facing deployment; the message layer is identical behind either.
Account auth (salted pbkdf2) gates entry at the login front desk.

Beyond the game, this server also serves the engineering-workspace surface over GMCP, additively
and orthogonally to the game path: once an OWNER logs in, their Native-Seed client is pushed the
creation `Form.Schema` plus the reference Seed's read-only workspace (its `Architecture.Map` and
`Blueprint.List`, real engine state, so the Master Client's panels light up from the running
server), an inbound `Seed.Create` / `Form.Submit` frame mints a real Seed (owner-gated, mirroring
the in-MUD `workspace` verb) and pushes its `workspace_packages` back, and a `Workspace.Request`
frame serves this instance's live `Deploy.Status` (version, uptime, connections, TLS), the
reference Seed's `Deploy.Manifest` (for a requested tier), and its `Research.Findings` when a
research manifest is mounted (`SEEDLAB_RESEARCH`).
Seedlab is lazy-imported inside the handlers (off the game load path) and its mutations serialized
under `SEEDLAB_LOCK`; nothing here touches the tick, `_push_state`, or the front desk.
"""

import contextlib
import os
import re
import socket
import socketserver
import ssl
import sys
import threading
import time
from typing import TYPE_CHECKING, Protocol

import structlog

from forge import handle_command, render_scene
from kernel.gmcp import (
    GMCP_OPT,
    enables_gmcp,
    friends_report,
    gmcp_frame,
    guild_report,
    items_report,
    mail_report,
    party_report,
    quest_report,
    read_gmcp_package,
    resists_report,
    room_report,
    seed_hello,
    skills_report,
    target_report,
    vitals_report,
)
from kernel.shelf.bulkhead import Bulkhead, BulkheadFull
from kernel.shelf.telnet_codec import IAC, SE, WILL, WONT, strip_iac
from kernel.world import bans, guild, maintenance_mode, party, presence, trade, tutorial
from kernel.world.accounts import password_fixable
from kernel.world.characters import save_all, save_character
from kernel.world.events import SHUTDOWN, bind_echo, bind_gmcp, unbind_echo, unbind_gmcp
from kernel.world.ranks import has_rank
from kernel.world.seed import SEED_NAME, load_splash
from kernel.world.session import SESSIONS, Session
from kernel.world.socket_bus import maybe_wire_broker

if TYPE_CHECKING:
    from kernel.seedlab.kernel import BlueprintKernel

TICK_LOCK = threading.Lock()
# Serializes seedlab (engineering-workspace) mutations across connection threads. The seedlab Kernel
# and its file store carry no lock of their own, so two connections minting/mutating Seeds could
# lost-update; this guards the additive workspace wire without touching the game tick's TICK_LOCK.
SEEDLAB_LOCK = threading.Lock()
_counter_lock = threading.Lock()
_counter = 0

# Structured server logs: one queryable event per lifecycle moment (start, connect, disconnect,
# stop), not prose. structlog only (no FastAPI on this hot path); configured for JSON in serve().
_LOG = structlog.get_logger("gateway")


def _configure_logging() -> None:
    """Emit gateway events as structured JSON lines. Idempotent; called once from serve() so tests
    (which drive the server directly, never serve()) keep structlog's default readable config."""
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        cache_logger_on_first_use=True,
    )


# --- the doorman's post: seats, silence, and the turnaway ledger ---
AUTOSAVE_EVERY = 25  # a named hero is autosaved every this many of their own commands, so a crash
# loses at most that many commands of progress (not a whole session). The tick lock is already held
# when it fires, so the save is consistent with the command that triggered it.
IDLE_TIMEOUT = 300.0  # seconds of silence before a connection is dropped
MAX_CONNECTIONS = 128  # concurrent sockets; thread-per-connection has a ceiling
MAX_LINE_BYTES = (
    4096  # cap a single client line: a newline-less flood must not be an unbounded read
)
MAX_LOGIN_FAILS = 5  # failed logins per client address within the window...
LOGIN_FAIL_WINDOW = 300.0  # ...before that address is refused for a cooldown

# Concurrent-session cap, as the Hardware Store's bulkhead part: admit up to MAX_CONNECTIONS
# handlers, reject the overflow fast (a full-forge message) so a connection flood cannot exhaust the
# thread-per-connection pool. This replaces a hand-rolled locked counter with the shelf part it was.
_SEATS = Bulkhead(MAX_CONNECTIONS)
_turnaway_ledger: dict[str, list[float]] = {}
_ledger_lock = threading.Lock()

# When this process started serving, for the instance's self-reported uptime (Deploy.Status). Set at
# import (~process start); monotonic so a wall-clock change never makes uptime jump or go negative.
_STARTED_AT = time.monotonic()


def _server_version() -> str:
    """The running engine's version, from the installed distribution (unknown when run un-packaged,
    e.g. a source checkout with no metadata) -- an honest self-report, never a hardcoded guess."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _dist_version

    try:
        return _dist_version("codeforge")
    except PackageNotFoundError:
        return "unknown"


def _next_player_id() -> str:
    global _counter
    with _counter_lock:
        _counter += 1
        return f"player{_counter}"


def _log_turnaway(ip: str) -> None:
    """Remember one failed login from an address. Also sweeps the whole
    table: addresses whose failures have all aged out are DELETED, so the
    dict is bounded by currently-failing addresses, not by every address
    ever seen."""
    now = time.monotonic()
    with _ledger_lock:
        for addr in list(_turnaway_ledger):
            live = [t for t in _turnaway_ledger[addr] if now - t < LOGIN_FAIL_WINDOW]
            if live:
                _turnaway_ledger[addr] = live
            else:
                del _turnaway_ledger[addr]
        _turnaway_ledger.setdefault(ip, []).append(now)


def _gate_is_barred(ip: str) -> bool:
    """True once an address has too many recent failures -- online
    brute-force defense that survives reconnects (the per-connection
    3-strikes does not). Read-only: never creates table entries, so
    connect-only traffic cannot grow the dict."""
    now = time.monotonic()
    with _ledger_lock:
        recent = [t for t in _turnaway_ledger.get(ip, []) if now - t < LOGIN_FAIL_WINDOW]
        return len(recent) >= MAX_LOGIN_FAILS


def _forgive_address(ip: str) -> None:
    """Clear an address's failure tally after a PROVEN-good login. A brute-forcer never reaches
    this (they never authenticate), so it can't reset the bar -- it only spares a legitimate user
    who fumbled a few times (a typo, a taken name) and then logged in successfully."""
    with _ledger_lock:
        _turnaway_ledger.pop(ip, None)


# How many passwords a NEW visitor may try before the whole registration is
# counted a failed attempt. A rejected password (too short, or the wrong one for
# an existing account) is a fixable typo, not a login attack, so it re-prompts in
# place instead of dropping to the top and burning a door attempt.
_REGISTER_TRIES = 3
_AETHRYN_CREATION_TRIES = 3


# --- telnet option negotiation (RFC 854/857): the password blackout ---
# The Telnet wire codec (command bytes, IAC stripping) lives in kernel.shelf.telnet_codec; the
# gate is a consumer of it. `_strip_telnet` is a local alias for the codec's `strip_iac` so callers
# (and the test twin) that reference it stay stable.
ECHO_OPT = 1
_ECHO_OFF = bytes([IAC, WILL, ECHO_OPT])  # "I will echo" -> client stops echoing
_ECHO_ON = bytes([IAC, WONT, ECHO_OPT])  # "I won't echo" -> client resumes

# GMCP (option 201): offer it on connect. A capable client answers DO/WILL GMCP and then gets
# structured state frames (Char.Vitals, Room.Info) alongside the text; a raw nc never answers, so
# it stays a plain-text client and sees no binary. Framing + reply-reader live in kernel/gmcp.py.
_WILL_GMCP = bytes([IAC, WILL, GMCP_OPT])

_strip_telnet = strip_iac


# Strip terminal control characters (ANSI/VT escapes and other C0/C1
# controls) but keep tab, newline, carriage return. Player-supplied text
# -- chat, especially -- must not carry escape sequences that could hijack
# or spoof another player's terminal.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _sanitize(text: str) -> str:
    """Remove terminal control characters from text bound for a client."""
    return _CONTROL_RE.sub("", text)


def _tls_context() -> ssl.SSLContext | None:
    """The server's TLS context if a cert + key are configured, else None (plaintext, LAN mode).

    Set CODEFORGE_TLS_CERT and CODEFORGE_TLS_KEY to PEM paths to serve over TLS -- the encrypted
    transport an internet-facing deployment needs. Unset (or either missing) means the historical
    plaintext transport, so a home-LAN server keeps working unchanged. The message layer is the same
    behind either; only the socket is wrapped."""
    cert = os.environ.get("CODEFORGE_TLS_CERT", "").strip()
    key = os.environ.get("CODEFORGE_TLS_KEY", "").strip()
    if not cert or not key:
        return None
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2  # refuse legacy TLS 1.0/1.1 outright
    context.load_cert_chain(certfile=cert, keyfile=key)  # fails loud on a bad/missing cert
    return context


class ForgeGateServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        # Wrap every accepted socket in TLS when configured; None keeps the plaintext transport.
        self._tls = _tls_context()

    def get_request(self) -> tuple[socket.socket, object]:
        """Accept a connection, TLS-wrapping it if the server is running with a cert. A handshake
        failure (a plaintext client on a TLS port) raises OSError, which the accept loop logs and
        skips -- one bad client never stops the server."""
        sock, addr = super().get_request()
        if self._tls is not None:
            sock = self._tls.wrap_socket(sock, server_side=True)
        return sock, addr


class _ByteReader(Protocol):
    """Just enough of a binary stream for `_read_message`: read exactly `size` bytes (the buffered
    `rfile` and an in-memory `BytesIO` both satisfy it, so the reader is testable off a socket)."""

    def read(self, size: int, /) -> bytes: ...


def _read_message(reader: _ByteReader, max_bytes: int) -> tuple[bytes, bool]:
    """Read one client MESSAGE: a newline-terminated line, OR a complete standalone GMCP
    subnegotiation frame (`IAC SB GMCP ... IAC SE`), whichever completes first. Returns
    `(raw_bytes, is_frame)`.

    This lets an out-of-band GMCP frame -- which carries NO trailing newline -- be processed the
    instant it arrives, instead of waiting for the next line the user types (the engineering-
    workspace wire's `Form.Submit` is exactly such a bare frame). A line still comes back whole at
    its newline, with any IAC negotiation the client glued before the text left intact for the
    caller's codec (exactly as `readline` delivered it). Only a GMCP frame that stands alone (its
    `IAC SE` reached before any newline) returns early as a frame; a bare non-GMCP subnegotiation is
    read through as before, and EOF or the size cap returns whatever was read, as a line."""
    buf = bytearray()
    while len(buf) < max_bytes:
        chunk = reader.read(1)
        if not chunk:
            return bytes(buf), False  # EOF: hand back whatever we have (a line, maybe empty)
        buf += chunk
        if chunk == b"\n":
            return bytes(buf), False  # a complete line
        # A GMCP subnegotiation closes on IAC SE. If what we have is now a complete GMCP frame with
        # no newline, it is a standalone out-of-band package -- return it now, not at the next line.
        if (
            chunk == bytes([SE])
            and len(buf) >= 2
            and buf[-2] == IAC
            and read_gmcp_package(bytes(buf)) is not None
        ):
            return bytes(buf), True
    return bytes(buf), False  # hit the cap: treat as a line (the tick parses what it can)


class _GateHandler(socketserver.StreamRequestHandler):
    timeout = IDLE_TIMEOUT  # StreamRequestHandler applies this to the socket

    def setup(self) -> None:
        super().setup()
        # Disable Nagle. Without this, each one-line reply waits ~40ms for a delayed
        # ACK before flushing -- a fixed per-command stall on every client. MUD
        # traffic is tiny interactive lines: exactly what TCP_NODELAY is for.
        with contextlib.suppress(OSError):  # setsockopt is platform-dependent
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # Offer GMCP and start disabled: only a client that answers positively flips it on.
        # _last_* memoize the last frame sent so we push only what actually changed.
        self._gmcp_enabled = False
        self._seed_announced = (
            False  # Native Seed handshake: Seed.Hello is sent once on GMCP enable
        )
        # The authenticated session, set once the front desk lets a player in. None while at the
        # login desk, which GATES the additive engineering-workspace wire: no inbound Seed.Create /
        # Form.Submit is dispatched until a real account is behind the connection.
        self._session: Session | None = None
        self._last_vitals: dict[str, int] | None = None
        self._last_room: dict[str, object] | None = None
        self._last_target: dict[str, object] = {}  # {} means "no foe"; clears the client's tracker
        self._last_quest: dict[str, str] = {}  # {} means "no active quest"
        self._last_items: dict[str, dict[str, object]] = {}  # {} = nothing worn; clears the panel
        self._last_skills: list[dict[str, object]] = []  # [] = no calling; the wieldable kit
        self._last_resists: dict[str, str] = {}  # {} = resists nothing unusual; the defensive grid
        self._last_party: dict[str, object] = {}  # {} = solo; clears the client's party panel
        self._last_guild: dict[str, str] = {}  # {} = guildless; clears the client's guild panel
        self._last_mail: dict[str, int] = {}  # {} = empty inbox; clears the mail badge
        self._last_friends: dict[str, object] = {}  # {} = no friends; clears the friends line
        self._cmds_since_save = 0  # autosave cadence counter for this connection's hero
        with contextlib.suppress(OSError):
            self.wfile.write(_WILL_GMCP)

    def _note_gmcp(self, raw: bytes) -> None:
        """Read a client's GMCP negotiation reply out of raw input and record its choice. When a
        client first enables GMCP, announce the loaded Seed with a `Seed.Hello` frame (once), so a
        Native-Seed client can negotiate entry (ADR-0002); a plain-text client never gets here."""
        verdict = enables_gmcp(raw)
        if verdict is not None:
            self._gmcp_enabled = verdict
        if self._gmcp_enabled and not self._seed_announced:
            self._seed_announced = True
            self._send_gmcp("Seed.Hello", seed_hello(SEED_NAME))
        # Additive engineering-workspace wire: a logged-in owner's client can create a Seed and get
        # its workspace pushed back, all over GMCP. Only after the front desk (self._session set),
        # and orthogonal to the game path -- a non-workspace frame is ignored here.
        if self._session is not None:
            self._handle_workspace_gmcp(raw)

    def _handle_workspace_gmcp(self, raw: bytes) -> None:
        """Dispatch an inbound engineering-workspace GMCP package on an authenticated connection:
        `Seed.Create` / `Form.Submit` create a Seed and push its workspace; `Workspace.Request`
        serves the reference Seed's `Deploy.Manifest` for a requested tier (a read, no mutation).
        Authorization before capability (architecture law 5): the whole surface is OWNER-gated,
        mirroring the in-MUD `workspace` verb's `min_rank='owner'` -- a non-owner's create request
        gets an honest `ok:false` verdict, and a non-owner's read request is silently ignored (there
        is nothing to serve). Any other inbound package (or none) is ignored, so the game path is
        never touched.

        The read loop (`_read_message`) recognizes a standalone GMCP subnegotiation, so a bare
        out-of-band frame (no trailing newline) is dispatched here the instant it arrives, not only
        at the next line boundary."""
        package = read_gmcp_package(raw)
        if package is None:
            return  # the common case: a normal command line carries no GMCP data frame
        from kernel.seedlab.workspace_gmcp import (
            FORM_SUBMIT_PACKAGE,
            SEED_CREATE_PACKAGE,
            SEED_CREATED_PACKAGE,
            WORKSPACE_REQUEST_PACKAGE,
            create_from_form_submit,
            create_from_request,
            seed_created,
            workspace_packages,
        )

        name, payload = package
        create_packages = (SEED_CREATE_PACKAGE, FORM_SUBMIT_PACKAGE)
        if name not in (*create_packages, WORKSPACE_REQUEST_PACKAGE):
            return
        session = self._session
        assert session is not None  # dispatch is only reached once the front desk set it
        if not has_rank(session, "owner"):
            if (
                name in create_packages
            ):  # a create is refused with a verdict; a read is just ignored
                self._send_gmcp(
                    SEED_CREATED_PACKAGE,
                    seed_created("", False, reason="creating a workspace requires owner rank"),
                )
            return
        if name == WORKSPACE_REQUEST_PACKAGE:
            self._serve_requested_workspace(payload)
            return
        owner = session.account or session.player_id
        with SEEDLAB_LOCK:
            kernel = self._workspace_kernel()
            if name == SEED_CREATE_PACKAGE:
                verdict = create_from_request(kernel, payload, owner=owner)
            else:
                from kernel.seedlab.form import load_definition

                verdict = create_from_form_submit(kernel, load_definition(), payload, owner=owner)
            self._send_gmcp(SEED_CREATED_PACKAGE, verdict)
            if verdict.get("ok"):
                record = kernel.get(str(verdict.get("id", "")))
                for pkg, data in workspace_packages(record):
                    self._send_gmcp(pkg, data)

    def _serve_requested_workspace(self, payload: object) -> None:
        """Serve the requestable read panels for the reference Seed on a `Workspace.Request`: its
        `Deploy.Manifest` (for the tier the client picked, default `prototype`) and, WHEN a research
        manifest is mounted, its `Research.Findings`. Owner-gated by the caller. Both are honest
        about absence: an unknown tier serves no manifest, and an unmounted or unreadable research
        source serves no findings (the panel stays empty rather than showing invented research).

        The research source is a MOUNT, like the Federal Guidance Library: `SEEDLAB_RESEARCH` (or,
        by default, `$SEEDLAB_HOME/research.json`) points at a JSON list of finding records. The
        engine never vendors research; a deployment mounts it, and an absent mount is a legible
        empty panel, not a fabricated one."""
        from pathlib import Path

        from kernel.seed_package import BlueprintPackageError, compile_manifest
        from kernel.seedlab.kernel import BlueprintKernelError
        from kernel.seedlab.workspace_gmcp import (
            DEPLOY_MANIFEST_PACKAGE,
            DEPLOY_STATUS_PACKAGE,
            RESEARCH_FINDINGS_PACKAGE,
            deploy_manifest,
            deploy_status,
            load_research_findings,
            research_findings,
        )

        # The running instance's own live status: real facts the node knows about itself, no cloud.
        self._send_gmcp(
            DEPLOY_STATUS_PACKAGE,
            deploy_status(
                version=_server_version(),
                seed=SEED_NAME,
                uptime_seconds=time.monotonic() - _STARTED_AT,
                connections=_SEATS.active,
                max_connections=_SEATS.limit,
                tls=bool(os.environ.get("CODEFORGE_TLS_CERT", "").strip()),
            ),
        )
        tier_id = "prototype"
        if isinstance(payload, dict):
            requested = payload.get("tier")
            if isinstance(requested, str) and requested.strip():
                tier_id = requested.strip()
        try:
            manifest = compile_manifest(SEED_NAME, tier_id)
        except BlueprintPackageError as exc:
            _LOG.warning("workspace_deploy_unavailable", tier=tier_id, error=str(exc))
        else:
            self._send_gmcp(DEPLOY_MANIFEST_PACKAGE, deploy_manifest(manifest, seed=SEED_NAME))

        research_path = Path(
            os.environ.get("SEEDLAB_RESEARCH")
            or Path(os.environ.get("SEEDLAB_HOME", ".seedlab")) / "research.json"
        )
        try:
            findings = load_research_findings(research_path)
        except (OSError, ValueError, BlueprintKernelError):
            return  # no research mounted (or unreadable): the panel stays honestly empty
        self._send_gmcp(RESEARCH_FINDINGS_PACKAGE, research_findings(findings, seed=SEED_NAME))

    def _workspace_kernel(self) -> "BlueprintKernel":
        """A Kernel over the file-backed seedlab store at `$SEEDLAB_HOME/seeds` (default
        `.seedlab/seeds`), the same store the in-MUD `workspace` verb uses. Read at call time so a
        test can point `SEEDLAB_HOME` at a tmp dir; lazy-imported so seedlab stays off the gateway's
        load path (the game path never imports it)."""
        from pathlib import Path

        from kernel.seedlab.kernel import BlueprintKernel, FileSeedStore

        root = Path(os.environ.get("SEEDLAB_HOME", ".seedlab")) / "seeds"
        return BlueprintKernel(FileSeedStore(root))

    def _push_workspace_form(self) -> None:
        """Push the engineering creation Form (`Form.Schema`) to a logged-in owner's Native-Seed
        client, so its Seed Creation Wizard can render. Owner-gated by the caller; additive and
        optional (a game client ignores the package). A missing catalog is logged, never a crash."""
        from kernel.seedlab.form import FormError, load_definition
        from kernel.seedlab.workspace_gmcp import FORM_SCHEMA_PACKAGE, form_schema

        try:
            definition = load_definition()
        except FormError as exc:
            _LOG.warning("workspace_form_unavailable", error=str(exc))
            return
        self._send_gmcp(FORM_SCHEMA_PACKAGE, form_schema(definition, seed=SEED_NAME))

    def _push_reference_workspace(self) -> None:
        """Push the reference engineering Seed's READ-ONLY workspace to a logged-in owner's client,
        so the Master Client's read panels light up from the RUNNING server (not just a fixture):
        its own module map (`Architecture.Map`, the classification registry) and its filed
        Blueprints (`Blueprint.List`). Real engine state, parameter-free, owner-gated by the caller;
        additive and optional (a game client ignores them). A missing or broken source is logged and
        skipped, never a crash. `Deploy.Manifest` (needs a chosen tier) and `Research.Findings` (a
        per-Seed manifest) are request-driven, not auto-pushed."""
        from kernel.blueprint import load_all
        from kernel.seedlab.kernel import BlueprintKernelError
        from kernel.seedlab.workspace_gmcp import (
            ARCHITECTURE_MAP_PACKAGE,
            BLUEPRINT_LIST_PACKAGE,
            architecture_map,
            blueprint_list,
            load_module_designations,
        )

        try:
            modules = load_module_designations()
        except (OSError, ValueError, BlueprintKernelError) as exc:
            _LOG.warning("workspace_architecture_unavailable", error=str(exc))
        else:
            self._send_gmcp(ARCHITECTURE_MAP_PACKAGE, architecture_map(modules, seed=SEED_NAME))
        try:
            blueprints = load_all()
        except (OSError, ValueError) as exc:
            _LOG.warning("workspace_blueprints_unavailable", error=str(exc))
        else:
            self._send_gmcp(BLUEPRINT_LIST_PACKAGE, blueprint_list(blueprints, seed=SEED_NAME))

    def _send_gmcp(self, package: str, data: object) -> None:
        """Push one GMCP frame, only to a client that enabled GMCP (never to a plain-text nc)."""
        if not self._gmcp_enabled:
            return
        with contextlib.suppress(OSError):
            self.wfile.write(gmcp_frame(package, data))

    def _push_state(self, session: Session) -> None:
        """Emit Room.Info and Char.Vitals when they change (and once on entry). No-op until the
        client enables GMCP, so the reports are not even computed for a plain-text session."""
        if not self._gmcp_enabled:
            return
        room = room_report(session)
        if room != self._last_room:
            self._send_gmcp("Room.Info", room)
            self._last_room = room
        vitals = vitals_report(session)
        if vitals is not None and vitals != self._last_vitals:
            self._send_gmcp("Char.Vitals", vitals)
            self._last_vitals = vitals
        # Char.Target / Char.Quest: an empty {} clears the client's tracker when a fight ends or an
        # arc completes, so a change from "something" to "nothing" is pushed exactly once.
        target = target_report(session) or {}
        if target != self._last_target:
            self._send_gmcp("Char.Target", target)
            self._last_target = target
        quest = quest_report(session) or {}
        if quest != self._last_quest:
            self._send_gmcp("Char.Quest", quest)
            self._last_quest = quest
        items = items_report(session)
        if items != self._last_items:
            self._send_gmcp("Char.Items", items)
            self._last_items = items
        # Char.Skills: the wieldable kit, so a client's co-pilot can recommend a specific move for a
        # foe's weakness. Changes only when the calling/subjob changes, so it is pushed rarely.
        skills = skills_report(session)
        if skills != self._last_skills:
            self._send_gmcp("Char.Skills", skills)
            self._last_skills = skills
        # Char.Resists: the player's defensive grid, so a client can warn when a foe's element hits
        # a weakness. Like Skills, it changes only on a calling switch, so it is pushed rarely.
        resists = resists_report(session)
        if resists != self._last_resists:
            self._send_gmcp("Char.Resists", resists)
            self._last_resists = resists
        # Char.Party / Char.Guild: the player's social memberships, so a client can render a party
        # roster and guild badge. An empty {} clears the panel when they leave (like Char.Target).
        party = party_report(session) or {}
        if party != self._last_party:
            self._send_gmcp("Char.Party", party)
            self._last_party = party
        guild = guild_report(session) or {}
        if guild != self._last_guild:
            self._send_gmcp("Char.Guild", guild)
            self._last_guild = guild
        # Char.Mail / Char.Friends: the unread-letter count and who of your friends is online, so a
        # client can badge mail and show the fellowship. Empty {} clears each when it empties.
        mail = mail_report(session) or {}
        if mail != self._last_mail:
            self._send_gmcp("Char.Mail", mail)
            self._last_mail = mail
        friends = friends_report(session) or {}
        if friends != self._last_friends:
            self._send_gmcp("Char.Friends", friends)
            self._last_friends = friends

    def _autosave(self, session: Session) -> None:
        """Persist a named hero every AUTOSAVE_EVERY commands. Called under the tick lock just after
        the command that may have changed their state, so the save is consistent and cheap."""
        if not session.named:
            return
        self._cmds_since_save += 1
        if self._cmds_since_save >= AUTOSAVE_EVERY:
            save_character(session)
            self._cmds_since_save = 0

    def _send(self, text: str) -> None:
        self.wfile.write((_sanitize(text) + "\r\n").encode("utf-8"))

    def _ask(self, prompt: str) -> str | None:
        """One question at the front desk. None means they walked away
        (hung up or idled out)."""
        self.wfile.write((prompt + " ").encode("utf-8"))
        try:
            line = self.rfile.readline(MAX_LINE_BYTES)
        except OSError:
            return None  # idle timeout or broken pipe
        if not line:
            return None
        self._note_gmcp(line)  # the client's GMCP reply often rides the first input
        return _strip_telnet(line).decode("utf-8", errors="ignore").strip()

    def _ask_secret(self, prompt: str) -> str | None:
        """A question whose answer must not appear on the client's
        screen: negotiate echo OFF, read, negotiate echo ON. The
        telnet-native getpass. (nc ignores negotiation -- raw pipes
        keep their echo; Mudlet and telnet go dark.)"""
        self.wfile.write((prompt + " ").encode("utf-8") + _ECHO_OFF)
        try:
            line = self.rfile.readline(MAX_LINE_BYTES)
        except OSError:
            return None  # idle timeout or broken pipe
        self.wfile.write(_ECHO_ON)
        self._send("")  # the client didn't echo their Enter; supply the newline
        if not line:
            return None
        self._note_gmcp(line)
        return _strip_telnet(line).decode("utf-8", errors="ignore").strip()

    def _passwd(self, session: Session) -> None:
        """Self-service password change with the echo blackout: prompt
        the old secret and the new one twice, then let the tick's passwd
        verb do the actual rotation. UX out here, tick stays the door."""
        old = self._ask_secret("Current password:")
        new = self._ask_secret("New password:")
        again = self._ask_secret("New password again:")
        if old is None or new is None or again is None:
            return  # walked away mid-change; nothing touched
        with TICK_LOCK:
            response = handle_command(session, f"passwd {old} {new} {again}")
        self._send(response)

    def _register_dialogue(self, session: Session) -> str | None:
        """The NEW-account sub-dialogue. A password the tick rejects (too short, or
        wrong for an account that already exists) re-prompts the password IN PLACE,
        keeping the handle the visitor already chose, instead of dropping them to the
        top menu and spending a door attempt on a typo (the bug this closed). Returns
        the tick's final `register` response for the caller to send, or None if the
        visitor walked away mid-registration."""
        handle = self._ask("Choose your character@account:")
        if handle is None:
            return None
        handle = handle.strip()
        initial_calling: str | None = None
        if SEED_NAME == "aethryn":
            from kernel.world.jobs import calling_label, character_creation_menu

            self._send(character_creation_menu())
            for _ in range(_AETHRYN_CREATION_TRIES):
                choice = self._ask("Calling (name):")
                if choice is None:
                    return None
                initial_calling = calling_label(choice)
                if initial_calling is not None:
                    break
                self._send("That calling is not available. Choose one from the menu.")
            if initial_calling is None:
                self._send("Character creation cancelled. Reconnect to try again.")
                return None
        response = ""
        for attempt in range(_REGISTER_TRIES):
            secret = self._ask_secret("Choose a password:")
            if secret is None:
                return None
            with TICK_LOCK:
                response = handle_command(session, f"register {handle} {secret.strip()}")
            last_try = attempt == _REGISTER_TRIES - 1
            if not password_fixable(response) or last_try:
                if response.startswith("Welcome,") and initial_calling is not None:
                    with TICK_LOCK:
                        chosen = handle_command(session, f"job {initial_calling}")
                        save_character(session)
                    response = f"{response}\n{chosen}"
                return response  # success, a handle problem, or out of tries
            self._send(response)  # a fixable password: nudge, then re-ask in place
        return response

    def _front_desk(self, session: Session) -> bool:
        """The classic connection ritual: authenticate BEFORE the world.
        The dialogue assembles login/register commands for the engine
        tick -- UX out here, but the tick stays the only door."""
        ip = self.client_address[0]
        if _gate_is_barred(ip):
            self._send("Too many failed logins from your address. Try again later.")
            return False
        self._send(load_splash())
        for _ in range(3):
            who = self._ask("Character (character@account) or NEW:")
            if who is None:
                return False
            who = who.strip().lower()
            if not who:
                self._send("Login required: enter your character@account, or type NEW.")
                continue
            if who == "new":
                response = self._register_dialogue(session)
                if response is None:
                    return False  # the visitor walked away mid-registration
            else:
                secret = self._ask_secret("Password:")
                if secret is None:
                    return False
                with TICK_LOCK:
                    response = handle_command(session, f"login {who} {secret.strip()}")
            self._send(response)
            if response.startswith(("Welcome back,", "Welcome,")):
                # A proven login, but a banned hero is turned away with their reason (moderation
                # outranks even a wizard's rank; an admin must lift it).
                if bans.is_banned(session.player_id):
                    self._send(f"You are banned: {bans.reason(session.player_id)}")
                    return False
                # The door may be down for maintenance: staff (wizard+) still enter; everyone else
                # is turned away with the reason. Rank is known now (the login set session.rank).
                if maintenance_mode.is_on() and not has_rank(session, "wizard"):
                    self._send(f"CodeForge is closed for maintenance: {maintenance_mode.reason()}")
                    return False
                _forgive_address(ip)  # a proven-good login clears any prior fumbles
                if response.startswith("Welcome,"):  # a fresh character needs its opening scene
                    self._send(render_scene(session.location, viewer=session.player_id))
                    nudge = tutorial.greeting(
                        session
                    )  # onboarding: point a new hero at the first step
                    if nudge:
                        self._send(nudge)
                return True
            _log_turnaway(ip)  # this login/register attempt failed
        self._send("Too many attempts. The door closes.")
        return False

    def handle(self) -> None:
        # One bulkhead slot per connection: held for the session's life, released on exit even if
        # the handler raises. A full compartment refuses fast instead of over-filling the pool.
        try:
            with _SEATS.slot():
                self._serve_player()
        except BulkheadFull:
            self._send("The forge is full right now. Try again shortly.")

    def _serve_player(self) -> None:
        player_id = _next_player_id()
        session = Session(player_id=player_id)
        entered = False
        with TICK_LOCK:
            SESSIONS[player_id] = session
            bind_echo(player_id, self._send)
            bind_gmcp(player_id, self._send_gmcp)  # structured frames pushed by social events
        _LOG.info("connection_open", peer=self.client_address[0])
        try:
            # The front desk may raise if the client drops mid-handshake (a
            # health-check connect, a reset). Whatever happens, the finally below
            # unbinds this session so a dead sink can never linger and crash
            # another player's broadcast.
            entered = self._front_desk(session)
            if not entered:
                return
            # The account is now authenticated: open the additive engineering-workspace wire for
            # this connection, and (for an owner) push the creation Form so their Native-Seed
            # client's Wizard can render. Orthogonal to the game path below.
            self._session = session
            if has_rank(session, "owner"):
                self._push_workspace_form()
                self._push_reference_workspace()
            presence.mark_online(
                session.player_id, session.location
            )  # joins the shared roster + room
            last_room = session.location  # track moves so the cross-process room view stays current
            self._push_state(session)  # first frames: the scene they logged into
            need_prompt = True
            while session.alive:
                if need_prompt:
                    self.wfile.write(b"> ")
                try:
                    message, is_frame = _read_message(self.rfile, MAX_LINE_BYTES)
                except OSError:
                    break  # idle timeout or broken pipe -> disconnect
                if not message:
                    break  # client hung up
                self._note_gmcp(message)  # negotiation + the engineering-workspace wire
                if is_frame:
                    # A standalone out-of-band GMCP frame: handled by _note_gmcp, it is not a game
                    # command, and it did not consume the prompt already on screen -- so process the
                    # next input without reprinting "> ".
                    need_prompt = False
                    continue
                need_prompt = True
                # Strip mid-session IAC negotiation (window-size, terminal-type, GMCP frames a
                # client glues to input) before the tick reads it -- the same codec the login
                # prompts (`_ask_line`/`_ask_secret`) already run. Without it, a client's answering
                # IAC bytes leak into the command line as decoded garbage and route to "Huh?".
                text = _strip_telnet(message).decode("utf-8", errors="ignore")
                if text.strip().lower() == "passwd":
                    self._passwd(session)  # multi-prompt dialogue with echo blackout
                    continue
                with TICK_LOCK:
                    response = handle_command(session, text)
                    self._autosave(session)  # periodic persist, under the same lock as the tick
                if response:
                    self._send(response)
                self._push_state(session)  # reflect any vitals/room change into GMCP
                if session.location != last_room:  # a move: refresh the cross-process room roster
                    last_room = session.location
                    presence.mark_at(session.player_id, last_room)
        except OSError:
            pass  # client dropped (broken pipe / reset) -- disconnect quietly
        finally:
            with TICK_LOCK:
                if entered:
                    save_character(session)  # only real players persist
                    presence.mark_offline(session.player_id)  # ...and leaves the shared roster
                party.on_disconnect(session.player_id)  # a logout leaves the fellowship
                trade.on_disconnect(session.player_id)  # ...and cancels any open trade
                guild.on_disconnect(session.player_id)  # ...and drops a pending guild invite
                unbind_echo(session.player_id)
                unbind_gmcp(session.player_id)
                SESSIONS.pop(session.player_id, None)
            _LOG.info("connection_close", player=session.player_id, entered=entered)


def serve(host: str = "0.0.0.0", port: int = 4000) -> None:
    # Power-on check: refuse to serve on a database whose columns are behind the models, rather
    # than crash the first login on `no such column`. Read-only; it names the fix, never migrates.
    from kernel.world.schema_guard import SchemaError, require_current_schema

    try:
        require_current_schema()
    except SchemaError as exc:
        print(f"REFUSING TO START: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    _configure_logging()  # gateway events emit as structured JSON from here
    broker_bus = maybe_wire_broker()  # CODEFORGE_BUS_BROKER set -> join a multi-process deployment
    if broker_bus is not None:
        _LOG.info("bus_broker_wired", broker=os.environ.get("CODEFORGE_BUS_BROKER"))
    with ForgeGateServer((host, port), _GateHandler) as server:

        def _save_and_stop() -> None:
            """The @shutdown hook. It runs INSIDE the tick lock (the verb reached it through
            handle_command), so it drains every live hero to disk WITHOUT re-acquiring the lock,
            then stops accepting. No player loses progress to an admin shutdown."""
            saved = save_all()
            _LOG.info("gateway_stop", reason="admin", saved=saved)
            print(f"Shutdown: saved {saved} live hero(es).")
            server.shutdown()

        SHUTDOWN["hook"] = _save_and_stop
        transport = "TLS (encrypted)" if server._tls is not None else "plaintext (LAN only)"
        _LOG.info("gateway_start", host=host, port=port, tls=server._tls is not None)
        print(f"CodeForge gateway listening on {host}:{port}  [{transport}]")
        print(f"Connect with:  nc <this-machine> {port}   (or any telnet client)")
        print("Press Ctrl+C to shut down.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down the gateway. The world sleeps.")
            # A signal, not a command: the lock is free here, so acquire it to save consistently
            # (waiting out any in-flight command first).
            with TICK_LOCK:
                saved = save_all()
            print(f"Saved {saved} live hero(es).")
            server.shutdown()


if __name__ == "__main__":
    serve()
