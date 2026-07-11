"""Test twin for parts/workshop.py -- the engineering cockpit (display-only).

Card functions render the menu, the catalog, and a reuse search; the engine-tick
tests prove the commands are reachable through handle_command (a feature isn't
wired until the tick proves it)."""

import pytest

from forge import handle_command
from parts.session import SESSIONS, Session
from parts.workshop import catalog_view, reuse_search, workshop_menu


@pytest.fixture(autouse=True)
def fresh_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def _player() -> Session:
    session = Session(player_id="builder")
    SESSIONS["builder"] = session
    return session


def test_menu_lists_live_tools_and_is_honest_about_whats_coming():
    menu = workshop_menu()
    assert "engineering cockpit" in menu
    assert "catalog" in menu and "reuse" in menu  # live
    assert (
        "Coming" in menu and "arch" in menu
    )  # honest about what's not built yet (the proving ground arch)


def test_blueprint_is_a_live_workshop_tool_now():
    # blueprint (browse/read/render/draft) is built, so the cockpit advertises it as LIVE,
    # not "coming" -- the menu must reflect what the workshop can actually do.
    menu = workshop_menu()
    live, _, coming = menu.partition("Coming")
    assert "blueprint" in live
    assert "blueprint" not in coming


def test_catalog_view_shows_cataloged_parts():
    text = catalog_view()
    assert "HARDWARE CATALOG" in text
    assert "rank-gate" in text  # a real part in catalog/parts.yaml


def test_reuse_search_finds_by_domain_and_handles_misses():
    assert "event-ledger" in reuse_search("audit")  # audit-trail reuse
    assert "No cataloged part" in reuse_search("zzznope")
    assert "Reuse what?" in reuse_search("")


def test_workshop_commands_are_reachable_through_the_tick():
    session = _player()
    assert "engineering cockpit" in handle_command(session, "workshop")
    assert "HARDWARE CATALOG" in handle_command(session, "catalog")
    assert "HARDWARE CATALOG" in handle_command(session, "hardware")  # alias
    assert "HARDWARE CATALOG" in handle_command(session, "parts")  # alias
    assert "event-ledger" in handle_command(session, "reuse audit")
