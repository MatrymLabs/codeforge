"""Test twin for parts/web_gateway.py -- the browser gate, over a real
ASGI WebSocket. The same door (handle_command) proven reachable from a
fourth transport: connect, clear the front desk, drive the tick."""

import contextlib

import pytest
from fastapi.testclient import TestClient

import parts.web_gateway as web
from parts import doors, items, npcs
from parts.accounts import account_password_ok
from parts.session import SESSIONS
from parts.web_gateway import app


def _register_and_enter(ws, handle: str = "hero@co") -> None:
    ws.receive_text()  # splash
    ws.receive_text()  # front-desk prompt
    ws.send_text("new")
    ws.receive_text()  # character@account prompt
    ws.send_text(handle)
    ws.receive_text()  # password prompt
    ws.send_text("swordfish9")
    ws.receive_text()  # welcome
    ws.receive_text()  # scene


@pytest.fixture(autouse=True)
def fresh_world():
    import copy

    items_snap = copy.deepcopy(items.ITEMS)
    doors_snap = copy.deepcopy(doors.DOORS)
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    web._web_seats = 0
    yield
    items.ITEMS.clear()
    items.ITEMS.update(items_snap)
    doors.DOORS.clear()
    doors.DOORS.update(doors_snap)
    npcs.NPCS.clear()
    npcs.NPCS.update(npcs_snap)
    SESSIONS.clear()


def test_health_reports_the_web_surface():
    body = TestClient(app).get("/health").json()
    assert body["status"] == "alive"
    assert body["surface"] == "web"


def test_index_serves_the_browser_client():
    page = TestClient(app).get("/").text
    assert "CodeForge" in page
    assert "/ws" in page  # the client dials the websocket
    assert "xterm" in page  # the terminal it renders into


def test_empty_input_is_refused_login_is_required():
    """Guest access was removed: an empty line re-prompts, never enters."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        assert "T H E   F I R S T   F O R G E" in ws.receive_text()  # splash first
        assert "Character" in ws.receive_text()  # the front-desk prompt
        ws.send_text("")  # just hit Enter
        assert "Login required" in ws.receive_text()  # refused
        assert "Character" in ws.receive_text()  # re-prompted, not seated


def test_register_over_the_wire_creates_an_account_and_enters():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()  # splash
        ws.receive_text()  # "Character (character@account) or NEW:"
        ws.send_text("new")
        assert "character@account" in ws.receive_text()
        ws.send_text("webhero@webco")
        assert "password" in ws.receive_text().lower()
        ws.send_text("swordfish9")  # >= 8, clears the password floor
        assert "Welcome, Webhero@webco" in ws.receive_text()
        assert "The Cold Forge" in ws.receive_text()  # scene after entry
        ws.send_text("help")
        assert "Commands:" in ws.receive_text()  # the tick is reachable
    assert account_password_ok("webco", "swordfish9")  # it really persisted


def test_quit_delivers_the_farewell_before_the_socket_closes():
    """Teardown flushes the outbox: the last line (the quit farewell) must
    reach the visitor, not get cut off by the close."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()  # splash
        ws.receive_text()  # prompt
        ws.send_text("new")
        ws.receive_text()  # choose character@account
        ws.send_text("byebye@byeco")
        ws.receive_text()  # choose a password
        ws.send_text("swordfish9")
        ws.receive_text()  # welcome
        ws.receive_text()  # scene
        ws.send_text("quit")
        assert "world dims" in ws.receive_text().lower()


def test_a_wrong_password_is_refused_then_the_door_reprompts():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()  # splash
        ws.receive_text()  # prompt
        ws.send_text("nobody@nowhere")
        assert "password" in ws.receive_text().lower()
        ws.send_text("wrongpassword")
        assert "do not align" in ws.receive_text()
        assert "NEW" in ws.receive_text().upper()  # re-prompted, not booted


def test_full_gate_turns_visitors_away_when_seated_out():
    web._web_seats = web.MAX_CONNECTIONS
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        assert "full" in ws.receive_text().lower()


def test_a_failed_connection_setup_frees_the_seat(monkeypatch):
    """A client aborting mid-handshake (routine on a public link) must not leak its seat -
    otherwise the counter climbs forever and the demo turns everyone away. The seat is claimed
    inside the try/finally, so setup blowing up still frees it."""

    def boom(*args, **kwargs):
        raise RuntimeError("client aborted the handshake")

    monkeypatch.setattr(web, "bind_echo", boom)  # a setup step fails after the seat is claimed
    client = TestClient(app)
    with contextlib.suppress(Exception), client.websocket_connect("/ws") as ws:
        ws.receive_text()
    assert web._web_seats == 0  # freed despite the failure (previously leaked to 1)


def test_a_broadcast_cannot_inject_terminal_escapes(monkeypatch):
    """The public web edge sanitizes every outbound line (like the TCP gateway's _send), so
    player chat can't push terminal-hijacking escape sequences to another visitor's xterm.js.
    Proven via the shouter's own echo, which rides the same sanitized transport edge."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        _register_and_enter(ws, "shouter@co")
        ws.send_text("shout hello\x1b[2J\x1b]0;PWNED\x07world")
        echo = ws.receive_text()  # the "You shout ..." echo, back through the sanitized _pump
        assert "\x1b" not in echo and "\x07" not in echo  # no raw escape / BEL reached the terminal
        assert "hello" in echo and "world" in echo  # the text survived, only escapes were stripped
