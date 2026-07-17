"""Test twin for parts/ranks.py -- authority checked before power."""

import pytest

from forge import handle_command
from parts import events
from parts.events import bind_echo, unbind_echo
from parts.ranks import has_rank
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_sessions():
    SESSIONS.clear()
    events.SHUTDOWN["hook"] = None
    yield
    SESSIONS.clear()
    events.SHUTDOWN["hook"] = None


def _seat(name: str, rank: str = "player", location: str = "forge") -> Session:
    s = Session(player_id=name, location=location, named=True, rank=rank)
    SESSIONS[name] = s
    return s


def test_rank_order_is_a_ladder():
    assert has_rank(_seat("w", "wizard"), "player")
    assert has_rank(_seat("o", "owner"), "wizard")
    assert not has_rank(_seat("p", "player"), "wizard")


def test_players_are_refused_every_wizard_verb():
    p = _seat("mortal")
    for verb in ("@teleport library", "@grant mortal owner", "@shutdown"):
        assert "lack the authority" in handle_command(p, verb)
    assert p.location == "forge"
    assert p.rank == "player"


def test_an_unknown_wizard_verb_lists_the_full_admin_surface():
    """The 'known verbs' listing is derived from the command spine, so an unknown @-verb names
    the spine's ADMIN verbs (@sg/@forge/@arch) alongside this module's legacy trio -- it can't
    silently omit half the admin surface the way a hand-kept list did."""
    out = handle_command(_seat("root", "owner"), "@bogus")
    assert "Unknown wizard verb" in out
    for verb in ("@teleport", "@grant", "@shutdown", "@sg", "@forge", "@arch"):
        assert verb in out


def test_teleport_moves_a_wizard_and_is_witnessed():
    w = _seat("gandalf", "wizard")
    _seat("bystander", location="library")
    heard: list[str] = []
    bind_echo("bystander", heard.append)
    out = handle_command(w, "@teleport library")
    assert w.location == "library"
    assert "You step between places" in out
    assert "Gandalf appears from nowhere." in heard
    unbind_echo("bystander")


def test_teleport_refuses_unknown_rooms():
    w = _seat("gandalf", "wizard")
    assert "no room labeled" in handle_command(w, "@teleport narnia")
    assert w.location == "forge"


def test_grant_is_owner_only_and_persists_rank():
    o = _seat("matrym", "owner")
    target = _seat("apprentice")
    out = handle_command(o, "@grant apprentice wizard")
    assert "now rank: wizard" in out
    assert target.rank == "wizard"
    wiz = _seat("gandalf", "wizard")
    assert "lack the authority" in handle_command(wiz, "@grant apprentice owner")


def test_shutdown_saves_everyone_and_fires_the_hook():
    fired: list[bool] = []
    events.SHUTDOWN["hook"] = lambda: fired.append(True)
    o = _seat("matrym", "owner")
    p = _seat("bystander")
    heard: list[str] = []
    bind_echo("bystander", heard.append)
    out = handle_command(o, "@shutdown")
    assert out == "The world sleeps."
    assert fired == [True]
    assert not o.alive and not p.alive
    assert any("going to sleep" in line for line in heard)
    unbind_echo("bystander")
