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
from parts.gateway import ForgeGateServer, _GateHandler, _sanitize
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    items_snap = copy.deepcopy(items.ITEMS)
    doors_snap = copy.deepcopy(doors.DOORS)
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    gateway._counter = 0
    gateway._seats_filled = 0
    gateway._turnaway_ledger.clear()
    yield
    items.ITEMS.clear()
    items.ITEMS.update(items_snap)
    doors.DOORS.clear()
    doors.DOORS.update(doors_snap)
    npcs.NPCS.clear()
    npcs.NPCS.update(npcs_snap)
    SESSIONS.clear()


@pytest.fixture()
def server():
    srv = ForgeGateServer(("127.0.0.1", 0), _GateHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _connect(srv: ForgeGateServer) -> socket.socket:
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


_acct_seq = 0


def _connect_player(srv: ForgeGateServer, who: str | None = None) -> socket.socket:
    """Register a fresh character@account and step into the world. Anonymous
    'guest' access was removed -- login is required -- so tests that just need
    a body in the world register one here."""
    global _acct_seq
    if who is None:
        _acct_seq += 1
        who = f"hero{_acct_seq}"
    sock = _connect(srv)
    _read_until(sock, b"NEW: ")
    _line(sock, "new")
    _read_until(sock, b"account: ")
    _line(sock, f"{who}@{who}_co")
    _read_until(sock, b"password: " + bytes([255, 251, 1]))
    _line(sock, "swordfish9")  # clears the 8-char floor
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
    banner = _read_until(sock, b"NEW: ")
    assert "T H E   F I R S T   F O R G E" in banner
    assert "The Cold Forge" not in banner  # the world waits behind the desk
    sock.close()


def test_empty_enter_does_not_grant_access(server):
    """Guest access was removed: pressing Enter re-prompts, never seats."""
    sock = _connect(server)
    _read_until(sock, b"NEW: ")
    _line(sock, "")  # just hit Enter, as a curious visitor would
    reply = _read_until(sock, b"NEW: ")  # the door re-prompts...
    assert "Login required" in reply  # ...with a refusal
    assert "The Cold Forge" not in reply  # and never opens the world
    sock.close()


def test_register_over_the_wire_seats_and_enters(server):
    sock = _connect(server)
    _read_until(sock, b"NEW: ")
    _line(sock, "new")
    _read_until(sock, b"account: ")
    _line(sock, "newbie@newco")
    _read_until(sock, b"password: " + bytes([255, 251, 1]))
    _line(sock, "swordfish9")
    scene = _read_until(sock, b"> ")
    assert "Welcome, Newbie@newco" in scene
    assert "The Cold Forge" in scene
    sock.close()


def test_login_dialogue_restores_a_hero_over_the_wire(server):
    _saved_account()
    sock = _connect(server)
    _read_until(sock, b"NEW: ")
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
        _read_until(sock, b"NEW: ")
        _line(sock, "matrym@matlabs")
        _read_until(sock, b"Password: " + bytes([255, 251, 1]))
        _line(sock, "wrong")
    tail = _drain_to_close(sock)  # server hangs up
    assert "Too many attempts" in tail
    sock.close()


def test_two_players_share_one_world(server):
    a, b = _connect_player(server), _connect_player(server)
    for s in (a, b):
        _command(s, "n"), _command(s, "e")
    assert "You take a copper key." in _command(a, "take key")
    assert "You don't see that here." in _command(b, "take key")
    a.close(), b.close()


def test_who_lists_everyone_and_quit_unseats(server):
    a, b = _connect_player(server, "ember"), _connect_player(server, "quill")
    out = _command(a, "who")
    assert "Ember" in out and "Quill" in out
    b.sendall(b"quit\n")
    b.recv(4096)
    b.close()
    deadline = time.time() + 2.0
    out = _command(a, "who")
    while "Quill" in out and time.time() < deadline:
        time.sleep(0.05)  # the server thread's cleanup races our next question
        out = _command(a, "who")
    assert "Quill" not in out
    a.close()


def test_password_prompt_negotiates_echo_blackout(server):
    """The telnet-native getpass: IAC WILL ECHO before the secret,
    IAC WONT ECHO after. Pinned at the byte level, over the wire."""
    _saved_account()
    sock = _connect(server)
    _read_until(sock, b"NEW: ")
    _line(sock, "matrym@matlabs")
    raw = _read_until_raw(sock, b"Password: " + bytes([255, 251, 1]))
    assert raw.endswith(bytes([255, 251, 1]))  # echo OFF ordered
    _line(sock, "swordfish")
    after = _read_until_raw(sock, b"> ")
    assert bytes([255, 252, 1]) in after  # echo ON restored
    assert "Welcome back, Matrym@matlabs" in after.decode("utf-8", errors="ignore")
    sock.close()


def _login(srv: ForgeGateServer, char="matrym", account="matlabs", pw="swordfish") -> socket.socket:
    """Connect and clear the front desk into the world as an account."""
    sock = _connect(srv)
    _read_until(sock, b"NEW: ")
    _line(sock, f"{char}@{account}")
    _read_until(sock, b"Password: " + bytes([255, 251, 1]))
    _line(sock, pw)
    _read_until(sock, b"> ")
    return sock


def test_passwd_flow_rotates_the_secret_with_blackout(server):
    """Bare 'passwd' in-world triggers the three-prompt dialogue, each
    prompt echo-blacked-out; the new secret then opens the door."""
    from parts.accounts import account_password_ok

    _saved_account()
    sock = _login(server)
    _line(sock, "passwd")
    raw = _read_until_raw(sock, b"Current password: " + bytes([255, 251, 1]))
    assert raw.endswith(bytes([255, 251, 1]))  # echo OFF for the old secret
    _line(sock, "swordfish")
    _read_until_raw(sock, b"New password: " + bytes([255, 251, 1]))
    _line(sock, "NewSecret9")
    _read_until_raw(sock, b"New password again: " + bytes([255, 251, 1]))
    _line(sock, "NewSecret9")
    out = _read_until(sock, b"> ")
    assert "Password changed" in out
    sock.close()
    assert account_password_ok("matlabs", "NewSecret9")  # new secret lives
    assert not account_password_ok("matlabs", "swordfish")  # old is dead


def test_passwd_flow_rejects_a_mismatch_over_the_wire(server):
    from parts.accounts import account_password_ok

    _saved_account()
    sock = _login(server)
    _line(sock, "passwd")
    _read_until_raw(sock, b"Current password: " + bytes([255, 251, 1]))
    _line(sock, "swordfish")
    _read_until_raw(sock, b"New password: " + bytes([255, 251, 1]))
    _line(sock, "AAAA1")
    _read_until_raw(sock, b"New password again: " + bytes([255, 251, 1]))
    _line(sock, "BBBB2")
    out = _read_until(sock, b"> ")
    assert "do not match" in out
    assert account_password_ok("matlabs", "swordfish")  # unchanged
    sock.close()


def test_sanitize_strips_control_chars_but_keeps_layout():
    assert _sanitize("hi\x1b[31mRED\x1b[0m") == "hi[31mRED[0m"  # ESC gone, text left inert
    assert _sanitize("line1\nline2\tok\r") == "line1\nline2\tok\r"  # newline/tab/CR kept
    assert _sanitize("bell\x07nul\x00del\x7f") == "bellnuldel"


def test_chat_escape_sequences_are_stripped_before_broadcast(server):
    """A player's chat must not carry escape sequences into another
    player's terminal. Sanitize at the client boundary."""
    a = _connect_player(server)
    b = _connect_player(server)  # both start in the same room
    _line(a, "say \x1b[31mred\x1b[2Jalert")
    _read_until(a, b"> ")  # a's own turn completes first
    heard = _read_until(b, b"\r\n")  # b hears the broadcast
    assert "\x1b" not in heard  # no raw escape reached b
    assert "red" in heard and "alert" in heard  # the words survived
    a.close()
    b.close()


def test_repeated_failures_rate_limit_the_address(server, monkeypatch):
    """Per-connection 3-strikes resets on reconnect; the per-IP limiter
    does not. After enough failures the address is refused up front."""
    _saved_account()
    monkeypatch.setattr(gateway, "MAX_LOGIN_FAILS", 3)
    sock = _connect(server)
    for _ in range(3):  # three bad passwords: door closes, 3 failures logged
        _read_until(sock, b"NEW: ")
        _line(sock, "matrym@matlabs")
        _read_until_raw(sock, bytes([255, 251, 1]))
        _line(sock, "wrongpass")
    assert "Too many attempts" in _drain_to_close(sock)
    sock.close()
    refused = _connect(server)  # same address, now over the limit
    assert "Too many failed logins" in _drain_to_close(refused)
    refused.close()


def test_rate_limit_check_never_grows_the_table(server):
    """_gate_is_barred is read-only: connect-only traffic (no failed
    logins) must not add dict entries -- that would be a memory leak an
    attacker could drive with bare connects."""
    sock = _connect_player(server)  # a clean visit: no failures
    sock.close()
    assert gateway._turnaway_ledger == {}
    assert gateway._gate_is_barred("10.9.8.7") is False
    assert "10.9.8.7" not in gateway._turnaway_ledger


def test_stale_failure_addresses_are_swept_out(monkeypatch):
    """Addresses whose failures aged past the window are deleted, not
    kept forever: the table is bounded by currently-failing addresses."""
    clock = {"now": 1000.0}
    monkeypatch.setattr(gateway.time, "monotonic", lambda: clock["now"])
    gateway._log_turnaway("10.0.0.1")
    assert gateway._gate_is_barred("10.0.0.1") is False  # one strike isn't a ban
    clock["now"] += gateway.LOGIN_FAIL_WINDOW + 1  # the window passes
    gateway._log_turnaway("10.0.0.2")  # any new failure sweeps the table
    assert "10.0.0.1" not in gateway._turnaway_ledger  # stale key gone
    assert list(gateway._turnaway_ledger) == ["10.0.0.2"]


def test_connection_cap_refuses_when_full(server, monkeypatch):
    monkeypatch.setattr(gateway, "MAX_CONNECTIONS", 1)
    holder = _connect_player(server)  # occupies the only slot
    overflow = _connect(server)
    assert "forge is full" in _drain_to_close(overflow)
    holder.close()
    overflow.close()


def test_idle_connection_times_out_and_closes(server, monkeypatch):
    monkeypatch.setattr(gateway._GateHandler, "timeout", 0.5)
    sock = _connect_player(server)  # seated in the world, then goes silent
    assert _drain_to_close(sock) == ""  # server drops the idle socket, no data
    sock.close()


def test_client_negotiation_bytes_never_pollute_the_secret(server):
    """Clients reply with their own IAC sequences; the stripper must
    keep them out of the password."""
    _saved_account()
    sock = _connect(server)
    _read_until(sock, b"NEW: ")
    _line(sock, "matrym@matlabs")
    _read_until_raw(sock, bytes([255, 251, 1]))
    # a compliant client's reply (IAC DO ECHO) arrives glued to the secret
    sock.sendall(bytes([255, 253, 1]) + b"swordfish\n")
    out = _read_until(sock, b"> ")
    assert "Welcome back, Matrym@matlabs" in out
    sock.close()
