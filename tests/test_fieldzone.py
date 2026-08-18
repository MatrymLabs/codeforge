"""Test twin for kernel/world/fieldzone.py -- the field-backed wilderness assembler.

Acceptance: a valid config generates a world-shaped, LIVING field grafted to its hub by a reciprocal
exit, with area metadata so cull/forage route. Refusal: a malformed config, an unreachable landmark,
a not-world-shaped region, and an id collision each FAIL LOUD (a broken zone never ships silently).
"""

from __future__ import annotations

from typing import cast

import pytest

from kernel.world.fieldzone import (
    FieldZone,
    FieldZoneError,
    _gate_cell,
    build_field_zone,
    load_field_configs,
)
from kernel.world.seed import Room

# A config the worldgen twin already proved world-shaped + fully reachable (24x18, seed 7, two
# landmarks). attach_dir west -> the field's back exit home is `east`.
_CFG = {
    "id": "probe",
    "name": "The Probe Wilds",
    "region": "Testreach",
    "biome": "temperate-meadow",
    "attach": "probe_hub",
    "attach_dir": "west",
    "level_min": 1,
    "level_max": 30,
    "width": 24,
    "height": 18,
    "seed": 7,
    "landmarks": [
        {"at": [3, 3], "name": "Old Cairn", "kind": "site"},
        {"at": [20, 14], "name": "Sunken Keep", "kind": "dungeon"},
    ],
}


# --- the config loader ---------------------------------------------------------------------------


def test_a_valid_fields_file_loads_with_ids_injected(tmp_path) -> None:
    p = tmp_path / "fields.yaml"
    p.write_text(
        "veridia:\n  name: The Veridia Wilds\n  region: Veridia\n  biome: temperate-meadow\n"
        "  attach: veridia\n  attach_dir: west\n  level_min: 1\n  level_max: 30\n"
        "  width: 24\n  height: 18\n  seed: 7\n",
        encoding="utf-8",
    )
    configs = load_field_configs(p)
    assert configs is not None and len(configs) == 1
    assert configs[0]["id"] == "veridia" and configs[0]["attach"] == "veridia"


def test_a_missing_fields_file_is_none_not_an_error(tmp_path) -> None:
    assert load_field_configs(tmp_path / "absent.yaml") is None


def test_a_non_mapping_fields_file_is_refused(tmp_path) -> None:
    p = tmp_path / "fields.yaml"
    p.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(FieldZoneError, match="non-empty mapping"):
        load_field_configs(p)


def test_a_row_that_is_not_a_mapping_is_refused(tmp_path) -> None:
    p = tmp_path / "fields.yaml"
    p.write_text("veridia: just-a-string\n", encoding="utf-8")
    with pytest.raises(FieldZoneError, match="must be a mapping"):
        load_field_configs(p)


def test_a_missing_required_key_is_refused(tmp_path) -> None:
    p = tmp_path / "fields.yaml"
    p.write_text("veridia:\n  name: X\n  attach: veridia\n", encoding="utf-8")  # no biome/width/...
    with pytest.raises(FieldZoneError, match="missing required key"):
        load_field_configs(p)


def test_a_bad_attach_direction_is_refused(tmp_path) -> None:
    p = tmp_path / "fields.yaml"
    p.write_text(
        "veridia:\n  name: X\n  region: R\n  biome: temperate-meadow\n  attach: veridia\n"
        "  attach_dir: sideways\n  level_min: 1\n  level_max: 30\n  width: 10\n  height: 10\n",
        encoding="utf-8",
    )
    with pytest.raises(FieldZoneError, match="not a compass dir"):
        load_field_configs(p)


# --- the assembler: a living, grafted field ------------------------------------------------------


def test_a_field_zone_is_world_shaped_living_and_grafted() -> None:
    fz = build_field_zone(_CFG, taken=set())
    assert isinstance(fz, FieldZone)
    assert fz.label == "field_probe" and fz.attach == "probe_hub" and fz.attach_dir == "west"
    # the gate is a real field cell, and it carries the reciprocal exit HOME to the hub
    assert fz.gate in fz.rooms
    assert fz.rooms[fz.gate]["exits"]["east"] == "probe_hub"  # east = reverse of west
    # the field is alive: foes + gather nodes + guardians, every creature on a real cell
    assert fz.npcs and all(npc["location"] in fz.rooms for npc in fz.npcs.values())
    assert any("node" in r for r in fz.rooms.values()), "the field must carry gather nodes"
    assert any(k.startswith("probe_lord_") for k in fz.npcs), "the field must seat guardians"


def test_the_zone_metadata_covers_every_field_room() -> None:
    fz = build_field_zone(_CFG, taken=set())
    assert fz.zone["rooms"] == list(fz.rooms)  # every cell belongs to the area, so zone_of resolves
    assert fz.zone["biome"] == "temperate-meadow" and fz.zone["region"] == "Testreach"
    assert fz.zone["level_min"] == 1 and fz.zone["level_max"] == 30
    assert fz.zone["name"] == "The Probe Wilds"


def test_building_the_same_field_is_deterministic() -> None:
    a = build_field_zone(_CFG, taken=set())
    b = build_field_zone(_CFG, taken=set())
    assert set(a.rooms) == set(b.rooms) and a.npcs == b.npcs and a.gate == b.gate


def test_an_unreachable_landmark_is_refused_loud() -> None:
    bad = {**_CFG, "landmarks": [{"at": [100, 100], "name": "Nowhere"}]}  # off the map -> no room
    with pytest.raises(FieldZoneError):
        build_field_zone(bad, taken=set())


def test_a_region_that_is_not_world_shaped_is_refused() -> None:
    tiny = {
        **_CFG,
        "width": 1,
        "height": 1,
        "landmarks": [],
    }  # a single cell is a trail, not a world
    with pytest.raises(FieldZoneError, match="not a world-shaped"):
        build_field_zone(tiny, taken=set())


def test_a_room_id_collision_with_the_world_is_refused() -> None:
    # the (3,3) landmark cell is always 'probe_3_3'; pretend the world already owns it
    with pytest.raises(FieldZoneError, match="collide"):
        build_field_zone(_CFG, taken={"probe_3_3"})


def test_a_zone_can_climb_UP_into_its_field() -> None:  # noqa: N802
    # some hubs attach vertically (you climb UP into the highland wilderness); the field's door
    # leads back DOWN. A 2D field cell never spends its up/down slots, so the graft is always free.
    vertical = {**_CFG, "attach_dir": "up", "biome": "glacier-waste"}
    fz = build_field_zone(vertical, taken=set())
    assert fz.attach_dir == "up"
    assert fz.rooms[fz.gate]["exits"]["down"] == "probe_hub"  # down = reverse of up


def test_gate_cell_finds_a_free_edge_slot() -> None:
    rooms = cast(
        "dict[str, Room]",
        {
            "z_0_0": {"exits": {"east": "z_1_0"}},  # a west-edge cell: its `west` slot is free
            "z_1_0": {"exits": {"west": "z_0_0"}},
        },
    )
    assert _gate_cell(rooms, "west") == "z_0_0"  # lowest id whose `west` slot is open
