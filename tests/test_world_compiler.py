"""Tests for the multi-region Aethryn World Package compiler milestone."""

from __future__ import annotations

import json
from pathlib import Path

from kernel.domains.manifest_compiler import VERIDIA_PROFILE, AethrynRegionProfile
from kernel.domains.world_compiler import (
    compile_aethryn_world,
    install_compiled_world,
    load_aethryn_profiles,
)
from kernel.seed_package import ScalingModel, compile_manifest


def _manifest():
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


def _two_profiles() -> tuple[AethrynRegionProfile, ...]:
    return (
        VERIDIA_PROFILE,
        AethrynRegionProfile(
            region_id="duskwood_vale",
            display_name="Duskwood Vale Wilds",
            biome="wild-forest",
            level_min=20,
            level_max=50,
            seed=17,
            landmarks=(
                (0.15, 0.18, "Duskwood Cairn", "site"),
                (0.48, 0.48, "Duskwood Moot", "site"),
                (0.82, 0.78, "Duskwood Keep", "dungeon"),
            ),
        ),
    )


def test_shipped_zone_data_exposes_all_fourteen_compiler_profiles() -> None:
    profiles = load_aethryn_profiles()
    assert len(profiles) == 14
    assert profiles[0].region_id == "veridia"
    assert {profile.region_id for profile in profiles} >= {
        "veridia",
        "duskwood_vale",
        "the_voidscar",
    }


def test_two_regions_compile_deterministically_and_connect_by_the_canonical_graph() -> None:
    manifest = _manifest()
    a = compile_aethryn_world(manifest, _two_profiles())
    b = compile_aethryn_world(manifest, _two_profiles())

    assert a.actual_rooms == sum(region.actual_rooms for region in a.regions)
    assert a.actual_monsters == sum(region.actual_monsters for region in a.regions)
    assert set(a.graph["regions"]) == {"veridia", "duskwood_vale"}
    veridia = next(region for region in a.regions if region.profile.region_id == "veridia")
    duskwood = next(region for region in a.regions if region.profile.region_id == "duskwood_vale")
    assert a.rooms[veridia.region.start]["exits"]["route_duskwood_vale"] == duskwood.region.start
    assert a.rooms[duskwood.region.start]["exits"]["route_veridia"] == veridia.region.start
    assert a.rooms == b.rooms and a.npcs == b.npcs and a.graph == b.graph


def test_assembled_world_installs_as_one_hostable_seed(tmp_path) -> None:
    world = compile_aethryn_world(_manifest(), _two_profiles())
    hosted = install_compiled_world(world, tmp_path)

    assert hosted.ok
    assert set(hosted.files) == {
        "assembly_manifest.json",
        "build_manifest.json",
        "items.yaml",
        "npcs.yaml",
        "rooms.yaml",
        "world.yaml",
        "world_graph.yaml",
        "zones.yaml",
    }
    assembly = json.loads((Path(hosted.seed_dir) / "assembly_manifest.json").read_text())
    assert assembly["assembly"]["regions"] == ["veridia", "duskwood_vale"]
    assert assembly["assembly"]["actual_rooms"] == world.actual_rooms
