"""Test twin for adapters/gateway.py -- the front desk, over real sockets."""

import copy
import os
import re
import socket
import ssl
import subprocess
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

import adapters.gateway as gateway
from adapters.gateway import ForgeGateServer, _GateHandler, _sanitize
from kernel.session_registry import FileSessionRegistry, SessionRegistryError
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


def _read_until_contains(sock: socket.socket, marker: bytes) -> str:
    data = b""
    while marker not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data.decode("utf-8", errors="ignore")


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


def _live_runtime(path, seed_id, consumer, ledger_path, *, activate=True):
    """Build one explicitly trusted runtime for a live gateway proof."""
    from kernel.hardware_activation import ActivationApproval, ActivationApprovalLedger
    from kernel.hardware_lifecycle import HardwareRegistry
    from kernel.hardware_runtime import HardwareRuntimeController
    from kernel.permission_policy import PermissionPolicy, PermissionRule
    from kernel.session_identity import SessionIdentity
    from kernel.shelf.plugin_registry import PluginInfo, PluginRegistry

    hardware = HardwareRegistry(path)
    if hardware.get("validator") is None:
        hardware.discover("validator")
        for state in ("validated", "approved", "installed"):
            hardware.transition("validator", state)
    runtime = HardwareRuntimeController(
        hardware, PluginRegistry(), seed_id=seed_id, consumer=consumer
    )
    runtime.register_provider(PluginInfo("validator"), object)
    now = datetime(2026, 8, 5, 18, 0, tzinfo=UTC)
    identity = SessionIdentity(
        "operator",
        "human",
        f"session-{seed_id}",
        seed_id,
        now - timedelta(minutes=1),
        now + timedelta(minutes=30),
        f"corr-{seed_id}",
        roles=frozenset({"operator"}),
        capabilities=frozenset({"component.activate", "component.restore", "component.disable"}),
    )
    policy = PermissionPolicy(
        tuple(
            PermissionRule(capability, scope=seed_id)
            for capability in ("component.activate", "component.restore", "component.disable")
        )
    )
    if activate:
        runtime.activate(
            "validator",
            approval=ActivationApproval(
                f"approval-{seed_id}",
                "validator",
                hardware.get("validator").version,
                seed_id,
                "reviewer",
                (now + timedelta(minutes=5)).isoformat(),
            ),
            ledger=ActivationApprovalLedger(ledger_path),
            identity=identity,
            policy=policy,
            now=now,
        )
    return hardware, runtime, identity, policy


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


def _drain_to_close_after_command(sock: socket.socket, text: str) -> str:
    _line(sock, text)
    return _drain_to_close(sock)


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


def test_aethryn_new_character_gets_a_calling_menu_and_persists_choice(server, monkeypatch):
    """Aethryn's network creation path chooses a calling before the new hero enters the world."""
    from kernel.world.characters import load_character

    monkeypatch.setattr(gateway, "SEED_NAME", "aethryn")
    sock = _connect(server)
    _read_until(sock, b"NEW: ")
    _line(sock, "new")
    _read_until(sock, b"account: ")
    _line(sock, "aethrynmenu@aethrynco")
    menu = _read_until(sock, b"Calling (name): ")
    assert "CHARACTER CREATION" in menu
    assert "vanguard" in menu
    _line(sock, "vanguard")
    _read_until(sock, b"Skin color: ")
    _line(sock, "copper")
    _read_until(sock, b"password: " + bytes([255, 251, 1]))
    _line(sock, "swordfish9")
    scene = _read_until(sock, b"> ")
    assert "Welcome, Aethrynmenu@aethrynco" in scene
    assert "way of the Vanguard" in scene
    assert load_character("aethrynmenu")["job"] == "vanguard"
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


def _login(
    srv: ForgeGateServer,
    char="matrym",
    account="matlabs",
    pw="swordfish",
    *,
    timeout: float = 3.0,
) -> socket.socket:
    """Connect and clear the front desk into the world as an account."""
    sock = _connect(srv)
    sock.settimeout(timeout)
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
    assert b"Seed.Profile" in out and b"Observation Log" in out
    expected_seed = os.environ.get("FORGE_SEED", "first-forge")
    assert f'"seed":"{expected_seed}"'.encode() in out
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


# --- the additive engineering-workspace wire (owner creates a Seed over GMCP) ---------------------

_PW_PROMPT = b"Password: " + bytes([255, 251, 1])


def _saved_owner(char="wren", account="forge", pw="swordfish"):
    """A saved OWNER-ranked account: the in-MUD `workspace` verb and the gateway wire are both
    owner-gated (authorization before capability)."""
    hero = Session(player_id=char, location="courtyard", named=True, account=account)
    hero.rank = "owner"
    SESSIONS[char] = hero
    save_character(hero)
    SESSIONS.clear()
    register_account(f"{account}_seed", account, pw)
    adopt(char, account)


def _login_gmcp(srv, char, account, pw="swordfish"):
    """Connect with GMCP enabled and clear the front desk; returns (sock, bytes seen up to the
    first prompt) so a test can assert what was pushed on entry."""
    sock = _connect(srv)
    sock.sendall(_DO_GMCP)
    _read_until(sock, b"NEW: ")
    _line(sock, f"{char}@{account}")
    _read_until_raw(sock, _PW_PROMPT)
    _line(sock, pw)
    return sock, _read_until_raw(sock, b"> ")


def test_authenticated_gmcp_receives_one_server_session_identity_and_revocation(tmp_path):
    registry = FileSessionRegistry(tmp_path / "sessions")
    server = ForgeGateServer(("127.0.0.1", 0), _GateHandler, session_registry=registry)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        _saved_hero_with_calling()
        sock, out = _login_gmcp(server, "mira", "mlabs")
        try:
            assert out.count(b"Core.Session") == 1
            assert b'Core.Session {"principal_id":"mlabs"' in out
            assert b'"capabilities":["game.command"]' in out
            assert b'"seed_id":"first-forge"' in out
            assert len(list(registry.root.glob("*.json"))) == 1
        finally:
            sock.close()
        for _ in range(20):
            records = list(registry.root.glob("*.json"))
            if records and registry.load(records[0].stem).state == "invalidated":
                break
            time.sleep(0.05)
        else:
            pytest.fail("gateway did not revoke the published session identity")
    finally:
        server.shutdown()
        server.server_close()


def test_an_owner_login_pushes_the_creation_form_over_gmcp(server, tmp_path, monkeypatch):
    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    _saved_owner()
    sock, out = _login_gmcp(server, "wren", "forge")
    assert _SB_GMCP in out and b"Form.Schema" in out  # the Wizard's creation Form, as data
    assert b"product_types" in out  # the Form projects its product types
    sock.close()


def test_an_owner_login_serves_the_reference_read_workspace(server, tmp_path, monkeypatch):
    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    _saved_owner()
    sock, out = _login_gmcp(server, "wren", "forge")
    # the reference Seed's REAL read panels light up from the running server, not just a fixture
    assert b"Architecture.Map" in out and b"module_count" in out  # the engine's own module registry
    assert b"Blueprint.List" in out and b"blueprint_count" in out  # its filed Blueprints
    sock.close()


def test_an_owner_login_pushes_live_engineering_evidence(server, tmp_path, monkeypatch):
    """CF-205: the live gateway projects a real Workshop write into Engineering.Evidence."""
    from kernel.seedlab.kernel import SeedKernel
    from kernel.seedlab.registry import configured_seed_store
    from kernel.seedlab.workshop_services import CreatorWorkshopService

    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    kernel = SeedKernel(configured_seed_store(tmp_path))
    kernel.create_seed("First Forge", "matrym", "live evidence proof", seed_id="first-forge")
    CreatorWorkshopService.durable(tmp_path / "workshop").create_draft(
        "gateway-draft", "first-forge", "matrym", {"command": "inspect"}
    )
    _saved_owner()
    sock, out = _login_gmcp(server, "wren", "forge")
    try:
        assert b"Engineering.Evidence" in out
        assert b'"catalog"' in out
        assert b'"draft_id":"gateway-draft"' in out
    finally:
        sock.close()


def test_a_non_owner_login_gets_no_workspace_packages(server, tmp_path, monkeypatch):
    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    _saved_account()  # a default player-rank account
    sock, out = _login_gmcp(server, "matrym", "matlabs")
    # the workspace surface is owner-gated: a player sees neither the Form nor the read panels
    assert b"Form.Schema" not in out
    assert b"Architecture.Map" not in out and b"Blueprint.List" not in out
    sock.close()


def test_an_owner_creates_a_seed_over_gmcp_and_gets_its_workspace(server, tmp_path, monkeypatch):
    from kernel.gmcp import gmcp_frame

    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    _saved_owner()
    sock, _ = _login_gmcp(server, "wren", "forge")
    submit = {
        "product_type": "training",
        "answers": {
            "name": "Onboarding",
            "purpose": "train new hires",  # owner is injected server-side (authenticated account)
            "scenarios": "server outage drill",
            "competencies": "incident response",
            "certification": True,
        },
    }
    sock.sendall(gmcp_frame("Form.Submit", submit) + b"\n")  # a newline gives readline its boundary
    out = _read_until_raw(sock, b"> ")
    assert b"Seed.Created" in out and b'"ok":true' in out  # the engine minted the Seed
    assert b'"correlation_id":"gateway-seed-create-wren"' in out
    assert b"Project.Status" in out and b"Onboarding" in out  # its workspace was pushed back
    assert list((tmp_path / "seeds").glob("*.json"))  # and it persisted to the file store
    sock.close()


def test_owner_seed_creation_emits_a_traceable_gateway_log(server, tmp_path, monkeypatch):
    from kernel.gmcp import gmcp_frame

    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    _saved_owner()
    submit = {
        "product_type": "training",
        "answers": {
            "name": "Logged Onboarding",
            "purpose": "trace gateway creation",
            "scenarios": "structured logs",
            "competencies": "correlation",
            "certification": False,
        },
    }
    logs = []

    def record_log(event, identity, **fields):
        logs.append(
            {
                "event": event,
                "correlation_id": identity.correlation_id,
                "session_id": identity.session_id,
                "seed_id": identity.seed_id,
                "worker_id": "gateway",
                **fields,
            }
        )

    monkeypatch.setattr(gateway, "_log_trace_event", record_log)
    sock, _ = _login_gmcp(server, "wren", "forge")
    try:
        sock.sendall(gmcp_frame("Form.Submit", submit) + b"\n")
        _read_until_raw(sock, b"> ")
    finally:
        sock.close()

    event = next(item for item in logs if item["event"] == "workspace_seed_create")
    assert event["correlation_id"] == "gateway-seed-create-wren"
    assert event["seed_id"] == "seedlab"
    assert event["worker_id"] == "gateway"
    assert event["status"] == "accepted"
    assert "password" not in str(event).lower()


def test_repeated_owner_form_submit_is_idempotent_over_gmcp(server, tmp_path, monkeypatch):
    from kernel.gmcp import gmcp_frame

    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    _saved_owner()
    sock, _ = _login_gmcp(server, "wren", "forge")
    submit = {
        "product_type": "training",
        "answers": {
            "name": "Retryable Onboarding",
            "purpose": "train new hires",
            "scenarios": "server outage drill",
            "competencies": "incident response",
            "certification": True,
        },
    }

    sock.sendall(gmcp_frame("Form.Submit", submit) + b"\n")
    first = _read_until_raw(sock, b"> ")
    sock.sendall(gmcp_frame("Form.Submit", submit) + b"\n")
    second = _read_until_raw(sock, b"> ")

    seed_ids = [
        match.group(1)
        for response in (first, second)
        if (match := re.search(rb'Seed\.Created \{[^}]*"id":"([^"]+)"', response))
    ]
    assert len(seed_ids) == 2 and seed_ids[0] == seed_ids[1]
    assert b'"ok":true' in first and b'"ok":true' in second
    assert len(list((tmp_path / "seeds").glob("*.json"))) == 1
    sock.close()


def test_seed_create_over_gmcp_mints_a_seed(server, tmp_path, monkeypatch):
    from kernel.gmcp import gmcp_frame

    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    _saved_owner()
    sock, _ = _login_gmcp(server, "wren", "forge")
    sock.sendall(gmcp_frame("Seed.Create", {"name": "toolkit", "kind": "engineering"}) + b"\n")
    out = _read_until_raw(sock, b"> ")
    assert b"Seed.Created" in out and b'"ok":true' in out and b"Project.Status" in out
    sock.close()


def test_a_non_owner_is_refused_seed_creation_over_gmcp(server, tmp_path, monkeypatch):
    from kernel.gmcp import gmcp_frame

    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    _saved_account()  # a default player-rank account (matrym@matlabs)
    sock, out = _login_gmcp(server, "matrym", "matlabs")
    assert b"Form.Schema" not in out  # the creation Form is owner-gated: a player never sees it
    sock.sendall(gmcp_frame("Seed.Create", {"name": "sneaky", "kind": "engineering"}) + b"\n")
    reply = _read_until_raw(sock, b"> ")
    assert b"Seed.Created" in reply and b'"ok":false' in reply  # refused, honestly
    assert b"requires owner rank" in reply
    assert b"Project.Status" not in reply  # nothing was created or served
    assert not list((tmp_path / "seeds").glob("*.json"))  # no Seed on disk
    sock.close()


# --- _read_message: the out-of-band subnegotiation reader (bare GMCP frames, no newline) ----------


def _read_until_in(sock: socket.socket, marker: bytes, limit: int = 25) -> bytes:
    """Read until `marker` appears anywhere in the stream (a GMCP frame ends in IAC SE, not the
    marker, so `endswith` will not do)."""
    data = b""
    for _ in range(limit):
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
        if marker in data:
            break
    return data


def test_read_message_returns_a_line_at_the_newline():
    import io

    from adapters.gateway import _read_message

    assert _read_message(io.BytesIO(b"look\nmore"), 1024) == (b"look\n", False)


def test_read_message_returns_a_bare_gmcp_frame_before_any_newline():
    import io

    from adapters.gateway import _read_message
    from kernel.gmcp import gmcp_frame

    frame = gmcp_frame("Form.Submit", {"product_type": "training", "answers": {}})
    reader = io.BytesIO(frame + b"look\n")  # a bare out-of-band frame, THEN a command line
    assert _read_message(reader, 1024) == (
        frame,
        True,
    )  # the frame returns first (no newline waited)
    assert _read_message(reader, 1024) == (b"look\n", False)  # then the command line


def test_read_message_keeps_glued_negotiation_inside_the_line():
    import io

    from adapters.gateway import _read_message

    line = bytes([255, 253, 201]) + b"mira@mlabs\n"  # IAC DO GMCP glued before the login line
    assert _read_message(io.BytesIO(line), 1024) == (line, False)  # whole line, negotiation intact


def test_read_message_does_not_early_return_on_a_non_gmcp_subnegotiation():
    import io

    from adapters.gateway import _read_message

    naws = bytes([255, 250, 31, 0, 80, 0, 24, 255, 240])  # IAC SB NAWS ... IAC SE (option 31)
    reader = io.BytesIO(naws + b"look\n")
    # NAWS is not GMCP, so it is read through to the newline as a line (as before), never a frame
    assert _read_message(reader, 1024) == (naws + b"look\n", False)


def test_read_message_at_eof_returns_what_it_has_as_a_line():
    import io

    from adapters.gateway import _read_message

    assert _read_message(io.BytesIO(b"partial"), 1024) == (b"partial", False)  # no newline, EOF


def test_read_message_respects_the_size_cap():
    import io

    from adapters.gateway import _read_message

    msg, is_frame = _read_message(io.BytesIO(b"x" * 100), 10)
    assert (
        len(msg) == 10 and is_frame is False
    )  # a flood with no newline is capped, treated as line


def test_a_bare_out_of_band_form_submit_is_served_without_a_newline(server, tmp_path, monkeypatch):
    from kernel.gmcp import gmcp_frame

    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    _saved_owner()
    sock, _ = _login_gmcp(server, "wren", "forge")
    submit = {
        "product_type": "training",
        "answers": {
            "name": "OOB",
            "purpose": "prove out-of-band",
            "scenarios": "drill",
            "competencies": "response",
            "certification": True,
        },
    }
    sock.sendall(gmcp_frame("Form.Submit", submit))  # NO trailing newline: a true out-of-band frame
    out = _read_until_in(sock, b"Project.Status")
    assert b"Seed.Created" in out and b'"ok":true' in out  # the engine minted it, no newline needed
    assert b"Project.Status" in out and b"OOB" in out  # its workspace pushed back
    sock.close()


# --- Workspace.Request: pull the reference Seed's Deploy.Manifest on demand (a chosen tier) -------


def test_an_owner_workspace_request_serves_the_deploy_manifest(server, tmp_path, monkeypatch):
    from kernel.gmcp import gmcp_frame

    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    _saved_owner()
    sock, _ = _login_gmcp(server, "wren", "forge")
    sock.sendall(
        gmcp_frame("Workspace.Request", {"tier": "prototype"})
    )  # a bare out-of-band request
    out = _read_until_in(sock, b"Deploy.Manifest")
    assert b"Deploy.Manifest" in out and b"prototype" in out  # the deploy panel's data, on demand
    assert b"target_players" in out  # the real derived sizing
    sock.close()


def test_a_workspace_request_defaults_the_tier_when_none_is_given(server, tmp_path, monkeypatch):
    from kernel.gmcp import gmcp_frame

    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    _saved_owner()
    sock, _ = _login_gmcp(server, "wren", "forge")
    sock.sendall(gmcp_frame("Workspace.Request", {}))  # no tier -> the default (prototype)
    out = _read_until_in(sock, b"Deploy.Manifest")
    assert b"Deploy.Manifest" in out and b"prototype" in out
    sock.close()


def test_an_unknown_tier_is_an_honest_no_op(server, tmp_path, monkeypatch):
    from kernel.gmcp import gmcp_frame

    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    _saved_owner()
    sock, _ = _login_gmcp(server, "wren", "forge")
    # a valid ping so the read has something to stop on, then the bad request should add nothing
    sock.sendall(gmcp_frame("Workspace.Request", {"tier": "galactic"}))  # not a modelled tier
    sock.sendall(b"look\n")
    out = _read_until_raw(sock, b"> ")
    assert (
        b"Deploy.Manifest" not in out
    )  # a tier the engine does not model serves nothing, honestly
    sock.close()


def test_a_non_owner_workspace_request_is_silently_ignored(server, tmp_path, monkeypatch):
    from kernel.gmcp import gmcp_frame

    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    _saved_account()  # a player-rank account
    sock, _ = _login_gmcp(server, "matrym", "matlabs")
    sock.sendall(gmcp_frame("Workspace.Request", {"tier": "prototype"}))
    sock.sendall(b"look\n")
    out = _read_until_raw(sock, b"> ")
    assert (
        b"Deploy.Manifest" not in out
    )  # owner-gated: a player gets no workspace, no verdict noise
    sock.close()


# --- Research.Findings served from a MOUNTED manifest on a Workspace.Request (the FGL pattern) ----


def test_a_mounted_research_manifest_is_served_on_a_workspace_request(
    server, tmp_path, monkeypatch
):
    import json as _json

    from kernel.gmcp import gmcp_frame

    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    (tmp_path / "research.json").write_text(
        _json.dumps([{"id": "EXP-05", "title": "FTS5", "verdict": "verified improvement"}]),
        encoding="utf-8",
    )
    _saved_owner()
    sock, _ = _login_gmcp(server, "wren", "forge")
    sock.sendall(gmcp_frame("Workspace.Request", {}))
    out = _read_until_in(sock, b"Research.Findings")
    assert (
        b"Research.Findings" in out and b"EXP-05" in out
    )  # the mounted research, served on request
    sock.close()


def test_an_unmounted_research_source_serves_no_findings(server, tmp_path, monkeypatch):
    from kernel.gmcp import gmcp_frame

    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))  # no research.json mounted here
    _saved_owner()
    sock, _ = _login_gmcp(server, "wren", "forge")
    sock.sendall(gmcp_frame("Workspace.Request", {"tier": "prototype"}))
    sock.sendall(b"look\n")  # a boundary so we capture the whole response
    out = _read_until_raw(sock, b"> ")
    assert b"Deploy.Manifest" in out  # deploy is still served
    assert b"Research.Findings" not in out  # honest: no mount, no findings, an empty panel
    sock.close()


# --- Deploy.Status: the running instance's own live status on a Workspace.Request (7b) ------------


def test_a_workspace_request_serves_the_instance_deploy_status(server, tmp_path, monkeypatch):
    from kernel.gmcp import gmcp_frame

    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    _saved_owner()
    sock, _ = _login_gmcp(server, "wren", "forge")
    sock.sendall(gmcp_frame("Workspace.Request", {}))
    out = _read_until_in(sock, b"Deploy.Status")
    assert b"Deploy.Status" in out  # the running instance reports itself
    assert b'"version":' in out and b'"connections":' in out  # real self-facts, not a cloud URL
    assert b'"seed":"' in out and b'"uptime_seconds":' in out
    sock.close()


def test_live_master_client_workspace_flow_survives_gateway_restart(server, tmp_path, monkeypatch):
    """The first live SeedLab vertical slice: the Master Client's text commands and GMCP panels
    cross a real gateway, and the Seed remains addressable after a fresh gateway reads the same
    file-backed workspace. The source is deliberately tiny, but pytest is a real subprocess run.
    """
    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path / "lab"))
    source = tmp_path / "source"
    (source / "sample").mkdir(parents=True)
    (source / "sample" / "__init__.py").write_text("VALUE = 42\n", encoding="utf-8")
    (source / "test_smoke.py").write_text(
        "def test_smoke():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )
    (source / "pyproject.toml").write_text(
        "[project]\nname = 'live-seedlab-source'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )

    _saved_owner()
    sock, _ = _login_gmcp(server, "wren", "forge")
    try:
        created = _command(sock, "workspace create LiveFlow prove the live platform loop")
        seed_match = re.search(rb"seed-[a-z0-9-]+", created.encode())
        assert seed_match is not None
        seed_id = seed_match.group().decode()
        assert b"Project.Status" in created.encode() and b"LiveFlow" in created.encode()

        connected = _command(sock, f"workspace connect {seed_id} {source}")
        assert b"Source.Tree" in connected.encode()
        assert b"Source.Connection" in connected.encode()
        assert b"Model.Schema" in connected.encode()
        assert b"sample" in connected.encode()

        modeled = _command(sock, f"workspace model {seed_id}")
        assert b"Model.Schema" in modeled.encode() and b"live-seedlab-source" in modeled.encode()

        built = _command(sock, f"workspace run {seed_id} {source} pytest")
        assert b"Build.Report" in built.encode() and b"1 passed" in built.encode()

        reported = _command(sock, f"workspace report {seed_id}")
        assert b"Build.Report" in reported.encode() and b"1 run(s), 1 ok" in reported.encode()

        assert b"RUNNING" in _command(sock, f"workspace start {seed_id}").encode()
        backed_up = _command(sock, f"workspace backup {seed_id}")
        backup_match = re.search(r"bk-[A-Za-z0-9_.-]+", backed_up)
        assert backup_match is not None
        backup_id = backup_match.group()
        assert b"STOPPED" in _command(sock, f"workspace stop {seed_id}").encode()
        restored = _command(sock, f"workspace restore {seed_id} {backup_id}")
        assert b"RUNNING" in restored.encode() and b"Project.Status" in restored.encode()
    finally:
        sock.close()

    # A second listening gateway over the same SEEDLAB_HOME proves recovery through the actual
    # server boundary, not merely a fresh Kernel object inside the unit test.
    recovered = ForgeGateServer(("127.0.0.1", 0), _GateHandler)
    threading.Thread(target=recovered.serve_forever, daemon=True).start()
    try:
        fresh, _ = _login_gmcp(recovered, "wren", "forge")
        try:
            status = _command(fresh, f"workspace status {seed_id}")
            assert b"RUNNING" in status.encode() and b"LiveFlow" in status.encode()
        finally:
            fresh.close()
    finally:
        recovered.shutdown()
        recovered.server_close()


def test_native_aethryn_client_journey_publishes_and_recovers_workshop_state(
    server, tmp_path, monkeypatch
):
    """The native Seed journey crosses the real gateway and survives a fresh boot.

    The client uses the live text projection for movement and Workshop actions while GMCP carries
    the Seed profile and room state.  Hardware inspection is read-only; publication is the
    Creator Workshop's canonical overlay write.  Clearing the in-memory item and replaying that
    overlay before a second gateway starts mirrors the world assembly recovery path.
    """
    from kernel.world import creator_workshop as workshop
    from kernel.world import items

    monkeypatch.setenv("CODEFORGE_WORKSHOP_STATE", str(tmp_path / "aethryn-workshop.json"))
    workshop.clear_published_state()
    _saved_owner()
    sock, entered = _login_gmcp(server, "wren", "forge")
    try:
        # The helper intentionally consumes the pre-login handshake while waiting for NEW; the
        # Native Seed profile itself is covered by the dedicated handshake test above.  Entry still
        # carries the live room projection.
        assert b"Room.Info" in entered and b"courtyard" in entered

        navigated = _command(sock, "go south")
        assert b"The Cold Forge" in navigated.encode()
        navigated = _command(sock, "go library")
        assert b"The Grand Library" in navigated.encode()
        crossed = _command(sock, "go door")
        assert b"The Creator's Workshop" in crossed.encode()

        inspected = _command(sock, "look")
        assert b"Creator's Workshop" in inspected.encode()
        hardware = _command(sock, "hardware")
        assert b"HARDWARE CATALOG" in hardware.encode() and b"rank-gate" in hardware.encode()
        functions = _command(sock, "functions")
        assert b"FUNCTIONS CHECK" in functions.encode() and b"tested" in functions.encode()

        entered_forge = _command(sock, "go items")
        assert b"Item Forge" in entered_forge.encode()
        staged = _command(sock, "create item Native Journey Lantern at courtyard")
        assert b"Staged" in staged.encode() and b"Native Journey Lantern" in staged.encode()
        preview = _command(sock, "preview")
        assert b"not yet live" in preview.encode() and b"Native Journey Lantern" in preview.encode()

        _command(sock, "go hall")
        _command(sock, "go publish")
        published = _command(sock, "publish")
        assert b"Published to the living world" in published.encode()
        assert any(item["name"] == "Native Journey Lantern" for item in items.ITEMS.values())

        _command(sock, "go hall")
        _command(sock, "go out")
        _command(sock, "go out")
        recovered_location = _command(sock, "go north")
        assert b"Broken Courtyard" in recovered_location.encode()
    finally:
        sock.close()

    # Simulate the next world assembly from the durable Workshop overlay, not from the old process
    # memory.  The exact item is absent before replay and present again after replay.
    created_label = next(
        item_label
        for item_label, item in items.ITEMS.items()
        if item["name"] == "Native Journey Lantern"
    )
    items.ITEMS.pop(created_label)
    assert not any(item["name"] == "Native Journey Lantern" for item in items.ITEMS.values())
    assert workshop.restore_published_changes() == 1

    recovered = ForgeGateServer(("127.0.0.1", 0), _GateHandler)
    threading.Thread(target=recovered.serve_forever, daemon=True).start()
    try:
        fresh, _ = _login_gmcp(recovered, "wren", "forge")
        try:
            scene = _command(fresh, "look")
            assert b"Broken Courtyard" in scene.encode()
            assert b"Native Journey Lantern" in scene.encode()
        finally:
            fresh.close()
    finally:
        recovered.shutdown()
        recovered.server_close()
        workshop.clear_published_state()


def test_live_gateway_runtime_reports_restart_recovery_and_independent_seed_binding(tmp_path):
    """CF-204: a real authenticated gateway sees durable runtime state after restart.

    Aethryn and First Forge use separate registries, so disabling one Seed's binding cannot
    silently disable the other Seed's component.  The command is read-only; activation and
    recovery happen through the governed controller before the socket boundary is opened.
    """
    ledger = tmp_path / "approvals.json"
    aethryn_path = tmp_path / "aethryn-hardware.json"
    _hardware, aethryn_runtime, identity, policy = _live_runtime(
        aethryn_path, "aethryn", "aethryn", ledger
    )
    first = ForgeGateServer(("127.0.0.1", 0), _GateHandler, hardware_runtime=aethryn_runtime)
    threading.Thread(target=first.serve_forever, daemon=True).start()
    try:
        _saved_account("runtimeaethryn", "runtimeaethrynco")
        sock = _login(first, "runtimeaethryn", "runtimeaethrynco")
        try:
            live = _command(sock, "hardware runtime")
            assert "HARDWARE RUNTIME" in live
            assert "seed: aethryn" in live
            assert "active bindings: validator" in live
            assert "validator: active" in live
        finally:
            sock.close()
    finally:
        first.shutdown()
        first.server_close()

    recovered_hardware, recovered_runtime, _identity, _policy = _live_runtime(
        aethryn_path, "aethryn", "aethryn", ledger, activate=False
    )
    # The helper starts from an installed record, so use the durable registry and explicitly
    # restore the already-active binding instead of activating it a second time.
    recovered_runtime.restore_active(
        "validator", identity=identity, policy=policy, now=datetime(2026, 8, 5, 18, 0, tzinfo=UTC)
    )
    restarted = ForgeGateServer(("127.0.0.1", 0), _GateHandler, hardware_runtime=recovered_runtime)
    threading.Thread(target=restarted.serve_forever, daemon=True).start()
    try:
        _saved_account("runtimerestart", "runtimerestartco")
        sock = _login(restarted, "runtimerestart", "runtimerestartco")
        try:
            recovered = _command(sock, "hardware runtime")
            assert "seed: aethryn" in recovered
            assert "active bindings: validator" in recovered
            assert "consumers: aethryn" in recovered
        finally:
            sock.close()
    finally:
        restarted.shutdown()
        restarted.server_close()

    _forge_hardware, forge_runtime, _forge_identity, _forge_policy = _live_runtime(
        tmp_path / "first-forge-hardware.json", "first-forge", "first-forge", ledger
    )
    second = ForgeGateServer(("127.0.0.1", 0), _GateHandler, hardware_runtime=forge_runtime)
    threading.Thread(target=second.serve_forever, daemon=True).start()
    try:
        _saved_account("runtimeforge", "runtimeforgeco")
        sock = _login(second, "runtimeforge", "runtimeforgeco")
        try:
            independent = _command(sock, "hardware runtime")
            assert "seed: first-forge" in independent
            assert "active bindings: validator" in independent
            assert "consumers: first-forge" in independent
        finally:
            sock.close()
    finally:
        second.shutdown()
        second.server_close()


def test_live_gateway_owner_can_disable_and_remove_its_hardware_binding(tmp_path):
    ledger = tmp_path / "approvals.json"
    hardware_path = tmp_path / "aethryn-hardware.json"
    hardware, runtime, _identity, _policy = _live_runtime(
        hardware_path, "aethryn", "aethryn", ledger
    )
    server = ForgeGateServer(("127.0.0.1", 0), _GateHandler, hardware_runtime=runtime)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        _saved_owner("hardwareowner", "howner")
        sock = _login(server, "hardwareowner", "howner")
        try:
            disabled = _command(sock, "hardware disable validator")
            assert "disabled" in disabled
            removed = _command(sock, "hardware remove validator")
            assert "removed" in removed
        finally:
            sock.close()
    finally:
        server.shutdown()
        server.server_close()

    record = hardware.get("validator")
    assert record.state == "disabled"
    assert record.consumers == ()
    assert runtime.active_names() == ()


def test_live_gateway_persists_and_revokes_authenticated_platform_session(tmp_path):
    registry = FileSessionRegistry(tmp_path / "sessions")
    server = ForgeGateServer(
        ("127.0.0.1", 0),
        _GateHandler,
        session_registry=registry,
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        _saved_owner("sessionowner", "sessionownerco")
        sock = _login(server, "sessionowner", "sessionownerco")
        try:
            records = list(registry.root.glob("*.json"))
            assert len(records) == 1
            identity = registry.load(records[0].stem).identity
            assert identity.principal_id == "sessionownerco"
            assert identity.seed_id == gateway.SEED_NAME
            registry.require_active(identity)
        finally:
            sock.close()
        for _ in range(20):
            try:
                registry.require_active(identity)
            except SessionRegistryError as exc:
                assert "invalidated" in str(exc)
                break
            time.sleep(0.05)
        else:
            pytest.fail("gateway did not persist session revocation after disconnect")
    finally:
        server.shutdown()
        server.server_close()


def test_live_gateway_denies_commands_after_platform_session_revocation(tmp_path):
    registry = FileSessionRegistry(tmp_path / "sessions")
    server = ForgeGateServer(
        ("127.0.0.1", 0),
        _GateHandler,
        session_registry=registry,
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        _saved_account("revokedcommand", "revokedcommandco")
        sock = _login(server, "revokedcommand", "revokedcommandco")
        try:
            record = next(registry.root.glob("*.json"))
            identity = registry.load(record.stem).identity
            registry.invalidate(
                identity.session_id,
                actor="test-operator",
                reason="authorization regression test",
            )
            response = _drain_to_close_after_command(sock, "look")
            assert "Session authority unavailable" in response
        finally:
            sock.close()
    finally:
        server.shutdown()
        server.server_close()


def test_character_location_survives_gateway_restart(tmp_path):
    """A real movement is saved, then loaded by a fresh gateway process boundary."""
    from uuid import uuid4

    from kernel.world.jobs import bind_calling
    from kernel.world.world import START_ROOM, WORLD

    expected_destination = WORLD[WORLD[START_ROOM]["exits"]["north"]]["name"]

    token = uuid4().hex[:6]
    character = f"reconnect{token}"
    account = f"reco{token}"
    password = "swordfish"
    hero = Session(player_id=character, location=START_ROOM, named=True, account=account)
    bind_calling(hero, "vanguard")
    SESSIONS[character] = hero
    save_character(hero)
    SESSIONS.clear()
    register_account(f"{account}_seed", account, password)
    adopt(character, account)

    registry = FileSessionRegistry(tmp_path / "sessions")
    first = ForgeGateServer(("127.0.0.1", 0), _GateHandler, session_registry=registry)
    threading.Thread(target=first.serve_forever, daemon=True).start()
    try:
        sock = _login(first, character, account, password, timeout=30.0)
        try:
            moved = _command(sock, "north")
            assert expected_destination in moved
        finally:
            sock.close()
    finally:
        first.shutdown()
        first.server_close()

    second = ForgeGateServer(("127.0.0.1", 0), _GateHandler, session_registry=registry)
    threading.Thread(target=second.serve_forever, daemon=True).start()
    try:
        sock = _login(second, character, account, password, timeout=30.0)
        try:
            restored = _command(sock, "look")
            assert expected_destination in restored
        finally:
            sock.close()
    finally:
        second.shutdown()
        second.server_close()


@pytest.mark.skipif(
    os.environ.get("FORGE_SEED", "").casefold() != "aethryn",
    reason="the live Aethryn journey requires FORGE_SEED=aethryn",
)
def test_live_aethryn_entry_navigation_combat_progression_and_restart(tmp_path):
    """Prove the next coherent player slice through the real Aethryn gateway boundary."""
    from uuid import uuid4

    from kernel.world.characters import load_character

    token = uuid4().hex[:6]
    character = f"journey{token}"
    account = f"journey{token}co"
    registry = FileSessionRegistry(tmp_path / "sessions")

    first = ForgeGateServer(("127.0.0.1", 0), _GateHandler, session_registry=registry)
    threading.Thread(target=first.serve_forever, daemon=True).start()
    try:
        sock = _connect(first)
        _read_until(sock, b"NEW: ")
        _line(sock, "new")
        _read_until(sock, b"account: ")
        _line(sock, f"{character}@{account}")
        creation = _read_until(sock, b"Calling (name): ")
        assert "CHARACTER CREATION" in creation
        _line(sock, "vanguard")
        _read_until(sock, b"Skin color: ")
        _line(sock, "copper")
        _read_until(sock, b"password: " + bytes([255, 251, 1]))
        _line(sock, "swordfish9")
        entered = _read_until(sock, b"> ")
        assert f"Welcome, {character.title()}@{account}" in entered
        assert "Veridia" in entered

        jobs = _command(sock, "jobs")
        assert "duelist" in jobs and "LOCKED" in jobs
        locked = _command(sock, "job duelist")
        assert "locked" in locked.lower() and "vanguard Lv 1/3" in locked

        east = _command(sock, "east")
        assert "Caeloria" in east
        west = _command(sock, "west")
        assert "Veridia" in west
        barrow = _command(sock, "go sunken")
        assert "Sunken Barrow" in barrow
        assert "barrow-rat" in _command(sock, "look")

        defeated = False
        for _ in range(8):
            outcome = _command(sock, "attack rat")
            if "You find" in outcome:
                defeated = True
                break
        assert defeated, "the authored level-2 Aethryn foe did not yield a combat reward"
        score = _command(sock, "score")
        assert "Vanguard" in score
        sock.close()
    finally:
        first.shutdown()
        first.server_close()

    saved = load_character(character)
    assert saved["location"] == "the_sunken_barrow"
    assert saved["job"] == "vanguard"
    assert saved["appearance"]

    second = ForgeGateServer(("127.0.0.1", 0), _GateHandler, session_registry=registry)
    threading.Thread(target=second.serve_forever, daemon=True).start()
    try:
        sock = _login(second, character, account, "swordfish9", timeout=30.0)
        try:
            restored = _command(sock, "look")
            assert "Sunken Barrow" in restored
            assert "Vanguard" in _command(sock, "score")
        finally:
            sock.close()
    finally:
        second.shutdown()
        second.server_close()


@pytest.mark.skipif(
    os.environ.get("FORGE_SEED", "").casefold() != "aethryn",
    reason="the live Aethryn journey requires FORGE_SEED=aethryn",
)
def test_live_aethryn_technique_item_equipment_social_and_exactly_once(tmp_path):
    """Prove the live command path for a Technique, gear ownership, equipment, and social output."""
    from uuid import uuid4

    from kernel.world.characters import load_character
    from kernel.world.jobs import bind_calling

    token = uuid4().hex[:6]
    character = f"gear{token}"
    account = f"gear{token}co"
    friend = f"friend{token}"
    friend_account = f"friend{token}co"
    password = "swordfish9"

    # Persist a second real character at the same room for a cross-session social observation.
    friend_session = Session(
        player_id=friend,
        location="the_sunken_barrow",
        named=True,
        account=friend_account,
    )
    bind_calling(friend_session, "vanguard")
    SESSIONS[friend] = friend_session
    save_character(friend_session)
    SESSIONS.pop(friend, None)
    register_account(f"{friend_account}_seed", friend_account, password)
    adopt(friend, friend_account)

    registry = FileSessionRegistry(tmp_path / "sessions")
    server = ForgeGateServer(("127.0.0.1", 0), _GateHandler, session_registry=registry)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    first_sock = None
    second_sock = None
    try:
        first_sock = _connect(server)
        _read_until(first_sock, b"NEW: ")
        _line(first_sock, "new")
        _read_until(first_sock, b"account: ")
        _line(first_sock, f"{character}@{account}")
        _read_until(first_sock, b"Calling (name): ")
        _line(first_sock, "vanguard")
        _read_until(first_sock, b"Skin color: ")
        _line(first_sock, "copper")
        _read_until(first_sock, b"password: " + bytes([255, 251, 1]))
        _line(first_sock, password)
        _read_until(first_sock, b"> ")

        assert "Ember Edge" in _command(first_sock, "skills")
        _command(first_sock, "go sunken")
        technique = _command(first_sock, "use ember edge on scout")
        assert "Ember Edge" in technique
        assert "hammer" in technique.lower()

        taken = _command(first_sock, "take hammer")
        assert "take" in taken.lower() and "hammer" in taken.lower()
        duplicate = _command(first_sock, "take hammer")
        assert (
            "not here" in duplicate.lower()
            or "aren't carrying" in duplicate.lower()
            or "don't see that here" in duplicate.lower()
        )
        inventory = _command(first_sock, "inventory")
        assert inventory.lower().count("hammer") == 1
        equipped = _command(first_sock, "equip hammer")
        assert "equip" in equipped.lower()
        assert "hammer" in _command(first_sock, "score").lower()

        second_sock = _login(server, friend, friend_account, password, timeout=30.0)
        second_room = _command(second_sock, "look")
        if "Sunken Barrow" not in second_room:
            second_room = _command(second_sock, "go sunken")
        assert "Sunken Barrow" in second_room
        _line(first_sock, "say Hello, Forge friend!")
        first_say = _read_until(first_sock, b"> ")
        second_say = _read_until_contains(second_sock, b"Forge friend!")
        assert "Hello, Forge friend!" in first_say
        assert "Hello, Forge friend!" in second_say
    finally:
        if second_sock is not None:
            second_sock.close()
        if first_sock is not None:
            first_sock.close()
        server.shutdown()
        server.server_close()

    saved = load_character(character)
    assert "cinder_hammer" in saved["equipped_gear"]
    assert saved["location"] == "the_sunken_barrow"

    restarted = ForgeGateServer(("127.0.0.1", 0), _GateHandler, session_registry=registry)
    threading.Thread(target=restarted.serve_forever, daemon=True).start()
    try:
        sock = _login(restarted, character, account, password, timeout=30.0)
        try:
            restored_inventory = _command(sock, "inventory")
            assert restored_inventory.lower().count("hammer") == 1
            assert "hammer" in _command(sock, "score").lower()
        finally:
            sock.close()
    finally:
        restarted.shutdown()
        restarted.server_close()
