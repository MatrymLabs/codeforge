"""Test twin for parts/web_gateway.py -- the browser gate, over a real
ASGI WebSocket. The same door (handle_command) proven reachable from a
fourth transport: connect, clear the front desk, drive the tick."""

import pytest
from fastapi.testclient import TestClient

import parts.web_gateway as web
from parts import doors, items, npcs
from parts.accounts import account_password_ok
from parts.session import SESSIONS
from parts.web_gateway import app


@pytest.fixture(autouse=True)
def fresh_world():
    import copy

    items_snap = copy.deepcopy(items.ITEMS)
    doors_snap = copy.deepcopy(doors.DOORS)
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    web._web_seats = 0
    yield
    items.ITEMS = items_snap
    doors.DOORS = doors_snap
    npcs.NPCS = npcs_snap
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


def test_guest_enters_the_world_and_the_tick_answers():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        assert "T H E   F I R S T   F O R G E" in ws.receive_text()  # splash first
        assert "Character" in ws.receive_text()  # the front-desk prompt
        ws.send_text("guest")
        assert "Wandering in as" in ws.receive_text()
        assert "The Cold Forge" in ws.receive_text()  # the start room
        ws.send_text("help")
        assert "Commands:" in ws.receive_text()  # the tick is reachable


def test_register_over_the_wire_creates_an_account_and_enters():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()  # splash
        ws.receive_text()  # "Character..., NEW, or GUEST:"
        ws.send_text("new")
        assert "character@account" in ws.receive_text()
        ws.send_text("webhero@webco")
        assert "password" in ws.receive_text().lower()
        ws.send_text("swordfish9")  # >= 8, clears the password floor
        assert "Welcome, Webhero@webco" in ws.receive_text()
        assert "The Cold Forge" in ws.receive_text()  # scene after entry
    assert account_password_ok("webco", "swordfish9")  # it really persisted


def test_quit_delivers_the_farewell_before_the_socket_closes():
    """Teardown flushes the outbox: the last line (the quit farewell) must
    reach the visitor, not get cut off by the close."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()  # splash
        ws.receive_text()  # prompt
        ws.send_text("guest")
        ws.receive_text()  # wandering in
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
        assert "GUEST" in ws.receive_text().upper()  # re-prompted, not booted


def test_full_gate_turns_visitors_away_when_seated_out():
    web._web_seats = web.MAX_CONNECTIONS
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        assert "full" in ws.receive_text().lower()
