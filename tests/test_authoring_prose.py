"""Coverage checks for the authored Aethryn prose pass."""

from __future__ import annotations

from pathlib import Path

import yaml

from kernel.world.authoring_prose import REGION_VOICES, ROOM_PROSE, author_world


def test_every_canon_region_has_a_distinct_authorial_voice() -> None:
    canon = yaml.safe_load(
        (Path(__file__).resolve().parent.parent / "content/seeds/aethryn/canon.yaml").read_text()
    )
    regions = {str(row["id"]) for row in canon["regions"]}
    assert regions == set(REGION_VOICES)
    for voice in REGION_VOICES.values():
        assert len(voice["terrain"]) >= 40
        assert len(voice["history"]) >= 40
        assert len(voice["pressure"]) >= 40
        assert len(voice["wildlife"]) == 4


def test_every_named_source_room_has_explicit_prose() -> None:
    source = Path(__file__).resolve().parent.parent / "content/seeds/aethryn/rooms.yaml"
    rooms = yaml.safe_load(source.read_text())
    assert set(rooms) <= set(ROOM_PROSE)
    assert all(len(description.split()) >= 20 for description in ROOM_PROSE.values())


def test_authoring_replaces_factory_room_and_enemy_copy() -> None:
    rooms = {
        "field_duskwood_vale_0001": {"desc": "The zone (levels 20-50) stretches before you."},
        "the_black_hollow_delve_vault": {"desc": "A generated vault."},
    }
    npcs = {
        "duskwood_vale_warden": {
            "name": "a warden",
            "location": "duskwood_vale",
            "dialogue": ["Welcome to a levels land."],
        },
        "the_black_hollow_deep_boss": {
            "name": "a boss",
            "location": "the_black_hollow",
            "tier": "boss",
            "dialogue": ["The guardian bars the way."],
        },
    }

    author_world(rooms, npcs)

    assert "levels 20-50" not in rooms["field_duskwood_vale_0001"]["desc"]
    assert "old wealth" in rooms["the_black_hollow_delve_vault"]["desc"]
    assert npcs["duskwood_vale_warden"]["name"] == "the vale's lantern warden"
    assert "heartbeat" in npcs["the_black_hollow_deep_boss"]["dialogue"][0]
