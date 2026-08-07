"""Tests for the offline pure-authoring serialization boundary."""

from __future__ import annotations

from tools.materialize_aethryn import _item_record, _npc_record, _quest_filename


def test_runtime_state_is_not_frozen_into_authored_npcs() -> None:
    record = _npc_record(
        {
            "name": "a keeper",
            "location": "greenhold",
            "hp": 10,
            "hp_now": 3,
            "next_line": 4,
            "ambient": True,
        }
    )
    assert record == {"name": "a keeper", "location": "greenhold", "hp": 10}


def test_materialized_item_locations_are_seed_locations() -> None:
    record = _item_record(
        {
            "name": "a record",
            "location": "room:archive",
            "slot": "",
            "mods": {},
            "prototype": "record",
            "rarity": "rare",
        }
    )
    assert record["location"] == "archive"
    assert "prototype" not in record and "rarity" not in record


def test_materialized_quest_filenames_are_safe_and_stable() -> None:
    assert _quest_filename("bounty:the-black-hollow") == "materialized_bounty_the_black_hollow.yaml"
