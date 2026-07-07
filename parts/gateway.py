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
from parts.session import SESSIONS, Session, display_name

TICK_LOCK = threading.Lock()
_counter_lock = threading.Lock()
_counter = 0


def _next_player_id() -> str:
    global _counter
    with _counter_lock:
        _counter += 1
        return f"player{_counter}"


class GatewayServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class _Handler(socketserver.StreamRequestHandler):
    def _send(self, text: str) -> None:
        self.wfile.write((text + "\r\n").encode("utf-8"))

    def handle(self) -> None:
        player_id = _next_player_id()
        session = Session(player_id=player_id)
        with TICK_LOCK:
            SESSIONS[player_id] = session
            register(player_id, self._send)
        self._send(f"Welcome to The First Forge, {display_name(player_id)}. Type HELP to begin.")
        self._send(render_scene(session.location, viewer=player_id))
        try:
            while session.alive:
                self.wfile.write(b"> ")
                line = self.rfile.readline()
                if not line:
                    break  # client hung up
                with TICK_LOCK:
                    response = handle_command(session, line.decode("utf-8", errors="ignore"))
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
