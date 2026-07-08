"""Test twin for parts/gateway.py -- the front desk, over real sockets."""

import copy
import socket
import threading
import time

import pytest

import parts.gateway as gateway
from parts import doors, items, npcs
from parts.accounts import adopt
from parts.accounts import register as register_account
from parts.characters import save_character
from parts.gateway import GatewayServer, _Handler
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    items_snap = copy.deepcopy(items.ITEMS)
    doors_snap = copy.deepcopy(doors.DOORS)
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    gateway._counter = 0
    yield
    items.ITEMS = items_snap
    doors.DOORS = doors_snap
    npcs.NPCS = npcs_snap
    SESSIONS.clear()


@pytest.fixture()
def server():
    srv = GatewayServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _connect(srv: GatewayServer) -> socket.socket:
    sock = socket.create_connection(("127.0.0.1", srv.server_address[1]), timeout=3)
    sock.settimeout(3)
    return sock


def _read_until(sock: socket.socket, marker: bytes) -> str:
    return _read_until_raw(sock, marker).decode("utf-8", errors="ignore")


def _read_until_raw(sock: socket.socket, marker: bytes) -> bytes:
    data = b""
    while not data.endswith(marker):
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def _drain_to_close(sock: socket.socket) -> str:
    """Read everything until the server hangs up. endswith(b"") is
    always True, so 'read until close' needs its own loop shape."""
    data = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            return data.decode("utf-8", errors="ignore")
        data += chunk


def _line(sock: socket.socket, text: str) -> None:
    sock.sendall((text + "\n").encode("utf-8"))


def _connect_guest(srv: GatewayServer) -> socket.socket:
    sock = _connect(srv)
    _read_until(sock, b"GUEST: ")
    _line(sock, "guest")
    _read_until(sock, b"> ")
    return sock


def _command(sock: socket.socket, text: str) -> str:
    _line(sock, text)
    return _read_until(sock, b"> ")


def _saved_account(char: str = "matrym", account: str = "matlabs", pw: str = "swordfish"):
    hero = Session(player_id=char, location="courtyard", named=True, account=account)
    SESSIONS[char] = hero
    hero.level = 2
    save_character(hero)
    SESSIONS.clear()
    register_account("other_seed", account, pw)  # creates the account
    adopt(char, account)  # attach the real character to it


def test_front_desk_shows_splash_and_stops_at_the_door(server):
    sock = _connect(server)
    banner = _read_until(sock, b"GUEST: ")
    assert "T H E   F I R S T   F O R G E" in banner
    assert "The Cold Forge" not in banner  # the world waits behind the desk
    sock.close()


def test_guest_path_seats_and_enters_the_world(server):
    sock = _connect(server)
    _read_until(sock, b"GUEST: ")
    _line(sock, "guest")
    scene = _read_until(sock, b"> ")
    assert "Wandering in as Player1" in scene
    assert "The Cold Forge" in scene
    sock.close()


def test_login_dialogue_restores_a_hero_over_the_wire(server):
    _saved_account()
    sock = _connect(server)
    _read_until(sock, b"GUEST: ")
    _line(sock, "matrym@matlabs")
    _read_until(sock, b"Password: " + bytes([255, 251, 1]))
    _line(sock, "swordfish")
    out = _read_until(sock, b"> ")
    assert "Welcome back, Matrym@matlabs" in out
    assert "Broken Courtyard" in out  # restored to their saved room
    sock.close()


def test_three_wrong_passwords_close_the_door(server):
    _saved_account()
    sock = _connect(server)
    for _ in range(3):
        _read_until(sock, b"GUEST: ")
        _line(sock, "matrym@matlabs")
        _read_until(sock, b"Password: " + bytes([255, 251, 1]))
        _line(sock, "wrong")
    tail = _drain_to_close(sock)  # server hangs up
    assert "Too many attempts" in tail
    sock.close()


def test_two_guests_share_one_world(server):
    a, b = _connect_guest(server), _connect_guest(server)
    for s in (a, b):
        _command(s, "n"), _command(s, "e")
    assert "You take a copper key." in _command(a, "take key")
    assert "You don't see that here." in _command(b, "take key")
    a.close(), b.close()


def test_who_lists_everyone_and_quit_unseats(server):
    a, b = _connect_guest(server), _connect_guest(server)
    out = _command(a, "who")
    assert "Player1" in out and "Player2" in out
    b.sendall(b"quit\n")
    b.recv(4096)
    b.close()
    deadline = time.time() + 2.0
    out = _command(a, "who")
    while "Player2" in out and time.time() < deadline:
        time.sleep(0.05)  # the server thread's cleanup races our next question
        out = _command(a, "who")
    assert "Player2" not in out
    a.close()


def test_password_prompt_negotiates_echo_blackout(server):
    """The telnet-native getpass: IAC WILL ECHO before the secret,
    IAC WONT ECHO after. Pinned at the byte level, over the wire."""
    _saved_account()
    sock = _connect(server)
    _read_until(sock, b"GUEST: ")
    _line(sock, "matrym@matlabs")
    raw = _read_until_raw(sock, b"Password: " + bytes([255, 251, 1]))
    assert raw.endswith(bytes([255, 251, 1]))  # echo OFF ordered
    _line(sock, "swordfish")
    after = _read_until_raw(sock, b"> ")
    assert bytes([255, 252, 1]) in after  # echo ON restored
    assert "Welcome back, Matrym@matlabs" in after.decode("utf-8", errors="ignore")
    sock.close()


def test_client_negotiation_bytes_never_pollute_the_secret(server):
    """Clients reply with their own IAC sequences; the stripper must
    keep them out of the password."""
    _saved_account()
    sock = _connect(server)
    _read_until(sock, b"GUEST: ")
    _line(sock, "matrym@matlabs")
    _read_until_raw(sock, bytes([255, 251, 1]))
    # a compliant client's reply (IAC DO ECHO) arrives glued to the secret
    sock.sendall(bytes([255, 253, 1]) + b"swordfish\n")
    out = _read_until(sock, b"> ")
    assert "Welcome back, Matrym@matlabs" in out
    sock.close()
