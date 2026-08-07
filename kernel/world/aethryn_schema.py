"""CARD: aethryn_schema -- versioned Aethryn content type and reference registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReferenceCollection = Literal["scalar", "list", "mapping_keys", "mapping_values"]


class SchemaRegistryError(ValueError):
    """A schema registry operation would create an ambiguous content contract."""


@dataclass(frozen=True, slots=True)
class ReferenceField:
    """A declared record field whose values point at another content type."""

    field_path: str
    target_type: str
    collection: ReferenceCollection = "scalar"


@dataclass(frozen=True, slots=True)
class SchemaDefinition:
    """The compiler contract for one normalized content type."""

    type_id: str
    schema_version: str
    parser: str
    validator: str
    migration: str
    reference_fields: tuple[ReferenceField, ...]
    serialization_format: str
    compiler_passes: tuple[str, ...]
    runtime_adapter: str
    optional_modules: tuple[str, ...] = ()


class SchemaRegistry:
    """Register and resolve one versioned schema definition per content type."""

    def __init__(self) -> None:
        self._definitions: dict[str, SchemaDefinition] = {}

    def register(self, definition: SchemaDefinition) -> None:
        """Register a type, refusing duplicates instead of silently replacing contracts."""
        if not definition.type_id:
            raise SchemaRegistryError("schema type_id must not be empty")
        if definition.type_id in self._definitions:
            raise SchemaRegistryError(f"schema type already registered: {definition.type_id}")
        self._definitions[definition.type_id] = definition

    def require(self, type_id: str) -> SchemaDefinition:
        """Return a schema or explain the missing registration and corrective action."""
        try:
            return self._definitions[type_id]
        except KeyError as exc:
            raise SchemaRegistryError(
                f"no schema registered for content type {type_id!r}; register its parser, "
                "validator, migration, references, serializer, and runtime adapter"
            ) from exc

    def definitions(self) -> tuple[SchemaDefinition, ...]:
        """Return registered definitions in stable type order."""
        return tuple(self._definitions[key] for key in sorted(self._definitions))


_ROOM = ReferenceField("exits", "rooms", "mapping_values")
_PARENT_REGION = ReferenceField("parent_region", "regions")
_PARENT_ZONE = ReferenceField("parent_zone", "zones")


def _definition(
    type_id: str,
    *references: ReferenceField,
    optional_modules: tuple[str, ...] = (),
) -> SchemaDefinition:
    return SchemaDefinition(
        type_id=type_id,
        schema_version="aethryn-content/1",
        parser="yaml.mapping",
        validator=f"aethryn_validation.validate_{type_id}",
        migration="identity",
        reference_fields=tuple(references),
        serialization_format="yaml",
        compiler_passes=("source_loading", "normalization", "reference_resolution"),
        runtime_adapter=f"kernel.world.seed.{type_id}",
        optional_modules=optional_modules,
    )


def default_schema_registry() -> SchemaRegistry:
    """Return the explicit registry for the currently supported packet content types."""
    registry = SchemaRegistry()
    definitions = [
        _definition("seas"),
        _definition(
            "regions",
            ReferenceField("land", "regions", "list"),
            ReferenceField("seas", "seas", "list"),
        ),
        _definition(
            "zones",
            ReferenceField("region", "regions"),
            ReferenceField("rooms", "rooms", "list"),
        ),
        _definition("settlements", _PARENT_REGION, _PARENT_ZONE),
        _definition(
            "districts",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("settlement_id", "settlements"),
        ),
        _definition(
            "neighborhoods",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("district_id", "districts"),
            ReferenceField("settlement_id", "settlements"),
        ),
        _definition(
            "wilderness",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("attach", "rooms"),
        ),
        _definition(
            "underground",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("attach", "rooms"),
        ),
        _definition(
            "rooms",
            _PARENT_REGION,
            _PARENT_ZONE,
            _ROOM,
            ReferenceField("parent_settlement", "settlements"),
            ReferenceField("parent_wilderness", "wilderness"),
            ReferenceField("district_id", "districts"),
            ReferenceField("neighborhood_id", "neighborhoods"),
        ),
        _definition("npcs", _PARENT_REGION, _PARENT_ZONE, ReferenceField("location", "rooms")),
        _definition("creatures", _PARENT_REGION, _PARENT_ZONE, ReferenceField("location", "rooms")),
        _definition(
            "population_profiles",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("candidate_rooms", "rooms", "list"),
            ReferenceField("creature_id", "creatures"),
        ),
        _definition(
            "spawn_pools",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("rooms", "rooms", "list"),
            ReferenceField("population_id", "population_profiles|ecology_flows|quest_pressures"),
        ),
        _definition(
            "roaming_routes",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("home_room", "rooms"),
            ReferenceField("rooms", "rooms", "list"),
            ReferenceField("population_id", "population_profiles|ecology_flows|quest_pressures"),
        ),
        _definition(
            "migration_rules",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("origin", "rooms"),
            ReferenceField("destinations", "rooms", "list"),
            ReferenceField("population_id", "population_profiles|ecology_flows|quest_pressures"),
        ),
        _definition("encounter_groups", _PARENT_REGION, _PARENT_ZONE),
        _definition(
            "crowd_specs",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("rooms", "rooms", "list"),
            ReferenceField("representative_npcs", "npcs", "list"),
        ),
        _definition(
            "ambient_presence",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("rooms", "rooms", "list"),
            ReferenceField("population_id", "population_profiles|ecology_flows|quest_pressures"),
        ),
        _definition(
            "items",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("source_room", "rooms"),
            ReferenceField("location", "rooms"),
        ),
        _definition(
            "resource_nodes", _PARENT_REGION, _PARENT_ZONE, ReferenceField("source_room", "rooms")
        ),
        _definition("economy_flows", _PARENT_REGION, _PARENT_ZONE),
        _definition(
            "ecology_flows", _PARENT_REGION, _PARENT_ZONE, ReferenceField("creature", "creatures")
        ),
        _definition("quest_pressures", _PARENT_REGION, _PARENT_ZONE),
        _definition(
            "state_changes", _PARENT_REGION, _PARENT_ZONE, ReferenceField("room_id", "rooms")
        ),
        _definition("dungeons", _PARENT_REGION, _PARENT_ZONE),
        _definition(
            "quests",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("pressure_id", "quest_pressures"),
            ReferenceField("creature_ids", "creatures", "list"),
            ReferenceField("item_ids", "items", "list"),
            ReferenceField("npc_ids", "npcs", "list"),
            ReferenceField("room_ids", "rooms", "list"),
        ),
        _definition(
            "quest_arcs",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("quest_ids", "quests", "list"),
        ),
        _definition("contract_templates", _PARENT_REGION, _PARENT_ZONE),
        _definition(
            "public_events",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("aftermath_effect_ids", "quest_world_effects", "list"),
        ),
        _definition("quest_world_effects", _PARENT_REGION, _PARENT_ZONE),
        _definition("quest_generation_profiles", _PARENT_REGION, _PARENT_ZONE),
        _definition("material_culture", _PARENT_REGION, _PARENT_ZONE),
        _definition("materials", _PARENT_REGION, _PARENT_ZONE),
        _definition("item_families", _PARENT_REGION, _PARENT_ZONE),
        _definition("quality_profiles", _PARENT_REGION, _PARENT_ZONE),
        _definition("crafting_stations", _PARENT_REGION, _PARENT_ZONE),
        _definition("merchant_stock_profiles", _PARENT_REGION, _PARENT_ZONE),
        _definition("loot_profiles", _PARENT_REGION, _PARENT_ZONE),
        _definition("placements", _PARENT_REGION, _PARENT_ZONE),
        _definition("equipment_sets", _PARENT_REGION, _PARENT_ZONE),
        _definition(
            "recipes",
            _PARENT_REGION,
            _PARENT_ZONE,
            ReferenceField("makes", "items"),
            ReferenceField("inputs", "items", "mapping_keys"),
        ),
        _definition("abilities", _PARENT_REGION, _PARENT_ZONE),
        _definition("jobs", _PARENT_REGION, _PARENT_ZONE),
        _definition("professions", _PARENT_REGION, _PARENT_ZONE),
        _definition("sets", _PARENT_REGION, _PARENT_ZONE),
        _definition(
            "quests_legacy",
            _PARENT_REGION,
            _PARENT_ZONE,
        ),
    ]
    for definition in definitions:
        registry.register(definition)
    return registry
