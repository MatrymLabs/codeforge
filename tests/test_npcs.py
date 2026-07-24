"""Test twin for parts/world/npcs.py -- presence, talk, and the dialogue cycle."""

import copy

import pytest

from parts.world import npcs
from parts.world.npcs import npcs_in, room_npcs_text, talk


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


# --- ask: topic-based conversation (over Npc.topics) --------------------------------------------


def _with_topics():
    """Give the librarian topics for the ask tests (restored by the fixture)."""
    npcs.NPCS["librarian"]["topics"] = {
        "archive": ["The archive holds every case we have filed."],
        "codex": ["Professor Codex teaches in the classroom.", "Ask it about lessons."],
    }


def test_ask_returns_a_topic_response():
    from parts.world.npcs import ask

    _with_topics()
    out = ask("librarian", "archive", "library")
    assert "every case we have filed" in out


def test_a_multi_line_topic_returns_all_its_lines():
    from parts.world.npcs import ask

    _with_topics()
    out = ask("librarian", "codex", "library")
    assert "teaches in the classroom" in out and "Ask it about lessons" in out


def test_a_bare_ask_lists_the_topics():
    from parts.world.npcs import ask

    _with_topics()
    out = ask("librarian", "", "library")
    assert "archive" in out and "codex" in out


def test_an_unknown_topic_is_refused_with_the_options():
    from parts.world.npcs import ask

    _with_topics()
    out = ask("librarian", "dragons", "library")
    assert "nothing to say" in out and "archive" in out


def test_asking_an_npc_with_no_topics():
    from parts.world.npcs import ask

    assert "nothing more to discuss" in ask("librarian", "anything", "library")  # no topics set


def test_ask_flows_through_the_engine_tick():
    import forge
    from parts.world.session import SESSIONS, Session

    _with_topics()
    s = Session(player_id="reader", location="library")
    SESSIONS["reader"] = s
    assert "every case we have filed" in forge.handle_command(s, "ask librarian about archive")
    SESSIONS.clear()
