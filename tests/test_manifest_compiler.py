"""Test twin for the first manifest -> Aethryn region -> World Package compiler slice."""

from __future__ import annotations

import json

import pytest

from kernel.domains.manifest_compiler import (
    ManifestCompilerError,
    compile_aethryn_region,
    install_compiled_region,
)
from kernel.seed_package import ScalingModel, compile_manifest
from kernel.world.world_manifest import audit_worlds, describe_world


def _manifest():
    # Small, fast test geometry while preserving the same manifest-driven ratios and code path.
    model = ScalingModel(
        rooms_per_player=0.4,
        npcs_per_room=0.9,
        monsters_per_room=1.6,
        rooms_per_zone=200.0,
        zones_per_region=1.0,
        rooms_per_settlement=200.0,
        rooms_per_dungeon=200.0,
        rooms_per_boss=200.0,
        quests_per_100_rooms=1.0,
        crafting_recipes_per_zone=2.0,
        bytes_per_room=1.0,
    )
    return compile_manifest("Aethryn", "prototype", model)


def test_manifest_compiles_a_deterministic_living_region() -> None:
    manifest = _manifest()
    a = compile_aethryn_region(manifest)
    b = compile_aethryn_region(manifest)

    assert a.region.ok and a.region.world_shaped
    assert a.width * a.height >= a.target_rooms
    assert a.actual_rooms > 0 and a.actual_monsters > 0
    assert a.region.rooms == b.region.rooms
    assert a.npcs == b.npcs
    assert a.target_rooms == manifest.sizing.rooms


def test_manifest_density_changes_the_compiled_geometry() -> None:
    small = compile_aethryn_region(_manifest())
    model = ScalingModel(
        rooms_per_player=4.0,
        rooms_per_zone=2_000.0,
        zones_per_region=1.0,
        rooms_per_settlement=2_000.0,
        rooms_per_dungeon=2_000.0,
        rooms_per_boss=2_000.0,
        bytes_per_room=1.0,
    )
    large = compile_aethryn_region(compile_manifest("Aethryn", "prototype", model))
    assert large.target_rooms > small.target_rooms
    assert large.width * large.height > small.width * small.height


def test_non_aethryn_projects_are_refused_by_the_aethryn_compiler() -> None:
    model = ScalingModel(rooms_per_player=0.4, rooms_per_zone=200.0, bytes_per_room=1.0)
    with pytest.raises(ManifestCompilerError, match="requires project 'Aethryn'"):
        compile_aethryn_region(compile_manifest("Other Game", "prototype", model))


def test_compiled_region_installs_as_a_hostable_seed(tmp_path) -> None:
    compiled = compile_aethryn_region(_manifest())
    hosted = install_compiled_region(compiled, tmp_path)

    assert hosted.ok
    assert set(hosted.files) == {
        "build_manifest.json",
        "npcs.yaml",
        "rooms.yaml",
        "world.yaml",
        "zones.yaml",
    }
    seed = tmp_path / "content" / "blueprints" / "aethryn-veridia"
    payload = json.loads((seed / "build_manifest.json").read_text(encoding="utf-8"))
    assert payload["project"] == "Aethryn"
    assert describe_world("aethryn-veridia", tmp_path).start_room == compiled.region.start
    assert audit_worlds(tmp_path) == {"aethryn-veridia": []}
