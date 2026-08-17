"""Test twin for kernel/world/npcs.py -- presence, talk, and the dialogue cycle."""

import copy

import pytest

from kernel.world import npcs
from kernel.world.npcs import npcs_in, room_npcs_text, talk


@pytest.fixture(autouse=True)
def fresh_world():
    """Snapshot NPCS before each test, restore after."""
    snapshot = copy.deepcopy(npcs.NPCS)
    yield
    npcs.NPCS.clear()
    npcs.NPCS.update(snapshot)
    npcs.reindex_npcs()


def test_librarian_lives_in_the_library():
    assert "librarian" in npcs_in("library")
    assert "librarian" in room_npcs_text("library").lower()


def test_apply_npc_moves_matches_a_full_rebuild():
    # The optimization's core contract: relocating a few NPCs in the index incrementally yields
    # exactly what a from-scratch rebuild would, so ambient roaming stays correct without the
    # O(npcs) rebuild that thrashed the hot path (every look/score paid a full ~54k-NPC rebuild).
    npcs.reindex_npcs()
    npcs_in("library")  # force the index to build
    mover = "librarian"
    old = npcs.NPCS[mover]["location"]
    dest = "a_far_off_room"
    npcs.NPCS[mover]["location"] = dest  # mutate world state, then mirror it in the index
    npcs.apply_npc_moves([(mover, old, dest)])
    incremental = {room: sorted(ids) for room, ids in npcs._by_room.items()}

    npcs.reindex_npcs()
    npcs_in("library")  # full rebuild over the same (now-mutated) NPCS
    rebuilt = {room: sorted(ids) for room, ids in npcs._by_room.items()}

    assert incremental == rebuilt  # incremental update is indistinguishable from a full rebuild
    assert mover in npcs_in(dest) and mover not in npcs_in(old)


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
    from kernel.world.npcs import ask  # noqa: PLC0415

    _with_topics()
    out = ask("librarian", "archive", "library")
    assert "every case we have filed" in out


def test_a_multi_line_topic_returns_all_its_lines():
    from kernel.world.npcs import ask  # noqa: PLC0415

    _with_topics()
    out = ask("librarian", "codex", "library")
    assert "teaches in the classroom" in out and "Ask it about lessons" in out


def test_a_bare_ask_lists_the_topics():
    from kernel.world.npcs import ask  # noqa: PLC0415

    _with_topics()
    out = ask("librarian", "", "library")
    assert "archive" in out and "codex" in out


def test_an_unknown_topic_is_refused_with_the_options():
    from kernel.world.npcs import ask  # noqa: PLC0415

    _with_topics()
    out = ask("librarian", "dragons", "library")
    assert "nothing to say" in out and "archive" in out


def test_asking_an_npc_with_no_topics():
    from kernel.world.npcs import ask  # noqa: PLC0415

    assert "nothing more to discuss" in ask("librarian", "anything", "library")  # no topics set


def test_ask_flows_through_the_engine_tick():
    import forge  # noqa: PLC0415
    from kernel.world.session import SESSIONS, Session  # noqa: PLC0415

    _with_topics()
    s = Session(player_id="reader", location="library")
    SESSIONS["reader"] = s
    assert "every case we have filed" in forge.handle_command(s, "ask librarian about archive")
    SESSIONS.clear()


def test_room_index_rebuilds_when_an_npc_is_added_then_removed():
    """The room index (npcs_in) must reflect NPC membership changes -- a foe added at runtime shows
    up in its room, and once removed it is gone -- so the O(1) index never lies about presence."""
    from kernel.world.seed import Npc  # noqa: PLC0415

    room = "index_probe_room"
    assert npcs_in(room) == []  # nothing here yet
    npcs.NPCS["probe_foe"] = Npc(
        name="a probe foe",
        keywords=["probe"],
        location=room,
        dialogue=['"..."'],
        next_line=0,
        hp=10,
        hp_now=10,
        xp=0,
        atk=0,
    )
    assert npcs_in(room) == ["probe_foe"]  # index rebuilt on the membership change
    del npcs.NPCS["probe_foe"]
    assert npcs_in(room) == []  # rebuilt again once it is gone


# --- numbered-target disambiguation (target_disambig shelf-part consumer) ------------------------
def _two_goblins(room: str = "goblin_den") -> None:
    """Two identical foes (both answer to 'goblin') in one room, so 'goblin' alone is ambiguous."""
    from kernel.world.seed import Npc  # noqa: PLC0415

    for i in (1, 2):
        npcs.NPCS[f"goblin_{i}"] = Npc(
            name=f"goblin {i}",
            keywords=["goblin"],
            location=room,
            dialogue=['"..."'],
            next_line=0,
            hp=10,
            hp_now=10,
            xp=0,
            atk=0,
        )


def test_trace_all_npcs_returns_every_match_in_order():
    _two_goblins()
    assert npcs.trace_all_npcs("goblin", "goblin_den") == ["goblin_1", "goblin_2"]
    assert npcs.trace_npc("goblin", "goblin_den") == "goblin_1"  # first, unchanged


def test_bare_npc_name_resolves_to_the_first():
    _two_goblins()
    assert npcs.resolve_npc_target("goblin", "goblin_den") == "goblin_1"


def test_npc_ordinal_picks_the_nth():
    _two_goblins()
    assert npcs.resolve_npc_target("2-goblin", "goblin_den") == "goblin_2"
    assert npcs.resolve_npc_target("goblin-2", "goblin_den") == "goblin_2"


def test_npc_overshoot_raises_with_a_count():
    from kernel.shelf.target_disambig import TargetError  # noqa: PLC0415

    _two_goblins()
    with pytest.raises(TargetError, match="only 2 here"):
        npcs.resolve_npc_target("3-goblin", "goblin_den")


def test_resolve_unknown_npc_is_none():
    _two_goblins()
    assert npcs.resolve_npc_target("2-troll", "goblin_den") is None
