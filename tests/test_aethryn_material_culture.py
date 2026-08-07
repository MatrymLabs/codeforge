"""Focused conformance tests for the in-place material-culture extension."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from kernel.world import items
from kernel.world.aethryn_compiler import compile_packet
from kernel.world.aethryn_validation import load_packet, validate_packet
from kernel.world.characters import reclone_item, snapshot_item
from kernel.world.material_culture import (
    compose_item,
    legacy_items,
    legacy_recipes,
    load_catalog,
    validate_catalog,
    validate_weapon,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "content" / "seeds" / "aethryn" / "material_culture.yaml"
PACKET = (
    ROOT
    / "content"
    / "seeds"
    / "aethryn"
    / "design"
    / "packets"
    / "veridia_greenhold_living_slice.yaml"
)


def test_veridia_catalog_is_clean_and_has_reachable_local_culture() -> None:
    catalog = load_catalog(CATALOG)
    report = validate_catalog(catalog)
    assert report.verdict == "CLEAN", [issue.message for issue in report.issues]
    assert {"greenhold_field_spear", "greenhold_arming_sword", "greenhold_roadwarden_bow"} <= set(
        catalog.prototypes
    )
    assert {"smelt_veridian_iron", "forge_greenhold_field_spear", "brew_meadowfoil_tonic"} <= set(
        catalog.recipes
    )
    assert len(catalog.merchant_stock) >= 2
    assert len(catalog.loot_profiles) >= 3


def test_composition_is_deterministic_and_rejects_incompatible_materials() -> None:
    catalog = load_catalog(CATALOG)
    first = compose_item(
        catalog, "field_spear", "veridian_iron_ore", "standard", "greenhold_roadwardens", seed=41017
    )
    second = compose_item(
        catalog, "field_spear", "veridian_iron_ore", "standard", "greenhold_roadwardens", seed=41017
    )
    assert first == second
    with pytest.raises(ValueError, match="invalid composition"):
        compose_item(catalog, "roadwarden_bow", "riverstone")


def test_weapon_budget_rejects_fast_heavy_unrestricted_combinations() -> None:
    catalog = load_catalog(CATALOG)
    valid = catalog.prototypes["greenhold_field_spear"]
    assert validate_weapon(valid, catalog.families["field_spear"]) == []
    invalid = copy.deepcopy(valid)
    invalid["level_band"] = [1, 1]
    invalid["weapon"] = {
        "damage_type": "fire",
        "reach": 4,
        "cadence": 1,
        "accuracy": 8,
        "base_damage_budget": 20,
    }
    errors = validate_weapon(invalid, catalog.families["field_spear"])
    assert any("unsupported damage type" in error for error in errors)
    assert any("budget" in error for error in errors)


def test_packet_validation_and_compilation_emit_material_culture_records(tmp_path: Path) -> None:
    packet = load_packet(PACKET)
    report = validate_packet(packet, root=ROOT)
    assert report.verdict == "CLEAN", [issue.message for issue in report.issues]
    first, first_manifest = compile_packet(PACKET, output_dir=tmp_path / "first", root=ROOT)
    second, second_manifest = compile_packet(PACKET, output_dir=tmp_path / "second", root=ROOT)
    assert first_manifest.output_digest == second_manifest.output_digest
    assert first_manifest.records["materials"] == 7
    assert first_manifest.records["items"] == 18
    assert first_manifest.records["crafting_stations"] == 5
    assert (first / "records.yaml").read_bytes() == (second / "records.yaml").read_bytes()


def test_rich_instance_state_survives_existing_item_snapshot_path() -> None:
    catalog = load_catalog(CATALOG)
    old_items = copy.deepcopy(items.ITEMS)
    old_prototypes = copy.deepcopy(items.PROTOTYPES)
    try:
        items.register_prototypes(legacy_items(catalog))
        iid = items.create_instance(
            "greenhold_field_spear",
            "player:reviewer",
            owner="reviewer",
            condition="damaged",
            durability=41,
            quality="sound",
            maker="Mara's bench",
            custody="military_issue",
            provenance={"packet_id": "veridia_greenhold_living_slice"},
        )
        snap = snapshot_item(iid)
        assert snap is not None
        assert snap["condition"] == "damaged"
        assert snap["custody"] == "military_issue"
        fresh = reclone_item(snap, "player:reviewer")
        assert fresh is not None
        assert items.ITEMS[fresh]["durability"] == 41
        assert (
            items.ITEMS[fresh]["instance_provenance"]["packet_id"]
            == "veridia_greenhold_living_slice"
        )
    finally:
        items.ITEMS.clear()
        items.ITEMS.update(old_items)
        items.PROTOTYPES.clear()
        items.PROTOTYPES.update(old_prototypes)


def test_rich_recipes_project_to_the_existing_recipe_shape() -> None:
    catalog = load_catalog(CATALOG)
    recipes = legacy_recipes(catalog)
    recipe = recipes["forge_greenhold_field_spear"]
    assert recipe["makes"] == "greenhold_field_spear"
    assert recipe["inputs"] == {"wrought_veridian_iron": 1, "alder_haft": 1, "boar_hide": 1}
    assert recipe["requires"]["profession"] == "smithing"
