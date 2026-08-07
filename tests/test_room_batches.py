"""Tests for the prose room-batch handoff contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from kernel.world.room_batches import apply_room_batches, batch_files
from kernel.world.seed import SeedError
from tools.import_aethryn_drops import _anchor_record
from tools.import_mud_batch import compile_batches, parse_text


def _write_batch(path: Path, *, rooms: dict[str, dict[str, Any]], final: bool = True) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "batch": {
                    "id": path.stem,
                    "sequence": 1,
                    "status": "ready",
                    "size": len(rooms),
                    "final": final,
                },
                "rooms": rooms,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_ready_batch_overlays_existing_rooms(tmp_path: Path) -> None:
    _write_batch(
        tmp_path / "batch_0001.yaml",
        rooms={
            "greenhold": {
                "desc": (
                    "The market wakes beneath wet awnings while old metal glints in the furrows "
                    "beyond the gate, and every stall carries a different version of the river's "
                    "latest rumour."
                )
            }
        },
    )
    world = {"greenhold": {"name": "Greenhold", "desc": "old", "exits": {}}}

    report = apply_room_batches(world, directory=tmp_path)

    assert report == {"batches": 1, "rooms": 1}
    assert "old metal" in world["greenhold"]["desc"]


def test_existing_room_batch_does_not_replace_canonical_exits_without_replace(
    tmp_path: Path,
) -> None:
    _write_batch(
        tmp_path / "batch_0001.yaml",
        rooms={
            "greenhold": {
                "desc": (
                    "The market wakes beneath wet awnings while old metal glints in the furrows "
                    "beyond the gate, and every stall carries a different version of the river's "
                    "latest rumour."
                ),
                "exits": {"north": "decorative_route"},
            }
        },
    )
    world = {
        "greenhold": {"name": "Greenhold", "desc": "old", "exits": {"out": "veridia"}},
        "veridia": {"name": "Veridia", "desc": "old", "exits": {}},
    }

    apply_room_batches(world, directory=tmp_path)

    assert world["greenhold"]["exits"] == {"out": "veridia"}


def test_non_final_batch_may_contain_any_positive_room_count(tmp_path: Path) -> None:
    _write_batch(
        tmp_path / "batch_0001.yaml",
        rooms={
            "greenhold": {
                "desc": (
                    "The market wakes beneath wet awnings while old metal glints in the furrows "
                    "beyond the gate, and every stall carries a different version of the river's "
                    "latest rumour."
                )
            }
        },
        final=False,
    )

    report = apply_room_batches(
        {"greenhold": {"name": "Greenhold", "desc": "old", "exits": {}}},
        directory=tmp_path,
    )
    assert report == {"batches": 1, "rooms": 1}


def test_large_batch_is_accepted_without_a_room_count_ceiling(tmp_path: Path) -> None:
    description = (
        "A broad authored chamber carries enough local detail to make its threshold feel "
        "deliberate and inhabited, with a landmark, a working route, and a reason to remember it."
    )
    rooms = {f"authored_room_{index:03d}": {"desc": description} for index in range(250)}
    _write_batch(tmp_path / "batch_0001.yaml", rooms=rooms, final=False)
    world = {label: {"name": label, "desc": "old", "exits": {}} for label in rooms}

    report = apply_room_batches(world, directory=tmp_path)

    assert report == {"batches": 1, "rooms": 250}


def test_batch_fails_loud_on_stale_room_id(tmp_path: Path) -> None:
    _write_batch(
        tmp_path / "batch_0001.yaml",
        rooms={
            "removed_room": {
                "desc": (
                    "This paragraph belongs to a room that no longer exists on the assembled map, "
                    "but its stale description must still fail the build before players can "
                    "encounter "
                    "it."
                ),
                "exits": {"north": "nowhere"},
            }
        },
    )

    with pytest.raises(SeedError, match="unknown room"):
        apply_room_batches(
            {"greenhold": {"name": "Greenhold", "desc": "old", "exits": {}}},
            directory=tmp_path,
        )


def test_batch_can_add_linked_rooms_and_visible_content(tmp_path: Path) -> None:
    _write_batch(
        tmp_path / "batch_0001.yaml",
        rooms={
            "new_place_a": {
                "name": "New Place A",
                "desc": (
                    "A newly authored place carries enough local detail to make its threshold feel "
                    "deliberate and inhabited, with a landmark, a working route, and a reason to "
                    "remember the crossing."
                ),
                "exits": {"east": "new_place_b"},
                "occupants": ["A patient ferryman waits beside the water."],
                "objects": ["A blue route marker leans against the wall."],
            },
            "new_place_b": {
                "name": "New Place B",
                "desc": (
                    "The second room closes the route with a view back toward the first place "
                    "and a "
                    "distinct local landmark, a visible occupant, and a path worth following home."
                ),
                "exits": {"west": "new_place_a"},
            },
        },
    )
    world = {"new_place_a": {"name": "old", "desc": "old", "exits": {}}}
    npcs: dict[str, dict[str, Any]] = {}
    items: dict[str, dict[str, Any]] = {}

    report = apply_room_batches(world, npcs, items, directory=tmp_path)

    assert report == {"batches": 1, "rooms": 2}
    assert world["new_place_b"]["exits"] == {"west": "new_place_a"}
    assert len(npcs) == 1 and len(items) == 1


def test_classic_mud_text_compiles_into_bounded_batches() -> None:
    text = """\
Sample Square
[Town Square]
Pale stones circle a fountain while market voices carry between the houses.
The air smells of bread, rain, and river water.
A clerk waits beside the fountain.
A public notice board stands near the gate.
A copper bell hangs under the eaves.
Obvious exits: north, east, south, west.

River Road
[Trade Road]
The road leaves the square and follows the river through open country.
Wind moves through the grass and distant birds call over the water.
A traveler studies the road marker.
A milestone points toward the crossing.
Fresh cart tracks darken the mud.
Obvious exits: west, east.
"""

    records = parse_text(text)
    batches = compile_batches(records, sequence=2)

    assert len(records) == 2
    assert batches[0]["rooms"]["sample_square"]["exits"]["north"] == "river_road"
    assert len(batches) == 1
    assert batches[0]["batch"]["final"] is True


def test_text_drop_labels_can_use_a_stable_namespace() -> None:
    records = parse_text(
        """\
Namespace Square
[Town Square]
Pale stones circle a fountain while market voices carry between the houses.
The air smells of bread, rain, and river water.
A clerk waits beside the fountain.
A public notice board stands near the gate.
A copper bell hangs under the eaves.
Obvious exits: north.
"""
    )

    batch = compile_batches(records, sequence=8, label_prefix="Skyward Spires")[0]

    assert "skyward_spires_namespace_square" in batch["rooms"]


def test_a_drop_anchor_adds_only_a_new_named_exit() -> None:
    world = {
        "greenhold": {
            "name": "Greenhold",
            "desc": "The established town anchor carries the current world prose.",
            "exits": {"out": "veridia"},
        }
    }

    record = _anchor_record(
        world,
        anchor_room="greenhold",
        anchor_exit="wards",
        first_room="drop_greenhold_square",
    )

    assert record["exits"] == {"out": "veridia", "wards": "drop_greenhold_square"}
    assert world["greenhold"]["exits"] == {"out": "veridia"}


def test_batches_apply_in_declared_sequence_order(tmp_path: Path) -> None:
    description = (
        "A maintained threshold records the packet order in visible notices, repaired stonework, "
        "fresh route marks, and a local reason for returning before nightfall."
    )
    _write_batch(
        tmp_path / "z_old_name.yaml",
        rooms={"anchor": {"desc": description, "exits": {"east": "new_place"}}},
    )
    second = tmp_path / "a_new_name.yaml"
    second.write_text(
        yaml.safe_dump(
            {
                "batch": {"id": "new", "sequence": 2, "status": "ready", "size": 1, "final": True},
                "rooms": {
                    "anchor": {"desc": description, "replace": True, "exits": {"west": "new_place"}}
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    assert [path.name for path in batch_files(tmp_path)] == ["z_old_name.yaml", "a_new_name.yaml"]
