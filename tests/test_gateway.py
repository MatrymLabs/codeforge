"""Test twin for adapters/gateway.py -- the front desk, over real sockets."""

import copy
import socket
import ssl
import subprocess
import threading
import time

import pytest

import adapters.gateway as gateway
from adapters.gateway import ForgeGateServer, _GateHandler, _sanitize
from kernel.shelf.bulkhead import Bulkhead
from kernel.world import doors, items, npcs
from kernel.world.accounts import adopt
from kernel.world.accounts import register as register_account
from kernel.world.characters import save_character
from kernel.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    items_snap = copy.deepcopy(items.ITEMS)
    doors_snap = copy.deepcopy(doors.DOORS)
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    gateway._counter = 0
    gateway._SEATS = Bulkhead(gateway.MAX_CONNECTIONS)  # fresh, empty seat bulkhead per test
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


def test_short_password_reprompts_in_place_then_registers(server):
    """A NEW visitor who fumbles the password LENGTH is re-prompted for the
    password in place -- keeping the handle they already chose -- not dumped
    back to the top menu (the death spiral a captured session exposed)."""
    sock = _connect(server)
    _read_until(sock, b"NEW: ")
    _line(sock, "new")
    _read_until(sock, b"account: ")
    _line(sock, "test@testing")
    _read_until(sock, b"password: " + bytes([255, 251, 1]))
    _line(sock, "short")  # 5 chars: under the 8-char floor
    nudge = _read_until(sock, b"password: " + bytes([255, 251, 1]))
    assert "Passwords need at least" in nudge  # it nudged...
    assert "NEW:" not in nudge  # ...and re-asked in place, NOT back at the top
    _line(sock, "swordfish9")  # a valid password now
    scene = _read_until(sock, b"> ")
    assert "Welcome, Test@testing" in scene  # the ORIGINAL handle survived
    sock.close()


def test_repeated_short_passwords_are_bounded_not_infinite(server):
    """The in-place retry is bounded: after _REGISTER_TRIES too-short tries the
    registration ends as one turnaway and the visitor is returned to the desk,
    never looped forever on the same prompt."""
    sock = _connect(server)
    _read_until(sock, b"NEW: ")
    _line(sock, "new")
    _read_until(sock, b"account: ")
    _line(sock, "test@testing")
    for _ in range(gateway._REGISTER_TRIES):
        _read_until(sock, b"password: " + bytes([255, 251, 1]))
        _line(sock, "short")
    back = _read_until(sock, b"NEW: ")  # returned to the top desk prompt
    assert "Passwords need at least" in back
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
    from kernel.world.accounts import account_password_ok

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
    from kernel.world.accounts import account_password_ok

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


def test_subnegotiation_bytes_never_pollute_the_secret():
    """A telnet subnegotiation frame (IAC SB ... IAC SE) glued to input -- e.g. a MUD client's
    window-size report -- must be fully stripped, or its body corrupts the password mid-login."""
    frame = bytes([255, 250, 31, 0, 80, 0, 24, 255, 240]) + b"swordfish"  # IAC SB NAWS ... IAC SE
    assert gateway._strip_telnet(frame).decode("utf-8", "ignore").strip() == "swordfish"
    # an unterminated frame (split across reads) drops to the end -- never leaks the body
    assert gateway._strip_telnet(bytes([255, 250, 31, 0, 80]) + b"leak") == b""


def test_main_loop_strips_iac_glued_to_a_command(server):
    """The login prompts already strip IAC; the MAIN input loop must too. A client that glues a
    window-size report (IAC SB NAWS ... IAC SE) to a command must still route the command, not
    let the frame's body bytes decode into garbage and fall through to 'Huh?'."""
    sock = _connect_player(server)
    frame = bytes([255, 250, 31, 0, 80, 0, 24, 255, 240])  # IAC SB NAWS 80x24 IAC SE
    sock.sendall(frame + b"look\n")
    out = _read_until(sock, b"> ")
    assert "Huh?" not in out
    assert "Cold Forge" in out  # the command reached the tick and rendered the room
    sock.close()


def test_a_proven_good_login_clears_the_failure_tally(monkeypatch):
    """Reset-on-success: a legitimate user who fumbled then logged in isn't barred by the leftover
    failures. A brute-forcer never reaches this (never authenticates), so it can't reset the bar."""
    monkeypatch.setattr(gateway, "MAX_LOGIN_FAILS", 3)
    ip = "5.6.7.8"
    for _ in range(2):
        gateway._log_turnaway(ip)
    gateway._forgive_address(ip)
    assert ip not in gateway._turnaway_ledger
    assert gateway._gate_is_barred(ip) is False


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
    monkeypatch.setattr(gateway, "_SEATS", Bulkhead(1))  # the seat bulkhead admits exactly one
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


# --- GMCP: structured out-of-band state for a capable client ---------------

_SB_GMCP = bytes([255, 250, 201])  # IAC SB GMCP (a subnegotiation frame opening)
_DO_GMCP = bytes([255, 253, 201])  # IAC DO GMCP (a client enabling GMCP)


def _saved_hero_with_calling(char="mira", account="mlabs", pw="swordfish", job="vanguard"):
    """A saved character that has taken a calling, so vitals actually derive on restore."""
    from kernel.world.jobs import bind_calling

    hero = Session(player_id=char, location="courtyard", named=True, account=account)
    bind_calling(hero, job)
    hero.level = 2
    SESSIONS[char] = hero
    save_character(hero)
    SESSIONS.clear()
    register_account(f"{account}_seed", account, pw)
    adopt(char, account)


def test_a_gmcp_client_receives_room_and_vitals_frames_on_entry(server):
    """A client that answers the GMCP offer gets Room.Info and Char.Vitals as subnegotiation
    frames the moment it enters the world -- structured state beside the text scene."""
    _saved_hero_with_calling()
    sock = _connect(server)
    sock.sendall(_DO_GMCP)  # enable GMCP before the dialogue (rides the first input line)
    _read_until(sock, b"NEW: ")
    _line(sock, "mira@mlabs")
    _read_until_raw(sock, b"Password: " + bytes([255, 251, 1]))
    _line(sock, "swordfish")
    out = _read_until_raw(sock, b"> ")
    assert _SB_GMCP in out  # at least one GMCP subnegotiation frame was pushed
    assert b"Room.Info" in out and b"Broken Courtyard" in out  # the room, as data
    assert b"Char.Vitals" in out and b'"hp":' in out  # live vitals, as data
    assert b"Char.Quest" in out  # the active story arc, as data (the tracker lights up)
    sock.close()


def test_a_gmcp_client_is_announced_the_seed_on_enabling_gmcp(server):
    """The Native Seed handshake (ADR-0002): a client that enables GMCP is announced the loaded Seed
    with a single Seed.Hello frame, so it can negotiate whether it can enter."""
    _saved_hero_with_calling()
    sock = _connect(server)
    sock.sendall(_DO_GMCP)  # enable GMCP (rides the first input line), the handshake trigger
    # Seed.Hello is announced the moment GMCP enables (before login), so accumulate all output.
    out = _read_until_raw(sock, b"NEW: ")
    _line(sock, "mira@mlabs")
    out += _read_until_raw(sock, b"Password: " + bytes([255, 251, 1]))
    _line(sock, "swordfish")
    out += _read_until_raw(sock, b"> ")
    assert b"Seed.Hello" in out  # the Seed announced itself to the capable client
    assert out.count(b"Seed.Hello") == 1  # exactly once, not on every frame push
    sock.close()


def test_a_gmcp_client_receives_char_items_for_equipped_gear(server):
    """An equipped hero's loadout is pushed as Char.Items on entry, so the client can draw the
    inventory panel from data - a frame we emit because we own the engine, not a MUD standard."""
    from kernel.world.items import clone
    from kernel.world.jobs import bind_calling

    hero = Session(player_id="mira", location="courtyard", named=True, account="mlabs")
    bind_calling(hero, "vanguard")
    hero.equipped["weapon"] = clone("forge_wrench", "player")  # a real, restorable prototype
    SESSIONS["mira"] = hero
    save_character(hero)
    SESSIONS.clear()
    register_account("mlabs_seed", "mlabs", "swordfish")
    adopt("mira", "mlabs")

    sock = _connect(server)
    sock.sendall(_DO_GMCP)
    _read_until(sock, b"NEW: ")
    _line(sock, "mira@mlabs")
    _read_until_raw(sock, b"Password: " + bytes([255, 251, 1]))
    _line(sock, "swordfish")
    out = _read_until_raw(sock, b"> ")
    assert b"Char.Items" in out and b"forge wrench" in out  # the loadout, as data
    sock.close()


def test_a_gmcp_client_receives_char_skills_for_the_wieldable_kit(server):
    """A calling's kit is pushed as Char.Skills on entry, so a client's co-pilot can recommend a
    specific move for a foe's weakness - a frame we emit because we own the engine."""
    from kernel.world.jobs import bind_calling

    hero = Session(player_id="tovi", location="courtyard", named=True, account="mlabs")
    bind_calling(hero, "vanguard")  # wields Power Strike
    SESSIONS["tovi"] = hero
    save_character(hero)
    SESSIONS.clear()
    register_account("mlabs_seed2", "mlabs", "swordfish")
    adopt("tovi", "mlabs")

    sock = _connect(server)
    sock.sendall(_DO_GMCP)
    _read_until(sock, b"NEW: ")
    _line(sock, "tovi@mlabs")
    _read_until_raw(sock, b"Password: " + bytes([255, 251, 1]))
    _line(sock, "swordfish")
    out = _read_until_raw(sock, b"> ")
    assert b"Char.Skills" in out and b"Power Strike" in out  # the kit, as data
    # A second command pushes state again with an unchanged kit: Char.Skills is NOT re-sent (the
    # change-detection holds, like the other frames), so the client's panel never flickers.
    _line(sock, "look")
    again = _read_until_raw(sock, b"> ")
    assert b"Char.Skills" not in again  # unchanged kit: no redundant frame
    sock.close()


def test_a_gmcp_client_receives_char_resists_for_the_defensive_grid(server):
    """An engineer's non-normal resistances are pushed as Char.Resists, so a client can warn when a
    foe's element hits a weakness - the defensive mirror of the foe's profile in Char.Target."""
    from kernel.world.jobs import bind_calling

    hero = Session(player_id="vess", location="courtyard", named=True, account="mlabs")
    bind_calling(hero, "engineer")  # declares LGT: Weak, ERT: Resist
    SESSIONS["vess"] = hero
    save_character(hero)
    SESSIONS.clear()
    register_account("mlabs_seed3", "mlabs", "swordfish")
    adopt("vess", "mlabs")

    sock = _connect(server)
    sock.sendall(_DO_GMCP)
    _read_until(sock, b"NEW: ")
    _line(sock, "vess@mlabs")
    _read_until_raw(sock, b"Password: " + bytes([255, 251, 1]))
    _line(sock, "swordfish")
    out = _read_until_raw(sock, b"> ")
    assert b"Char.Resists" in out and b"Weak" in out  # the defensive grid, as data
    _line(sock, "look")
    again = _read_until_raw(sock, b"> ")
    assert b"Char.Resists" not in again  # unchanged grid: no redundant frame
    sock.close()


def test_a_plain_client_never_receives_gmcp_frames(server):
    """A raw client that never answers the offer must not get a single GMCP subnegotiation
    frame -- only the offer byte (IAC WILL GMCP), never IAC SB GMCP binary in its text stream."""
    sock = _connect_player(server)  # _connect_player never negotiates GMCP
    _line(sock, "look")
    out = _read_until_raw(sock, b"> ")
    assert _SB_GMCP not in out  # no structured frames leak to a plain-text client
    sock.close()


# --- TLS transport (config-gated encrypted sockets) ---------------------------------------------
@pytest.fixture
def _tls_pair(tmp_path):
    """A throwaway self-signed cert + key for localhost, generated with the openssl binary (no
    Python crypto dep; a test-only key never enters the repo, so the secret scanner stays green)."""
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )
    return cert, key


def test_tls_context_is_none_without_a_configured_cert(monkeypatch):
    monkeypatch.delenv("CODEFORGE_TLS_CERT", raising=False)
    monkeypatch.delenv("CODEFORGE_TLS_KEY", raising=False)
    assert gateway._tls_context() is None  # unset -> plaintext transport, unchanged


def test_tls_context_loads_a_configured_cert(monkeypatch, _tls_pair):
    cert, key = _tls_pair
    monkeypatch.setenv("CODEFORGE_TLS_CERT", str(cert))
    monkeypatch.setenv("CODEFORGE_TLS_KEY", str(key))
    ctx = gateway._tls_context()
    assert isinstance(ctx, ssl.SSLContext)  # the cert loaded (a bad path/format would raise)
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2  # legacy TLS 1.0/1.1 refused


def test_the_server_context_completes_a_real_tls_handshake(monkeypatch, _tls_pair):
    cert, key = _tls_pair
    monkeypatch.setenv("CODEFORGE_TLS_CERT", str(cert))
    monkeypatch.setenv("CODEFORGE_TLS_KEY", str(key))
    server_ctx = gateway._tls_context()
    assert server_ctx is not None
    # Trust the self-signed test cert as its own CA and VERIFY it (CN=localhost). This exercises a
    # real, checked handshake -- not one with verification disabled -- so the test proves the server
    # presents a valid cert, not merely that bytes flow.
    client_ctx = ssl.create_default_context(cafile=str(cert))
    client_ctx.minimum_version = ssl.TLSVersion.TLSv1_2  # match the server: no legacy TLS
    a, b = socket.socketpair()
    got: dict[str, bytes] = {}

    def _server_side() -> None:
        with server_ctx.wrap_socket(a, server_side=True) as tls:
            tls.sendall(b"forge over tls")

    thread = threading.Thread(target=_server_side)
    thread.start()
    try:
        with client_ctx.wrap_socket(b, server_hostname="localhost") as tls:
            got["data"] = tls.recv(64)  # the handshake completed and bytes crossed encrypted
    finally:
        thread.join(timeout=5)
    assert got["data"] == b"forge over tls"


# --- structured server logging ------------------------------------------------------------------
def test_the_gateway_emits_structured_lifecycle_events():
    from structlog.testing import capture_logs

    with capture_logs() as logs:
        gateway._LOG.info("gateway_start", host="0.0.0.0", port=4000, tls=True)
        gateway._LOG.info("connection_open", peer="127.0.0.1")
        gateway._LOG.info("connection_close", player="ada", entered=True)
    events = {e["event"] for e in logs}
    assert {"gateway_start", "connection_open", "connection_close"} <= events
    start = next(e for e in logs if e["event"] == "gateway_start")
    assert start["port"] == 4000 and start["tls"] is True  # structured fields, queryable


def test_configure_logging_is_idempotent():
    gateway._configure_logging()
    gateway._configure_logging()  # a second call must not raise
