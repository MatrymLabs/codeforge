"""Test twin for forge.py -- scripted-input integration tests.

A robot player types commands into the REAL game loop.
This is the card that catches entry-point breakage: wiring gaps,
paste accidents, missing branches. If game_loop can't be driven
end to end, make check goes red.
"""

import copy

import pytest

import forge
from parts.world import doors, items


@pytest.fixture(autouse=True)
def fresh_world():
    """Snapshot ITEMS and DOORS before each test, restore after."""
    items_snap = copy.deepcopy(items.ITEMS)
    doors_snap = copy.deepcopy(doors.DOORS)
    yield
    items.ITEMS.clear()
    items.ITEMS.update(items_snap)
    doors.DOORS.clear()
    doors.DOORS.update(doors_snap)


def play(monkeypatch, capsys, commands: list[str]) -> str:
    """Feed scripted commands to the real game loop; return everything printed."""
    feed = iter(commands)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(feed))
    forge.game_loop()
    return capsys.readouterr().out


def test_full_playthrough_reaches_archive(monkeypatch, capsys):
    out = play(
        monkeypatch,
        capsys,
        ["n", "e", "take key", "unlock door with key", "go north", "quit"],
    )
    assert "You take a copper key." in out
    assert "You unlock the oak door" in out
    assert "The Sealed Archive" in out


def test_locked_door_blocks_the_player(monkeypatch, capsys):
    out = play(monkeypatch, capsys, ["n", "e", "go north", "quit"])
    assert "is locked" in out
    assert "The Sealed Archive" not in out


def test_unknown_command_gets_help_hint(monkeypatch, capsys):
    out = play(monkeypatch, capsys, ["dance wildly", "quit"])
    assert "Huh? Type HELP for commands." in out


def test_entering_a_room_shows_who_and_what_is_there(monkeypatch, capsys):
    """Regression: the Librarian must appear on ARRIVAL, not only on look."""
    out = play(monkeypatch, capsys, ["n", "e", "quit"])
    assert "The librarian is here." in out
    assert "You see a copper key here." in out
