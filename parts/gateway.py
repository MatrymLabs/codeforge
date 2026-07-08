"""CARD: gateway -- a line-based TCP server sharing one world.

Each connection gets its own Session; every command runs through the
same engine tick under one lock -- the classic MUD 'one command at a
time' model. Plain lines in, plain text out: connect with nc or any
telnet client.

Security: plaintext, no auth, LAN-visible. This is the compatibility
transport for your home network, not an internet-facing service.
"""

import socketserver
import threading

from forge import handle_command, render_scene
from parts.characters import save_character
from parts.events import SHUTDOWN, register, unregister
from parts.seed import SEED_DIR
from parts.session import SESSIONS, Session, display_name

TICK_LOCK = threading.Lock()
_counter_lock = threading.Lock()
_counter = 0


def _next_player_id() -> str:
    global _counter
    with _counter_lock:
        _counter += 1
        return f"player{_counter}"


# --- telnet option negotiation (RFC 854/857): the password blackout ---
IAC, WILL, WONT, DO, DONT = 255, 251, 252, 253, 254
ECHO_OPT = 1
_ECHO_OFF = bytes([IAC, WILL, ECHO_OPT])  # "I will echo" -> client stops echoing
_ECHO_ON = bytes([IAC, WONT, ECHO_OPT])  # "I won't echo" -> client resumes


def _strip_telnet(data: bytes) -> bytes:
    """Remove IAC command sequences from raw input. Clients answer our
    negotiation with their own IAC bytes -- those must never end up
    inside a password."""
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == IAC and i + 1 < len(data):
            command = data[i + 1]
            if command == IAC:  # escaped literal 255
                out.append(IAC)
                i += 2
            elif command in (WILL, WONT, DO, DONT):
                i += 3  # three-byte sequence: IAC <verb> <option>
            else:
                i += 2
        else:
            out.append(data[i])
            i += 1
    return bytes(out)


def load_splash() -> str:
    """The pre-login screen is world data: seeds/<world>/splash.txt."""
    path = SEED_DIR / "splash.txt"
    if path.exists():
        return path.read_text().rstrip("\n")
    return "Welcome, traveler."


class GatewayServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class _Handler(socketserver.StreamRequestHandler):
    def _send(self, text: str) -> None:
        self.wfile.write((text + "\r\n").encode("utf-8"))

    def _ask(self, prompt: str) -> str | None:
        """One question at the front desk. None means they walked away."""
        self.wfile.write((prompt + " ").encode("utf-8"))
        line = self.rfile.readline()
        if not line:
            return None
        return _strip_telnet(line).decode("utf-8", errors="ignore").strip()

    def _ask_secret(self, prompt: str) -> str | None:
        """A question whose answer must not appear on the client's
        screen: negotiate echo OFF, read, negotiate echo ON. The
        telnet-native getpass. (nc ignores negotiation -- raw pipes
        keep their echo; Mudlet and telnet go dark.)"""
        self.wfile.write((prompt + " ").encode("utf-8") + _ECHO_OFF)
        line = self.rfile.readline()
        self.wfile.write(_ECHO_ON)
        self._send("")  # the client didn't echo their Enter; supply the newline
        if not line:
            return None
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

    def _front_desk(self, session: Session) -> bool:
        """The classic connection ritual: authenticate BEFORE the world.
        The dialogue assembles login/register commands for the engine
        tick -- UX out here, but the tick stays the only door."""
        self._send(load_splash())
        for _ in range(3):
            who = self._ask("Character (character@account), NEW, or GUEST:")
            if who is None:
                return False
            who = who.strip().lower()
            if who in ("guest", "g", ""):
                self._send(f"Wandering in as {display_name(session.player_id)}.")
                self._send(render_scene(session.location, viewer=session.player_id))
                return True
            if who == "new":
                handle = self._ask("Choose your character@account:") or ""
                secret = self._ask_secret("Choose a password:") or ""
                command = f"register {handle.strip()} {secret.strip()}"
            else:
                secret = self._ask_secret("Password:") or ""
                command = f"login {who} {secret.strip()}"
            with TICK_LOCK:
                response = handle_command(session, command)
            self._send(response)
            if response.startswith("Welcome back,"):
                return True  # the restore response already renders the scene
            if response.startswith("Welcome,"):
                self._send(render_scene(session.location, viewer=session.player_id))
                return True
        self._send("Too many attempts. The door closes.")
        return False

    def handle(self) -> None:
        player_id = _next_player_id()
        session = Session(player_id=player_id)
        with TICK_LOCK:
            SESSIONS[player_id] = session
            register(player_id, self._send)
        if not self._front_desk(session):
            with TICK_LOCK:
                unregister(session.player_id)
                SESSIONS.pop(session.player_id, None)
            return
        try:
            while session.alive:
                self.wfile.write(b"> ")
                line = self.rfile.readline()
                if not line:
                    break  # client hung up
                text = line.decode("utf-8", errors="ignore")
                if text.strip().lower() == "passwd":
                    self._passwd(session)  # multi-prompt dialogue with echo blackout
                    continue
                with TICK_LOCK:
                    response = handle_command(session, text)
                if response:
                    self._send(response)
        finally:
            with TICK_LOCK:
                save_character(session)
                unregister(session.player_id)
                SESSIONS.pop(session.player_id, None)


def serve(host: str = "0.0.0.0", port: int = 4000) -> None:
    with GatewayServer((host, port), _Handler) as server:
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
