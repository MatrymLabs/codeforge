"""Test twin for the live cave/underzone publishing seam."""

from __future__ import annotations

from pathlib import Path

from kernel.world import canon
from kernel.world.underground import build_underground, load_underground_configs

SEED_DIR = Path(__file__).resolve().parent.parent / "content" / "seeds" / "aethryn"


def test_the_shipped_underground_manifest_covers_every_region_twice() -> None:
    configs = load_underground_configs(SEED_DIR / "underground.yaml")
    assert configs is not None
    region_ids = {region["id"] for region in canon.regions()}
    assert {cfg["region"] for cfg in configs} == region_ids
    assert len(configs) == len(region_ids) * 2
    assert {cfg["kind"] for cfg in configs} == {"cave", "underzone"}


def test_underground_areas_are_attached_living_and_provenanced() -> None:
    configs = load_underground_configs(SEED_DIR / "underground.yaml")
    assert configs is not None
    anchors = {cfg["attach"] for cfg in configs}
    expansion = build_underground(configs, anchors)
    assert len(expansion.zones) == 28
    assert expansion.rooms
    assert expansion.npcs
    assert all(zone["canon_status"] == "GENERATED_LOCAL" for zone in expansion.zones.values())
    assert all(zone["provenance"]["template"] == "cave" for zone in expansion.zones.values())
    assert all(
        zone["entrance"] in zone["rooms"]
        and expansion.rooms[zone["entrance"]]["exits"]["out"] == zone["attach"]
        for zone in expansion.zones.values()
    )


def test_underground_generation_is_deterministic() -> None:
    configs = load_underground_configs(SEED_DIR / "underground.yaml")
    assert configs is not None
    anchors = {cfg["attach"] for cfg in configs}
    first = build_underground(configs, anchors)
    second = build_underground(configs, anchors)
    assert first.rooms == second.rooms
    assert first.npcs == second.npcs
    assert first.zones == second.zones
