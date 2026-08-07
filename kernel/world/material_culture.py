# ruff: noqa: E501

"""Deterministic Aethryn material-culture catalog.

This module is an adapter around the existing seed item registry.  It owns explanatory structure
(materials, families, composition, supply origins, and validation), while ``items.py``,
``crafting.py``, ``professions.py``, ``shop.py``, ``gearsets.py``, and persistence remain the live
runtime authorities.  No runtime generation or model call occurs here: catalog composition is a
pure function of its inputs, seed, and generator version.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from kernel.world.aethryn_models import ValidationIssue, ValidationReport, content_digest
from kernel.world.seed import SEED_DIR, _UniqueKeyLoader

VALID_CATEGORIES = {
    "ingredient",
    "component",
    "weapon",
    "armor",
    "shield",
    "tool",
    "consumable",
    "household_good",
    "trade_good",
    "wearable",
    "key_item",
    "relic",
}
VALID_SLOTS = {"", "weapon", "body", "head", "arm", "leg", "feet", "accessory_1", "accessory_2"}
VALID_LAYERS = {"environmental", "ambient", "ambient_goods", "interactive", "portable", "unique"}
VALID_STATUSES = {"CANON_LOCKED", "CANON_WORKING", "AUTHORED_LOCAL", "GENERATED_LOCAL", "RUMOR"}
VALID_DAMAGE_TYPES = {"slash", "thrust", "pierce", "blunt", "physical"}
ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
FORBIDDEN_LEGACY_TERMS = ("unforging", "netharion survived", "god-killing", "divine strike")


@dataclass(frozen=True)
class MaterialCultureCatalog:
    metadata: Mapping[str, Any]
    materials: Mapping[str, Mapping[str, Any]]
    families: Mapping[str, Mapping[str, Any]]
    qualities: Mapping[str, Mapping[str, Any]]
    prototypes: Mapping[str, Mapping[str, Any]]
    durability_profiles: Mapping[str, Mapping[str, Any]]
    repair_profiles: Mapping[str, Mapping[str, Any]]
    salvage_profiles: Mapping[str, Mapping[str, Any]]
    recipes: Mapping[str, Mapping[str, Any]]
    stations: Mapping[str, Mapping[str, Any]]
    merchant_stock: Mapping[str, Mapping[str, Any]]
    loot_profiles: Mapping[str, Mapping[str, Any]]
    placements: Mapping[str, Mapping[str, Any]]
    equipment_sets: Mapping[str, Mapping[str, Any]]


class MaterialCultureError(ValueError):
    """A malformed material-culture catalog or impossible composition."""


def catalog_path(path: Path | None = None) -> Path:
    return path or (SEED_DIR / "material_culture.yaml")


def _section(raw: Mapping[str, Any], name: str) -> dict[str, Mapping[str, Any]]:
    value = raw.get(name, {})
    if not isinstance(value, dict):
        raise MaterialCultureError(f"material culture {name}: expected a mapping")
    return {str(key): dict(value) for key, value in value.items()}


def load_catalog(path: Path | None = None) -> MaterialCultureCatalog:
    """Load one catalog with deterministic, duplicate-key-safe YAML semantics."""
    where = catalog_path(path)
    if not where.exists():
        return MaterialCultureCatalog({}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {})
    raw = yaml.load(where.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(raw, dict):
        raise MaterialCultureError(f"material culture {where}: root must be a mapping")
    metadata = raw.get("metadata", {})
    if not isinstance(metadata, dict):
        raise MaterialCultureError(f"material culture {where}: metadata must be a mapping")
    materials = _section(raw, "materials")
    prototypes = _section(raw, "prototypes")
    # A source material is also a portable ingredient prototype in the existing item registry.
    # Synthesize only the mechanical shell here; its source and cultural meaning remain owned by
    # the MaterialSpec record, and the generated text is deliberately plain and deterministic.
    for material_id, material in materials.items():
        if material_id not in prototypes:
            display = str(material.get("display_name", material_id))
            prototypes[material_id] = {
                "display_name": f"a quantity of {display.lower()}",
                "keywords": [material_id, "material"],
                "family_id": "ingredient",
                "category": "ingredient",
                "short_description": f"A gathered quantity of {display.lower()} from its declared source.",
                "ground_description": f"A gathered quantity of {display.lower()} has been set down here.",
                "examine_description": f"This material is sourced from {', '.join(str(v) for v in material.get('source_habitats', [])) or 'a declared regional source'} and is used for {', '.join(str(v) for v in material.get('common_uses', [])) or 'local work'}.",
                "materials": [material_id],
                "maker_tradition": str(material.get("gathering_method", "local gathering")),
                "source_regions": list(material.get("source_regions", [])),
                "ownership_default": "unowned",
                "weight": float(material.get("weight_factor", 1.0)),
                "stackable": True,
                "stack_limit": 20,
                "value": max(1, int(float(material.get("value_factor", 1.0)) * 2)),
                "rarity": "common",
                "merchant_eligible": False,
                "loot_eligible": True,
            }
    return MaterialCultureCatalog(
        metadata=dict(metadata),
        materials=materials,
        families=_section(raw, "families"),
        qualities=_section(raw, "qualities"),
        prototypes=prototypes,
        durability_profiles=_section(raw, "durability_profiles"),
        repair_profiles=_section(raw, "repair_profiles"),
        salvage_profiles=_section(raw, "salvage_profiles"),
        recipes=_section(raw, "recipes"),
        stations=_section(raw, "stations"),
        merchant_stock=_section(raw, "merchant_stock"),
        loot_profiles=_section(raw, "loot_profiles"),
        placements=_section(raw, "placements"),
        equipment_sets=_section(raw, "equipment_sets"),
    )


def _metadata(catalog: MaterialCultureCatalog, row: Mapping[str, Any]) -> dict[str, Any]:
    source_ids = list(row.get("source_design_ids", catalog.metadata.get("source_design_ids", [])))
    source_paths = list(row.get("source_paths", catalog.metadata.get("source_paths", [])))
    packet_id = str(row.get("packet_id", catalog.metadata.get("packet_id", "")))
    provenance = dict(row.get("provenance", {}))
    provenance.setdefault("source_design_ids", source_ids)
    provenance.setdefault("source_paths", source_paths)
    provenance.setdefault("packet_id", packet_id)
    provenance.setdefault("generation_seed", int(catalog.metadata.get("generation_seed", 0)))
    provenance.setdefault("generator_name", str(catalog.metadata.get("generator_name", "")))
    provenance.setdefault("generator_version", str(catalog.metadata.get("generator_version", "")))
    provenance.setdefault(
        "authority",
        str(row.get("canon_status", catalog.metadata.get("canon_status", "GENERATED_LOCAL"))),
    )
    provenance.setdefault("note", str(catalog.metadata.get("provenance_note", "")))
    return {
        "source_design_ids": source_ids,
        "source_paths": source_paths,
        "packet_id": packet_id,
        "generation_seed": int(catalog.metadata.get("generation_seed", 0)),
        "generator_name": str(catalog.metadata.get("generator_name", "")),
        "generator_version": str(catalog.metadata.get("generator_version", "")),
        "provenance": provenance,
    }


def as_legacy_item(catalog: MaterialCultureCatalog, prototype_id: str) -> dict[str, Any]:
    """Project a rich prototype into the existing ``Item`` registry shape."""
    row = catalog.prototypes[prototype_id]
    category = str(row.get("category", "ingredient"))
    weapon = row.get("weapon", {}) if isinstance(row.get("weapon", {}), dict) else {}
    armor = row.get("armor", {}) if isinstance(row.get("armor", {}), dict) else {}
    consumable = row.get("consumable", {}) if isinstance(row.get("consumable", {}), dict) else {}
    effect = consumable.get("effect", {})
    item: dict[str, Any] = {
        "name": str(row.get("display_name", prototype_id)),
        "keywords": [str(value) for value in row.get("keywords", [prototype_id])],
        "location": "nowhere",
        "slot": str(row.get("equipment_slot", "")),
        "mods": _legacy_mods(category, weapon, armor),
        "prototype": prototype_id,
        "material_ids": [str(value) for value in row.get("materials", [])],
        "family_id": str(row.get("family_id", "")),
        "category": category,
        "short_description": str(row.get("short_description", "")),
        "ground_description": str(row.get("ground_description", "")),
        "examine_description": str(row.get("examine_description", "")),
        "equipped_description": str(row.get("equipped_description", "")),
        "damaged_description": str(row.get("damaged_description", "")),
        "broken_description": str(row.get("broken_description", "")),
        "use_feedback": str(row.get("use_feedback", "")),
        "repair_feedback": str(row.get("repair_feedback", "")),
        "crafting_feedback": str(row.get("crafting_feedback", "")),
        "consumption_feedback": str(row.get("consumption_feedback", "")),
        "salvage_feedback": str(row.get("salvage_feedback", "")),
        "maker_tradition": str(row.get("maker_tradition", "")),
        "source_regions": [str(value) for value in row.get("source_regions", [])],
        "ownership_default": str(row.get("ownership_default", "unowned")),
        "weight": float(row.get("weight", 0.0)),
        "stackable": bool(row.get("stackable", False)),
        "stack_limit": int(row.get("stack_limit", 1)),
        "value": int(row.get("value", 0)),
        "rarity": str(row.get("rarity", "common")),
        "level_band": list(row.get("level_band", [1, 1])),
        "quality_profile": str(row.get("quality_profile", "standard")),
        "durability_profile": str(row.get("durability_profile", "")),
        "repair_profile": str(row.get("repair_profile", "")),
        "salvage_profile": str(row.get("salvage_profile", "")),
        "merchant_eligible": bool(row.get("merchant_eligible", False)),
        "loot_eligible": bool(row.get("loot_eligible", False)),
        "unique": bool(row.get("unique", False)),
        "provenance": _metadata(catalog, row),
    }
    if effect:
        # Existing consumables only understand hp/mp.  Other effects remain structured metadata.
        hpmp = {str(key): int(value) for key, value in effect.items() if key in {"hp", "mp"}}
        if hpmp:
            item["consume"] = hpmp
        item["charges"] = int(consumable.get("charges", 1))
        item["effects"] = {str(key): int(value) for key, value in effect.items()}
    if row.get("lore"):
        item["lore"] = str(row["lore"])
    return item


def _legacy_mods(
    category: str, weapon: Mapping[str, Any], armor: Mapping[str, Any]
) -> dict[str, int]:
    if category == "weapon":
        return {
            "ATK": int(weapon.get("base_damage_budget", 0)),
            "ACC": int(weapon.get("accuracy", 0)),
        }
    if category in {"armor", "shield", "wearable"}:
        return {
            "DEF": int(armor.get("defense_budget", 0)),
            "MAG DEF": int(armor.get("magic_defense_budget", 0)),
            "EVA": int(armor.get("evasion", 0)),
        }
    return {}


def legacy_items(catalog: MaterialCultureCatalog) -> dict[str, dict[str, Any]]:
    return {
        prototype_id: as_legacy_item(catalog, prototype_id) for prototype_id in catalog.prototypes
    }


def legacy_recipes(catalog: MaterialCultureCatalog) -> dict[str, dict[str, Any]]:
    """Adapt rich recipe requirements to the existing ``craft`` verb shape."""
    return {
        recipe_id: {
            "name": str(row.get("display_name", recipe_id)),
            "makes": str(row.get("output_prototype", "")),
            "inputs": {
                str(req.get("prototype_id")): int(req.get("quantity", 0))
                for req in row.get("requirements", [])
                if isinstance(req, dict)
            },
            "culture_recipe": recipe_id,
            "station": str(row.get("station", "")),
            "profession": str(row.get("profession", "")),
            "requires": {"profession": str(row.get("profession", "")), "level": 1}
            if row.get("profession")
            else {},
            "output_quantity": int(row.get("output_quantity", 1)),
            "quality_logic": str(row.get("quality_logic", "fixed")),
            "provenance": _metadata(catalog, row),
        }
        for recipe_id, row in catalog.recipes.items()
    }


def catalog_professions(catalog: MaterialCultureCatalog) -> dict[str, dict[str, Any]]:
    """Derive profession declarations from recipes without creating a second skill system."""
    result: dict[str, dict[str, Any]] = {}
    for recipe_id, row in catalog.recipes.items():
        profession = str(row.get("profession", ""))
        if not profession:
            continue
        result.setdefault(
            profession,
            {
                "name": profession.replace("_", " ").title(),
                "kind": "craft",
                "works": [],
                "makes": [],
                "provenance": _metadata(catalog, row),
            },
        )["makes"].append(recipe_id)
    for material_id, row in catalog.materials.items():
        profession = str(row.get("gathering_profession", ""))
        if profession:
            result.setdefault(
                profession,
                {
                    "name": profession.replace("_", " ").title(),
                    "kind": "gather",
                    "works": [],
                    "makes": [],
                    "provenance": _metadata(catalog, row),
                },
            )["works"].append(material_id)
    for profile in catalog.repair_profiles.values():
        profession = str(profile.get("profession", ""))
        if profession:
            result.setdefault(
                profession,
                {
                    "name": profession.replace("_", " ").title(),
                    "kind": "craft",
                    "works": [],
                    "makes": [],
                    "provenance": _metadata(catalog, profile),
                },
            )
    return result


def compose_item(
    catalog: MaterialCultureCatalog,
    family_id: str,
    material_id: str,
    quality_id: str = "standard",
    maker: str = "",
    condition: str = "sound",
    *,
    seed: int | None = None,
) -> dict[str, Any]:
    """Compose a deterministic generated prototype from approved parts.

    Composition returns a fresh projection and never registers or mutates runtime state.  The
    budget is bounded by the family, material, quality, and level band; callers can inspect the
    ``composition_key`` and provenance before registering it through ``items.register_prototypes``.
    """
    family = catalog.families.get(family_id)
    material = catalog.materials.get(material_id)
    quality = catalog.qualities.get(quality_id)
    if not family or not material or not quality:
        raise MaterialCultureError(
            f"cannot compose {family_id}/{material_id}/{quality_id}: family, material, and quality must exist"
        )
    material_class = str(material.get("material_class", ""))
    if material_class not in family.get("allowed_material_classes", []):
        raise MaterialCultureError(
            f"invalid composition {family_id}+{material_id}: material class {material_class!r} is not allowed; "
            "choose a family-compatible material or author a new family"
        )
    if not maker and not family.get("regional_traditions"):
        raise MaterialCultureError(
            f"invalid composition {family_id}: no maker tradition is available"
        )
    stable_seed = int(catalog.metadata.get("generation_seed", 0) if seed is None else seed)
    key = f"{stable_seed}:{family_id}:{material_id}:{quality_id}:{maker}:{condition}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    tradition = maker or str(family.get("regional_traditions", ["local tradition"])[0])
    noun = str(family.get("display_name", family_id)).lower()
    material_name = str(material.get("display_name", material_id)).lower()
    return {
        "id": f"generated_{family_id}_{material_id}_{quality_id}_{digest[:8]}",
        "display_name": f"{material_name} {noun}",
        "keywords": [family_id, material_id, quality_id],
        "family_id": family_id,
        "category": str(family.get("category", "ingredient")),
        "materials": [material_id],
        "maker_tradition": tradition,
        "condition": condition,
        "quality_profile": quality_id,
        "source_regions": list(material.get("source_regions", [])),
        "level_band": [1, 1],
        "short_description": f"A {quality_id} {noun} made from {material_name} by the {tradition}.",
        "ground_description": f"A {material_name} {noun} rests here, showing the {tradition} in its construction.",
        "examine_description": f"The {noun} is built from {material_name}; its weight, wear, and use fit the {tradition} rather than an unnamed heroic maker.",
        "provenance": {
            "source_design_ids": list(catalog.metadata.get("source_design_ids", [])),
            "source_paths": list(catalog.metadata.get("source_paths", [])),
            "packet_id": str(catalog.metadata.get("packet_id", "")),
            "generation_seed": stable_seed,
            "generator_name": "aethryn_material_culture.compose_item",
            "generator_version": str(catalog.metadata.get("generator_version", "1.0.0")),
            "authority": "GENERATED_LOCAL",
            "note": f"composition key {key}",
        },
        "content_digest": content_digest(key),
    }


def weapon_budget(row: Mapping[str, Any]) -> int:
    weapon = row.get("weapon", {}) if isinstance(row.get("weapon", {}), dict) else {}
    # Reach and cadence consume budget; accuracy and properties are explicit bounded additions.
    return (
        int(weapon.get("base_damage_budget", 0))
        + int(weapon.get("accuracy", 0))
        + max(0, int(weapon.get("reach", 1)) - 1)
        + max(0, int(weapon.get("cadence", 1)) - 1)
    )


def validate_weapon(row: Mapping[str, Any], family: Mapping[str, Any] | None = None) -> list[str]:
    weapon = row.get("weapon", {}) if isinstance(row.get("weapon", {}), dict) else {}
    errors: list[str] = []
    damage_type = str(weapon.get("damage_type", ""))
    if damage_type not in VALID_DAMAGE_TYPES:
        errors.append(f"unsupported damage type {damage_type!r}; use {sorted(VALID_DAMAGE_TYPES)}")
    if family is not None and damage_type not in family.get("supported_damage_types", []):
        errors.append(
            f"damage type {damage_type!r} is not supported by family {family.get('display_name', '')!r}"
        )
    if int(weapon.get("base_damage_budget", 0)) < 0:
        errors.append("base damage budget cannot be negative")
    band = row.get("level_band", [1, 1])
    if not isinstance(band, list) or len(band) != 2 or int(band[0]) > int(band[1]):
        errors.append("level_band must be an ordered [minimum, maximum] pair")
    level_cap = max(1, int(band[1])) if isinstance(band, list) and len(band) == 2 else 1
    allowed_budget = (
        8 + level_cap // 2 + (2 if str(row.get("rarity", "common")) in {"uncommon", "rare"} else 0)
    )
    if weapon_budget(row) > allowed_budget:
        errors.append(
            f"weapon budget {weapon_budget(row)} exceeds approved cap {allowed_budget} for level band {band}"
        )
    if int(weapon.get("cadence", 1)) <= 0 or int(weapon.get("reach", 1)) <= 0:
        errors.append("reach and cadence must be positive")
    return errors


def _issue(
    issues: list[ValidationIssue], category: str, code: str, path: str, message: str, action: str
) -> None:
    issues.append(
        ValidationIssue(
            category, code, path, message, "AETHRYN_ITEM_AND_EQUIPMENT_SYSTEM.md", action
        )
    )


def validate_catalog(catalog: MaterialCultureCatalog | None = None) -> ValidationReport:
    catalog = catalog or load_catalog()
    issues: list[ValidationIssue] = []
    metadata = catalog.metadata
    for field in (
        "packet_id",
        "generation_seed",
        "generator_name",
        "generator_version",
        "source_design_ids",
        "source_paths",
    ):
        if metadata.get(field) in (None, "", []):
            _issue(
                issues,
                "PROVENANCE",
                "missing_catalog_metadata",
                f"metadata.{field}",
                f"catalog metadata lacks {field}",
                "inherit packet provenance before publication",
            )
    for section_name in (
        "materials",
        "families",
        "prototypes",
        "recipes",
        "stations",
        "merchant_stock",
        "loot_profiles",
        "placements",
        "equipment_sets",
    ):
        section = getattr(catalog, section_name)
        for record_id, row in section.items():
            path = f"{section_name}.{record_id}"
            if not ID_RE.fullmatch(record_id):
                _issue(
                    issues,
                    "PROVENANCE",
                    "invalid_id",
                    path,
                    f"record id {record_id!r} is not lowercase_snake_case",
                    "rename the record with a stable lowercase_snake_case id",
                )
            status = str(row.get("canon_status", metadata.get("canon_status", "GENERATED_LOCAL")))
            if status not in VALID_STATUSES:
                _issue(
                    issues,
                    "CANON",
                    "invalid_status",
                    f"{path}.canon_status",
                    f"status {status!r} is not on the authority ladder",
                    "use CANON_LOCKED, CANON_WORKING, AUTHORED_LOCAL, GENERATED_LOCAL, or RUMOR",
                )
            if status in {"CANON_LOCKED", "CANON_WORKING"}:
                _issue(
                    issues,
                    "CANON",
                    "unauthorized_promotion",
                    f"{path}.canon_status",
                    "material-culture generation cannot promote a record to locked canon",
                    "use AUTHORED_LOCAL or GENERATED_LOCAL until explicit human review",
                )
            if any(term in str(row).lower() for term in FORBIDDEN_LEGACY_TERMS):
                _issue(
                    issues,
                    "CANON",
                    "legacy_canon_leakage",
                    path,
                    "record text reintroduces forbidden legacy metaphysics or answers an open question",
                    "remove the term and describe only observable material behavior",
                )
    for material_id, row in catalog.materials.items():
        if not row.get("source_regions") and str(row.get("scarcity")) not in {
            "imported",
            "ancient",
            "artificial",
            "intentionally_unobtainable",
        }:
            _issue(
                issues,
                "MATERIAL",
                "missing_source",
                f"materials.{material_id}",
                "material has no source region or explicit exceptional origin",
                "add a region/habitat, or mark it imported, ancient, artificial, or intentionally_unobtainable",
            )
        if not row.get("gathering_profession") and str(row.get("scarcity")) not in {
            "imported",
            "ancient",
            "artificial",
            "intentionally_unobtainable",
        }:
            _issue(
                issues,
                "PROFESSION",
                "missing_gathering_profession",
                f"materials.{material_id}",
                "gatherable material has no gathering profession",
                "assign exactly one gathering profession",
            )
    for prototype_id, row in catalog.prototypes.items():
        path = f"prototypes.{prototype_id}"
        required = (
            "display_name",
            "family_id",
            "category",
            "short_description",
            "ground_description",
            "examine_description",
            "materials",
            "maker_tradition",
            "source_regions",
            "ownership_default",
        )
        for field_name in required:
            if row.get(field_name) in (None, "", []):
                _issue(
                    issues,
                    "ITEM",
                    "missing_item_field",
                    f"{path}.{field_name}",
                    f"portable or meaningful item is missing {field_name}",
                    "complete the item record before registering it",
                )
        if not row.get("provenance") and not metadata.get("source_design_ids"):
            _issue(
                issues,
                "PROVENANCE",
                "missing_provenance",
                path,
                "item has no explicit or inherited provenance",
                "add source ids, source paths, packet id, seed, generator, and version",
            )
        family = catalog.families.get(str(row.get("family_id")))
        if family is None:
            _issue(
                issues,
                "ITEM",
                "missing_family",
                f"{path}.family_id",
                f"item references unknown family {row.get('family_id')!r}",
                "add the family or correct the reference",
            )
        else:
            slot = str(row.get("equipment_slot", ""))
            if slot not in VALID_SLOTS or (slot and slot not in family.get("allowed_slots", [])):
                _issue(
                    issues,
                    "EQUIPMENT",
                    "invalid_slot",
                    f"{path}.equipment_slot",
                    f"slot {slot!r} is incompatible with family {row.get('family_id')!r}",
                    "choose one existing equipment slot allowed by the family",
                )
            for material_id in row.get("materials", []):
                material = catalog.materials.get(str(material_id))
                if material is None:
                    if str(material_id) not in catalog.prototypes:
                        _issue(
                            issues,
                            "MATERIAL",
                            "missing_material",
                            f"{path}.materials",
                            f"item references missing material {material_id!r}",
                            "add the material source record",
                        )
                elif str(material.get("material_class")) not in family.get(
                    "allowed_material_classes", []
                ):
                    _issue(
                        issues,
                        "MATERIAL",
                        "impossible_composition",
                        f"{path}.materials",
                        f"material {material_id!r} cannot be used by family {row.get('family_id')!r}",
                        "change the material or author an allowed construction family",
                    )
            if row.get("category") == "weapon":
                for error in validate_weapon(row, family):
                    _issue(
                        issues,
                        "BALANCE",
                        "weapon_budget",
                        path,
                        error,
                        "reduce the budget, narrow the level band, or add a meaningful acquisition/tradeoff",
                    )
        if bool(row.get("unique")) and bool(row.get("merchant_eligible")):
            _issue(
                issues,
                "ECONOMY",
                "unique_stock",
                path,
                "unique item is eligible for ordinary merchant stock",
                "remove merchant eligibility and use an authored placement or reward",
            )
    for recipe_id, row in catalog.recipes.items():
        path = f"recipes.{recipe_id}"
        output = str(row.get("output_prototype", ""))
        if output not in catalog.prototypes:
            _issue(
                issues,
                "CRAFTING",
                "missing_recipe_output",
                path,
                f"recipe output {output!r} does not name an item prototype",
                "add the output prototype or correct the recipe",
            )
        requirements = row.get("requirements", [])
        if not requirements:
            _issue(
                issues,
                "CRAFTING",
                "missing_recipe_inputs",
                path,
                "recipe has no input requirements",
                "declare at least one positive input",
            )
        for requirement in requirements:
            input_id = (
                str(requirement.get("prototype_id", "")) if isinstance(requirement, dict) else ""
            )
            quantity = (
                int(requirement.get("quantity", 0))
                if isinstance(requirement, dict)
                and str(requirement.get("quantity", "")).lstrip("-").isdigit()
                else 0
            )
            if input_id not in catalog.prototypes or quantity <= 0:
                _issue(
                    issues,
                    "CRAFTING",
                    "missing_recipe_input",
                    f"{path}.requirements",
                    f"recipe input {input_id!r} is missing or non-positive",
                    "reference a real prototype with a positive quantity",
                )
        if not row.get("profession"):
            _issue(
                issues,
                "PROFESSION",
                "missing_craft_profession",
                path,
                "recipe has no crafting profession",
                "assign exactly one craft profession",
            )
        if str(row.get("station", "")) not in catalog.stations:
            _issue(
                issues,
                "CRAFTING",
                "missing_station",
                path,
                f"recipe station {row.get('station')!r} does not exist",
                "add the station or correct the recipe",
            )
    for profile_id, row in catalog.merchant_stock.items():
        for item_id in list(row.get("ordinary_stock", {})) + list(row.get("conditional_stock", {})):
            if item_id not in catalog.prototypes:
                _issue(
                    issues,
                    "ECONOMY",
                    "missing_stock_item",
                    f"merchant_stock.{profile_id}",
                    f"merchant stock names missing item {item_id!r}",
                    "add the item or remove it from stock",
                )
            if item_id not in row.get("supply_sources", {}) and item_id not in row.get(
                "imported_goods", {}
            ):
                _issue(
                    issues,
                    "ECONOMY",
                    "stock_without_source",
                    f"merchant_stock.{profile_id}.{item_id}",
                    "stock has no local source or documented import route",
                    "declare supply_sources or imported_goods with a route",
                )
    for profile_id, row in catalog.loot_profiles.items():
        for item_id in list(row.get("guaranteed", [])) + list(row.get("weighted", {})):
            if item_id != "nothing" and item_id not in catalog.prototypes:
                _issue(
                    issues,
                    "LOOT",
                    "missing_loot_item",
                    f"loot_profiles.{profile_id}",
                    f"loot names missing item {item_id!r}",
                    "add the item prototype or remove the drop",
                )
        if str(row.get("source_class")) == "biological" and not row.get("body_class"):
            _issue(
                issues,
                "LOOT",
                "missing_body_class",
                f"loot_profiles.{profile_id}",
                "biological loot has no body class",
                "declare the body class before assigning biological materials",
            )
    for placement_id, row in catalog.placements.items():
        if str(row.get("layer", "")) not in VALID_LAYERS:
            _issue(
                issues,
                "PLACEMENT",
                "invalid_layer",
                f"placements.{placement_id}.layer",
                f"placement layer {row.get('layer')!r} is invalid",
                "use environmental, ambient_goods, interactive, portable, or unique",
            )
    for set_id, row in catalog.equipment_sets.items():
        pieces = list(row.get("pieces", []))
        slots = list(row.get("slots", []))
        if not pieces:
            _issue(
                issues,
                "EQUIPMENT",
                "empty_set",
                f"equipment_sets.{set_id}",
                "gear set has no pieces",
                "declare at least two compatible pieces",
            )
        for piece in pieces:
            if piece not in catalog.prototypes:
                _issue(
                    issues,
                    "EQUIPMENT",
                    "missing_set_piece",
                    f"equipment_sets.{set_id}",
                    f"set references missing piece {piece!r}",
                    "add the piece or correct the set",
                )
            elif str(catalog.prototypes[piece].get("equipment_slot", "")) not in slots:
                _issue(
                    issues,
                    "EQUIPMENT",
                    "set_slot_mismatch",
                    f"equipment_sets.{set_id}",
                    f"piece {piece!r} does not use a declared set slot",
                    "align the set slots with piece equipment slots",
                )
    return ValidationReport(
        verdict="FAIL" if any(issue.severity == "error" for issue in issues) else "CLEAN",
        issues=tuple(issues),
        input_digest=content_digest(catalog),
        output_digest=content_digest(
            {"catalog": asdict(catalog), "issues": [asdict(issue) for issue in issues]}
        ),
    )


def format_catalog_report(report: ValidationReport) -> str:
    if not report.issues:
        return "material-culture: CLEAN"
    lines = [f"material-culture: {report.verdict}"]
    for issue in report.issues:
        lines.append(f"- {issue.path}: {issue.message}; action: {issue.action}")
    return "\n".join(lines)
