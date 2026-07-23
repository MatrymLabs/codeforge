"""CARD: gateway -- a line-based TCP server sharing one world.

Each connection gets its own Session; every command runs through the
same engine tick under one lock -- the classic MUD 'one command at a
time' model. Plain lines in, plain text out: connect with nc or any
telnet client.

Security: plaintext, no auth, LAN-visible. This is the compatibility
transport for your home network, not an internet-facing service.
"""

import contextlib
import re
import socket
import socketserver
import threading
import time

from forge import handle_command, render_scene
from parts.gmcp import GMCP_OPT, enables_gmcp, gmcp_frame, room_report, vitals_report
from parts.shelf.bulkhead import Bulkhead, BulkheadFull
from parts.shelf.telnet_codec import IAC, WILL, WONT, strip_iac
from parts.world.accounts import password_fixable
from parts.world.characters import save_character
from parts.world.events import SHUTDOWN, bind_echo, unbind_echo
from parts.world.seed import load_splash
from parts.world.session import SESSIONS, Session

TICK_LOCK = threading.Lock()
_counter_lock = threading.Lock()
_counter = 0

# --- the doorman's post: seats, silence, and the turnaway ledger ---
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


# --- telnet option negotiation (RFC 854/857): the password blackout ---
# The Telnet wire codec (command bytes, IAC stripping) lives in parts.shelf.telnet_codec; the
# gate is a consumer of it. `_strip_telnet` is a local alias for the codec's `strip_iac` so callers
# (and the test twin) that reference it stay stable.
ECHO_OPT = 1
_ECHO_OFF = bytes([IAC, WILL, ECHO_OPT])  # "I will echo" -> client stops echoing
_ECHO_ON = bytes([IAC, WONT, ECHO_OPT])  # "I won't echo" -> client resumes

# GMCP (option 201): offer it on connect. A capable client answers DO/WILL GMCP and then gets
# structured state frames (Char.Vitals, Room.Info) alongside the text; a raw nc never answers, so
# it stays a plain-text client and sees no binary. Framing + the reply-reader live in parts/gmcp.py.
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


class ForgeGateServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


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
        self._last_vitals: dict[str, int] | None = None
        self._last_room: dict[str, object] | None = None
        with contextlib.suppress(OSError):
            self.wfile.write(_WILL_GMCP)

    def _note_gmcp(self, raw: bytes) -> None:
        """Read a client's GMCP negotiation reply out of raw input and record its choice."""
        verdict = enables_gmcp(raw)
        if verdict is not None:
            self._gmcp_enabled = verdict

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
        response = ""
        for attempt in range(_REGISTER_TRIES):
            secret = self._ask_secret("Choose a password:")
            if secret is None:
                return None
            with TICK_LOCK:
                response = handle_command(session, f"register {handle} {secret.strip()}")
            last_try = attempt == _REGISTER_TRIES - 1
            if not password_fixable(response) or last_try:
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
            if response.startswith("Welcome back,"):
                _forgive_address(ip)  # a proven-good login clears any prior fumbles
                return True  # the restore response already renders the scene
            if response.startswith("Welcome,"):
                _forgive_address(ip)
                self._send(render_scene(session.location, viewer=session.player_id))
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
        try:
            # The front desk may raise if the client drops mid-handshake (a
            # health-check connect, a reset). Whatever happens, the finally below
            # unbinds this session so a dead sink can never linger and crash
            # another player's broadcast.
            entered = self._front_desk(session)
            if not entered:
                return
            self._push_state(session)  # first frames: the scene they logged into
            while session.alive:
                self.wfile.write(b"> ")
                try:
                    line = self.rfile.readline(MAX_LINE_BYTES)
                except OSError:
                    break  # idle timeout or broken pipe -> disconnect
                if not line:
                    break  # client hung up
                self._note_gmcp(line)  # a client can enable/disable GMCP mid-session
                # Strip mid-session IAC negotiation (window-size, terminal-type, GMCP frames a
                # client glues to input) before the tick reads it -- the same codec the login
                # prompts (`_ask_line`/`_ask_secret`) already run. Without it, a client's answering
                # IAC bytes leak into the command line as decoded garbage and route to "Huh?".
                text = _strip_telnet(line).decode("utf-8", errors="ignore")
                if text.strip().lower() == "passwd":
                    self._passwd(session)  # multi-prompt dialogue with echo blackout
                    continue
                with TICK_LOCK:
                    response = handle_command(session, text)
                if response:
                    self._send(response)
                self._push_state(session)  # reflect any vitals/room change into GMCP
        except OSError:
            pass  # client dropped (broken pipe / reset) -- disconnect quietly
        finally:
            with TICK_LOCK:
                if entered:
                    save_character(session)  # only real players persist
                unbind_echo(session.player_id)
                SESSIONS.pop(session.player_id, None)


def serve(host: str = "0.0.0.0", port: int = 4000) -> None:
    with ForgeGateServer((host, port), _GateHandler) as server:
        SHUTDOWN["hook"] = server.shutdown
        print(f"CodeForge gateway listening on {host}:{port}")
        print(f"Connect with:  nc <this-machine> {port}   (or any telnet client)")
        print("Press Ctrl+C to shut down.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down the gateway. The world sleeps.")
            server.shutdown()


if __name__ == "__main__":
    serve()
