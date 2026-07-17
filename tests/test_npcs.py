"""Test twin for parts/npcs.py -- presence, talk, and the dialogue cycle."""

import copy

import pytest

from parts import npcs
from parts.npcs import npcs_in, room_npcs_text, talk


@pytest.fixture(autouse=True)
def fresh_world():
    """Snapshot NPCS before each test, restore after."""
    snapshot = copy.deepcopy(npcs.NPCS)
    yield
    npcs.NPCS.clear()
    npcs.NPCS.update(snapshot)


def test_librarian_lives_in_the_library():
    assert "librarian" in npcs_in("library")
    assert "librarian" in room_npcs_text("library").lower()


def test_an_aggressive_npc_is_telegraphed_in_the_room():
    """A hostile foe is flagged in the room render so a strike on the world beat is never a
    surprise: the room text is the player's only rubric for reading danger."""
    npcs.NPCS["reaver"] = {
        "name": "the reaver",
        "keywords": ["reaver"],
        "location": "library",
        "dialogue": ["..."],
        "next_line": 0,
        "hp": 20,
        "hp_now": 20,
        "xp": 10,
        "atk": 5,
        "aggressive": True,
    }
    text = room_npcs_text("library")
    assert "The reaver is here, and looks hostile." in text
    assert "The librarian is here." in text  # a peaceful NPC keeps the plain line, no false alarm


def test_talk_cycles_dialogue_and_wraps():
    first = talk("librarian", "library")
    second = talk("librarian", "library")
    talk("librarian", "library")  # third line
    wrapped = talk("librarian", "library")  # back to the start
    assert first != second
    assert "dust" in first
    assert wrapped == first


def test_talk_in_the_wrong_room_finds_no_one():
    assert talk("librarian", "forge") == "There is no one like that here."


def test_talk_to_unknown_name_finds_no_one():
    assert talk("dragon", "library") == "There is no one like that here."
