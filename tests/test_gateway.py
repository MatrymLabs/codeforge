"""Test twin for parts/gateway.py -- real sockets, real shared world."""

import copy
import socket
import threading

import pytest

import parts.gateway as gateway
from parts import doors, items, npcs, session
from parts.gateway import GatewayServer, _Handler


@pytest.fixture(autouse=True)
def fresh_world():
    items_snap = copy.deepcopy(items.ITEMS)
    doors_snap = copy.deepcopy(doors.DOORS)
    npcs_snap = copy.deepcopy(npcs.NPCS)
    session.SESSIONS.clear()
    gateway._counter = 0
    yield
    items.ITEMS = items_snap
    doors.DOORS = doors_snap
    npcs.NPCS = npcs_snap
    session.SESSIONS.clear()


@pytest.fixture()
def server():
    srv = GatewayServer(("127.0.0.1", 0), _Handler)  # port 0: OS picks a free one
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _connect(srv: GatewayServer) -> socket.socket:
    sock = socket.create_connection(("127.0.0.1", srv.server_address[1]), timeout=3)
    sock.settimeout(3)
    return sock


def _read_until_prompt(sock: socket.socket) -> str:
    data = b""
    while not data.endswith(b"> "):
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data.decode("utf-8")


def _command(sock: socket.socket, text: str) -> str:
    sock.sendall((text + "\n").encode("utf-8"))
    return _read_until_prompt(sock)


def test_connection_gets_the_splash_over_the_wire(server):
    """Pins the WIRING, not just the loader: the splash must arrive
    on a real socket. A loader that exists but is never called fails here."""
    sock = _connect(server)
    banner = _read_until_prompt(sock)
    assert "T H E   F I R S T   F O R G E" in banner
    assert "login <character>@<account> <password>" in banner
    assert "You are seated as Player1" in banner
    assert "The Cold Forge" in banner
    sock.close()


def test_two_clients_share_one_world(server):
    a, b = _connect(server), _connect(server)
    _read_until_prompt(a)
    _read_until_prompt(b)
    _command(a, "n"), _command(a, "e")
    _command(b, "n"), _command(b, "e")
    assert "You take a copper key." in _command(a, "take key")
    assert "You don't see that here." in _command(b, "take key")
    a.close(), b.close()


def test_who_lists_everyone_connected(server):
    a, b = _connect(server), _connect(server)
    _read_until_prompt(a)
    _read_until_prompt(b)
    out = _command(a, "who")
    assert "Player1" in out
    assert "Player2" in out
    a.close(), b.close()


def test_quit_unseats_the_player(server):
    a = _connect(server)
    _read_until_prompt(a)
    a.sendall(b"quit\n")
    a.recv(4096)  # farewell text
    a.close()
    b = _connect(server)
    _read_until_prompt(b)
    out = _command(b, "who")
    assert "Player1" not in out
    b.close()
