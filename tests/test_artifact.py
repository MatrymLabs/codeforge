"""Test twin for parts/world/artifact.py -- the Maker's Signet (the Creator Artifact).

Gates the campaign's absolutes: only the Seed Owner bears the Signet, and it opens the Creator
Interface + channels the Workshop's read-only tools REMOTELY (from any room, not just the Workshop).
A non-owner is refused; the read-only-only boundary is honoured (no create/publish here).
"""

import pytest

from forge import handle_command
from parts.world import artifact, events
from parts.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_sessions():
    SESSIONS.clear()
    events.SHUTDOWN["hook"] = None
    yield
    SESSIONS.clear()
    events.SHUTDOWN["hook"] = None


def _seat(name: str, rank: str, location: str = "veridia") -> Session:
    s = Session(player_id=name, location=location, named=True, rank=rank)
    SESSIONS[name] = s
    return s


def test_only_the_seed_owner_bears_the_signet():
    assert artifact.bears_signet(_seat("root", "owner"))
    assert not artifact.bears_signet(_seat("mage", "wizard"))
    assert not artifact.bears_signet(_seat("nobody", "player"))


def test_the_signet_opens_the_creator_interface_anywhere():
    # the owner is out in the wild (veridia), NOT in the Workshop -- the Signet still answers.
    owner = _seat("root", "owner", location="veridia")
    out = handle_command(owner, "signet")
    assert "Maker's Signet" in out and "signet survey" in out and "signet activity" in out


def test_the_signet_channels_the_read_only_tools_remotely():
    owner = _seat("root", "owner", location="veridia")
    _seat("hero", "player", location="veridia")  # someone to show up in activity
    survey = handle_command(owner, "signet survey")
    assert "Rooms:" in survey and "roughly a" in survey  # the world-shape report, from the wild
    activity = handle_command(owner, "signet activity")
    assert "Players online:" in activity and "Hero" in activity  # the live-play report


def test_a_non_owner_is_refused_the_signet():
    player = _seat("nosy", "player", location="veridia")
    assert "does not know your hand" in handle_command(player, "signet")
    assert "does not know your hand" in handle_command(player, "signet survey")


def test_an_unknown_function_is_refused_but_the_signet_still_answers_the_owner():
    owner = _seat("root", "owner")
    out = handle_command(owner, "signet publish")  # a mutating power the Signet does not carry
    assert "no power called 'publish'" in out and "survey" in out
