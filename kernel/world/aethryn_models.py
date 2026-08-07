"""CARD: aethryn_models -- typed records for deterministic Aethryn world compilation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

CanonStatus = Literal["CANON_LOCKED", "CANON_WORKING", "AUTHORED_LOCAL", "GENERATED_LOCAL", "RUMOR"]
ActionStatus = Literal["changed", "already", "refused", "unavailable"]
ValidationVerdict = Literal["CLEAN", "WATCHLIST", "FAIL"]


def _tuple_text(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"expected a list of text, got {type(value).__name__}")
    return tuple(str(entry) for entry in value)


@dataclass(frozen=True)
class Provenance:
    source_design_ids: tuple[str, ...]
    source_paths: tuple[str, ...]
    packet_id: str
    generation_seed: int
    generator_name: str
    generator_version: str
    authority: str
    note: str = ""


@dataclass(frozen=True)
class WorldRecord:
    stable_id: str
    display_name: str
    canon_status: CanonStatus
    parent_region: str
    parent_zone: str
    source_design_ids: tuple[str, ...]
    generation_seed: int
    generator_name: str
    generator_version: str
    provenance: Provenance
    content_digest: str = ""


@dataclass(frozen=True)
class ExitSpec:
    direction: str
    destination: str
    reciprocal_required: bool = True
    route_kind: str = "local"


@dataclass(frozen=True)
class WorldDesignSpec:
    world_id: str
    display_name: str
    canon_status: CanonStatus
    source_paths: tuple[str, ...]
    regions: tuple[RegionSpec, ...] = ()
    zones: tuple[ZoneSpec, ...] = ()
    settlements: tuple[SettlementSpec, ...] = ()
    dungeons: tuple[DungeonSpec, ...] = ()


@dataclass(frozen=True)
class RegionSpec(WorldRecord):
    threat_min: int = 0
    threat_max: int = 0


@dataclass(frozen=True)
class ZoneSpec(WorldRecord):
    threat_min: int = 0
    threat_max: int = 0


@dataclass(frozen=True)
class SettlementSpec(WorldRecord):
    population_band: str = ""
    government: str = ""
    food_sources: tuple[str, ...] = ()
    water_source: str = ""
    fuel_source: str = ""
    labor_base: tuple[str, ...] = ()
    waste_handling: str = ""
    economy: str = ""
    architecture: str = ""
    culture: str = ""
    services: tuple[str, ...] = ()
    external_connections: tuple[str, ...] = ()
    active_conflicts: tuple[str, ...] = ()
    daily_rhythm: str = ""


@dataclass(frozen=True)
class DistrictSpec(WorldRecord):
    settlement_id: str = ""
    purpose: tuple[str, ...] = ()


@dataclass(frozen=True)
class NeighborhoodSpec(WorldRecord):
    settlement_id: str = ""
    district_id: str = ""
    purpose: tuple[str, ...] = ()


@dataclass(frozen=True)
class WildernessSpec(WorldRecord):
    zone_id: str = ""
    habitat: str = ""
    traversal_identity: str = ""
    purpose: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoomSpec(WorldRecord):
    parent_settlement: str = ""
    parent_wilderness: str = ""
    district_id: str = ""
    neighborhood_id: str = ""
    purpose: tuple[str, ...] = ()
    description: str = ""
    exits: tuple[ExitSpec, ...] = ()
    room_type: str = ""
    tags: tuple[str, ...] = ()
    short_description: str = ""
    long_description: str = ""
    points_of_interest: tuple[dict[str, Any], ...] = ()
    conditions: tuple[dict[str, Any], ...] = ()
    prose_status: CanonStatus = "GENERATED_LOCAL"
    prose_source: str = ""


@dataclass(frozen=True)
class DungeonSpec(WorldRecord):
    built_by: str = ""
    original_purpose: str = ""
    historical_layer: str = ""
    failure: str = ""
    current_occupants: tuple[str, ...] = ()
    why_not_reclaimed: str = ""
    entrance_logic: str = ""
    traversal_grammar: tuple[str, ...] = ()
    gameplay_purpose: str = ""
    revelation: str = ""
    aftermath: str = ""
    state_change: str = ""


@dataclass(frozen=True)
class NPCSpec(WorldRecord):
    role: tuple[str, ...] = ()
    location: str = ""
    schedule: tuple[str, ...] = ()
    relationship_to_civilization: str = ""


@dataclass(frozen=True)
class CreatureSpec(WorldRecord):
    keywords: tuple[str, ...] = ()
    creature_category: str = "biological"
    habitat: str = ""
    allowed_regions: tuple[str, ...] = ()
    climate_tolerance: tuple[str, ...] = ()
    threat_range: tuple[int, int] = (0, 0)
    description: str = ""
    room_presence_description: str = ""
    examine_description: str = ""
    behavior: str = ""
    intelligence: str = ""
    disposition: str = ""
    social_organization: str = ""
    activity_period: str = ""
    movement_behavior: str = ""
    diet_or_energy_source: str = ""
    predators: tuple[str, ...] = ()
    prey_or_resource_pressure: str = ""
    reproduction_or_recurrence: str = ""
    seasonal_behavior: str = ""
    ecological_role: str = ""
    relationship_to_civilization: str = ""
    reason_for_persistence: str = ""
    combat_role: str = ""
    abilities: tuple[str, ...] = ()
    resistances: Mapping[str, str] = field(default_factory=dict)
    vulnerabilities: Mapping[str, str] = field(default_factory=dict)
    retreat_behavior: str = ""
    pursuit_behavior: str = ""
    assistance_behavior: str = ""
    loot_outputs: tuple[str, ...] = ()
    crafting_outputs: tuple[str, ...] = ()
    rarity: str = "common"
    provenance_note: str = ""


@dataclass(frozen=True)
class PopulationProfile:
    """Where and when a creature or social archetype is allowed to appear."""

    stable_id: str
    creature_id: str = ""
    region: str = ""
    zone: str = ""
    habitat: str = ""
    allowed_room_types: tuple[str, ...] = ()
    forbidden_room_types: tuple[str, ...] = ()
    candidate_rooms: tuple[str, ...] = ()
    population_min: int = 0
    population_max: int = 0
    carrying_capacity: int = 0
    spawn_rules: Mapping[str, Any] = field(default_factory=dict)
    reset_rules: Mapping[str, Any] = field(default_factory=dict)
    depletion_rules: Mapping[str, Any] = field(default_factory=dict)
    recovery_rules: Mapping[str, Any] = field(default_factory=dict)
    time_of_day: tuple[str, ...] = ()
    seasons: tuple[str, ...] = ()
    weather: tuple[str, ...] = ()
    state_conditions: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    player_pressure_effects: Mapping[str, Any] = field(default_factory=dict)
    migration_routes: tuple[str, ...] = ()
    rarity: str = "common"
    direct_presence_probability: float = 0.0
    ambient_evidence_probability: float = 0.0
    hostile_presence_probability: float = 0.0
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpawnPool:
    stable_id: str
    population_id: str = ""
    rooms: tuple[str, ...] = ()
    forbidden_rooms: tuple[str, ...] = ()
    max_active: int = 0
    reset_interval: int = 0
    spawn_probability: float = 0.0
    recurrence: str = ""
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoamingRoute:
    stable_id: str
    population_id: str = ""
    rooms: tuple[str, ...] = ()
    forbidden_rooms: tuple[str, ...] = ()
    home_room: str = ""
    origin_area: str = ""
    movement_interval: int = 1
    movement_probability: float = 0.0
    max_distance: int = 0
    destination_needs: tuple[str, ...] = ()
    closed_exit_behavior: str = "return"
    hazard_behavior: str = "avoid"
    return_behavior: str = "return_home"
    population_cap: int = 0
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MigrationRule:
    stable_id: str
    population_id: str = ""
    origin: str = ""
    destinations: tuple[str, ...] = ()
    trigger: str = ""
    return_trigger: str = ""
    season: tuple[str, ...] = ()
    weather: tuple[str, ...] = ()
    maximum_distance: int = 0
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EncounterGroupSpec:
    stable_id: str
    formation: str = "pack"
    composition: Mapping[str, tuple[int, int]] = field(default_factory=dict)
    minimum_size: int = 1
    maximum_size: int = 1
    leader_id: str = ""
    formation_behavior: str = "cohesive"
    cohesion: float = 1.0
    shared_aggression: bool = False
    ally_assistance: bool = False
    pursuit_distance: int = 0
    retreat_conditions: tuple[str, ...] = ()
    leader_loss_behavior: str = "scatter"
    casualty_behavior: str = "retreat_at_threshold"
    reinforcement_behavior: str = "none"
    loot_ownership: str = "group"
    spawn_rules: Mapping[str, Any] = field(default_factory=dict)
    recurrence: str = ""
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CrowdSpec:
    stable_id: str
    rooms: tuple[str, ...] = ()
    population_min: int = 0
    population_max: int = 0
    composition: Mapping[str, tuple[int, int]] = field(default_factory=dict)
    schedule: tuple[str, ...] = ()
    density_states: Mapping[str, tuple[int, int]] = field(default_factory=dict)
    collective_description: str = ""
    ambient_actions: tuple[str, ...] = ()
    mood: str = "steady"
    danger_reaction: str = "disperse_to_shelter"
    dispersal_behavior: str = "return_on_next_schedule"
    representative_npcs: tuple[str, ...] = ()
    accessibility_description: str = ""
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AmbientPresenceSpec:
    stable_id: str
    room: str = ""
    rooms: tuple[str, ...] = ()
    population_id: str = ""
    evidence_type: str = "sign"
    text: str = ""
    activity_lines: tuple[str, ...] = ()
    probability: float = 0.0
    time_of_day: tuple[str, ...] = ()
    state_conditions: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PopulationState:
    population_id: str
    zone: str = ""
    tick: int = 0
    current_count: int = 0
    occupied_rooms: tuple[str, ...] = ()
    ambient_rooms: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    depleted_until: int = 0
    persistence_scope: str = "zone"
    seed: int = 0
    generator_version: str = ""


@dataclass(frozen=True)
class PopulationManifest:
    zone: str
    tick: int
    states: tuple[PopulationState, ...] = ()
    direct_presence: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    ambient_presence: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    roaming_groups: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    evidence: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    digest: str = ""


@dataclass(frozen=True)
class ItemSpec(WorldRecord):
    origin: str = ""
    material: str = ""
    maker_or_tradition: str = ""
    use: str = ""
    custody: str = ""
    maintenance_state: str = ""
    regional_relevance: str = ""


# Material-culture records deliberately sit beside the legacy-compatible ItemSpec above.  The
# runtime item registry still owns containment and cloning; these records explain why a prototype
# exists and provide the compiler with enough structure to validate production, trade, ecology, and
# equipment without copying prototype data into every live instance.
@dataclass(frozen=True)
class MaterialSpec(WorldRecord):
    material_class: str = ""
    source_regions: tuple[str, ...] = ()
    source_habitats: tuple[str, ...] = ()
    gathering_method: str = ""
    gathering_profession: str = ""
    refinement_chain: tuple[str, ...] = ()
    common_uses: tuple[str, ...] = ()
    scarcity: str = "common"
    weight_factor: float = 1.0
    durability_factor: float = 1.0
    value_factor: float = 1.0
    repair_compatibility: tuple[str, ...] = ()
    elemental_properties: tuple[str, ...] = ()
    cultural_interpretation: str = ""


@dataclass(frozen=True)
class ItemFamilySpec(WorldRecord):
    category: str = ""
    allowed_material_classes: tuple[str, ...] = ()
    allowed_slots: tuple[str, ...] = ()
    construction_methods: tuple[str, ...] = ()
    regional_traditions: tuple[str, ...] = ()
    supported_damage_types: tuple[str, ...] = ()
    handedness: str = ""
    role: str = ""
    tradeoffs: tuple[str, ...] = ()


@dataclass(frozen=True)
class QualityProfile:
    stable_id: str
    display_name: str
    durability_factor: float = 1.0
    value_factor: float = 1.0
    modifier_budget: int = 0
    salvage_factor: float = 1.0
    source_causes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DurabilityProfile:
    stable_id: str
    maximum: int = 100
    wear_rate: int = 1
    damaged_threshold: int = 50
    broken_threshold: int = 0


@dataclass(frozen=True)
class RepairProfile:
    stable_id: str
    materials: Mapping[str, int] = field(default_factory=dict)
    profession: str = ""
    station: str = ""
    cost_per_point: int = 0
    feedback: str = ""


@dataclass(frozen=True)
class SalvageProfile:
    stable_id: str
    source_items: tuple[str, ...] = ()
    profession: str = ""
    tool: str = ""
    outputs: Mapping[str, tuple[int, int]] = field(default_factory=dict)
    quality_loss: int = 0
    prohibited_items: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlacementProfile:
    stable_id: str
    layer: str = "ambient"
    rooms: tuple[str, ...] = ()
    quantity: tuple[int, int] = (1, 1)
    ownership: str = "unowned"
    portable: bool = False
    interaction: str = ""


@dataclass(frozen=True)
class OwnershipProfile:
    stable_id: str
    kind: str = "unowned"
    holder: str = ""
    custody_rules: tuple[str, ...] = ()


@dataclass(frozen=True)
class ItemPrototypeSpec(WorldRecord):
    keywords: tuple[str, ...] = ()
    family_id: str = ""
    category: str = ""
    short_description: str = ""
    ground_description: str = ""
    examine_description: str = ""
    equipped_description: str = ""
    damaged_description: str = ""
    broken_description: str = ""
    use_feedback: str = ""
    repair_feedback: str = ""
    crafting_feedback: str = ""
    consumption_feedback: str = ""
    salvage_feedback: str = ""
    material_ids: tuple[str, ...] = ()
    construction_method: str = ""
    maker_tradition: str = ""
    source_regions: tuple[str, ...] = ()
    ownership_default: str = "unowned"
    weight: float = 0.0
    stackable: bool = False
    stack_limit: int = 1
    value: int = 0
    rarity: str = "common"
    level_band: tuple[int, int] = (1, 1)
    quality_profile: str = "standard"
    durability_profile: str = ""
    repair_profile: str = ""
    salvage_profile: str = ""
    merchant_eligible: bool = False
    loot_eligible: bool = False
    recipe_ids: tuple[str, ...] = ()
    equipment_slot: str = ""
    unique: bool = False


@dataclass(frozen=True)
class ItemInstance:
    prototype_id: str
    instance_id: str
    owner: str = ""
    location: str = ""
    container: str = ""
    quantity: int = 1
    condition: str = "sound"
    durability: int | None = None
    charges: int | None = None
    quality: str = "standard"
    maker: str = ""
    custom_inscription: str = ""
    custody: str = "unowned"
    stolen: bool = False
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WeaponSpec:
    prototype_id: str
    family_id: str
    handedness: str = "one"
    damage_type: str = "physical"
    reach: int = 1
    cadence: int = 1
    accuracy: int = 0
    base_damage_budget: int = 0
    operating_cost: int = 0
    stat_requirements: Mapping[str, int] = field(default_factory=dict)
    skill_requirements: Mapping[str, int] = field(default_factory=dict)
    special_properties: tuple[str, ...] = ()
    durability: int = 100
    repair_complexity: int = 1
    value: int = 0
    rarity: str = "common"
    level_band: tuple[int, int] = (1, 1)


@dataclass(frozen=True)
class ArmorSpec:
    prototype_id: str
    family_id: str
    equipment_slot: str
    defense_budget: int = 0
    magic_defense_budget: int = 0
    evasion: int = 0
    movement_cost: int = 0
    stamina_cost: int = 0
    stat_requirements: Mapping[str, int] = field(default_factory=dict)
    job_requirements: Mapping[str, int] = field(default_factory=dict)
    coverage: str = ""
    durability: int = 100
    repair_complexity: int = 1
    value: int = 0
    rarity: str = "common"
    level_band: tuple[int, int] = (1, 1)


@dataclass(frozen=True)
class ShieldSpec(ArmorSpec):
    block_budget: int = 0
    offensive_use: bool = False


@dataclass(frozen=True)
class ToolSpec:
    prototype_id: str
    family_id: str
    gathering_profession: str = ""
    repair_profile: str = ""
    durability: int = 100
    uses: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConsumableSpec:
    prototype_id: str
    effect: Mapping[str, int] = field(default_factory=dict)
    charges: int = 1
    consumption_feedback: str = ""


@dataclass(frozen=True)
class IngredientSpec:
    prototype_id: str
    source_material: str = ""
    gathering_profession: str = ""
    quantity_unit: str = "each"


@dataclass(frozen=True)
class TradeGoodSpec:
    prototype_id: str
    source: str = ""
    route_id: str = ""
    merchant_eligibility: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContainerSpec:
    prototype_id: str
    capacity: int = 1
    locked: bool = False
    custody: str = "unowned"


@dataclass(frozen=True)
class AmmunitionSpec:
    prototype_id: str
    weapon_family: str = ""
    damage_type: str = "physical"
    quantity: int = 1


@dataclass(frozen=True)
class KeyItemSpec:
    prototype_id: str
    unlocks: tuple[str, ...] = ()
    unique: bool = False


@dataclass(frozen=True)
class RelicSpec:
    prototype_id: str
    authored_review: bool = True
    historical_claim: str = ""
    global_state_effect: str = ""


@dataclass(frozen=True)
class RecipeRequirement:
    prototype_id: str
    quantity: int = 1
    stage: str = "input"


@dataclass(frozen=True)
class RecipeAcquisitionSpec:
    mode: str = "known"
    source: str = ""
    requirement: str = ""


@dataclass(frozen=True)
class RecipeSpec(WorldRecord):
    output_prototype: str = ""
    requirements: tuple[RecipeRequirement, ...] = ()
    profession: str = ""
    station: str = ""
    acquisition: RecipeAcquisitionSpec = field(default_factory=RecipeAcquisitionSpec)
    time_cost: int = 0
    output_quantity: int = 1
    quality_logic: str = "fixed"
    failure_behavior: str = "none"
    byproducts: Mapping[str, int] = field(default_factory=dict)
    recycling: bool = False


@dataclass(frozen=True)
class CraftingStationSpec(WorldRecord):
    supported_recipe_families: tuple[str, ...] = ()
    rooms: tuple[str, ...] = ()
    ownership: str = "communal_use"
    fuel_requirements: Mapping[str, int] = field(default_factory=dict)
    availability: str = "available"
    condition: str = "sound"
    repair_requirements: Mapping[str, int] = field(default_factory=dict)
    interaction_text: str = ""


@dataclass(frozen=True)
class MerchantStockProfile:
    stable_id: str
    merchant_id: str
    settlement: str
    shop_type: str
    ordinary_stock: Mapping[str, tuple[int, int]] = field(default_factory=dict)
    conditional_stock: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    restock_interval: int = 0
    supply_sources: Mapping[str, str] = field(default_factory=dict)
    imported_goods: Mapping[str, str] = field(default_factory=dict)
    scarcity_behavior: str = ""
    buy_rules: Mapping[str, Any] = field(default_factory=dict)
    sell_rules: Mapping[str, Any] = field(default_factory=dict)
    markup: float = 1.0
    restrictions: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LootProfile:
    stable_id: str
    source_id: str
    source_class: str
    guaranteed: tuple[str, ...] = ()
    weighted: Mapping[str, int] = field(default_factory=dict)
    quantity_ranges: Mapping[str, tuple[int, int]] = field(default_factory=dict)
    rarity: str = "common"
    threat_band: tuple[int, int] = (1, 1)
    ownership: str = "unowned"
    regional_restrictions: tuple[str, ...] = ()
    production_reason: str = ""
    respawn_behavior: str = "resettable"
    unique_restrictions: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EquipmentSetSpec:
    stable_id: str
    display_name: str
    pieces: tuple[str, ...]
    slots: tuple[str, ...]
    bonuses: Mapping[str, int] = field(default_factory=dict)
    partial_behavior: str = "none"
    tradition: str = ""
    canon_status: CanonStatus = "GENERATED_LOCAL"


@dataclass(frozen=True)
class ItemGenerationProfile:
    stable_id: str
    family_ids: tuple[str, ...] = ()
    material_ids: tuple[str, ...] = ()
    tradition_ids: tuple[str, ...] = ()
    quality_ids: tuple[str, ...] = ()
    level_band: tuple[int, int] = (1, 1)
    allowed_properties: tuple[str, ...] = ()
    item_density: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ItemGenerationManifest:
    packet_id: str
    generator_name: str
    generator_version: str
    generation_seed: int
    item_prototypes: tuple[str, ...] = ()
    item_instances: tuple[str, ...] = ()
    material_ids: tuple[str, ...] = ()
    recipe_ids: tuple[str, ...] = ()
    station_ids: tuple[str, ...] = ()
    merchant_profile_ids: tuple[str, ...] = ()
    loot_profile_ids: tuple[str, ...] = ()
    set_ids: tuple[str, ...] = ()
    output_digest: str = ""


@dataclass(frozen=True)
class ResourceNodeSpec(WorldRecord):
    resource: str = ""
    habitat: str = ""
    recurrence: str = ""
    source_room: str = ""
    economic_use: str = ""


@dataclass(frozen=True)
class EconomyFlowSpec(WorldRecord):
    source: str = ""
    sink: str = ""
    resource: str = ""
    purpose: str = ""
    transport: str = ""
    surplus_or_shortage: str = ""
    inventory_provenance: str = ""


@dataclass(frozen=True)
class EcologyFlowSpec(WorldRecord):
    habitat: str = ""
    creature: str = ""
    energy_source: str = ""
    pressure: str = ""
    recurrence: str = ""
    civilization_relation: str = ""


@dataclass(frozen=True)
class QuestPressureSpec(WorldRecord):
    pressure_type: str = ""
    pressure: str = ""
    affected_records: tuple[str, ...] = ()
    competing_interests: tuple[str, ...] = ()
    resolution_scope: str = ""
    cause: str = ""
    current_severity: str = ""
    duration: str = ""
    recurrence: str = ""
    stakeholders: tuple[str, ...] = ()
    beneficiaries: tuple[str, ...] = ()
    opposing_interests: tuple[str, ...] = ()
    valid_grammars: tuple[str, ...] = ()
    unsuitable_grammars: tuple[str, ...] = ()
    escalation_behavior: str = ""
    resolution_conditions: tuple[str, ...] = ()
    partial_resolution_conditions: tuple[str, ...] = ()
    world_state_dependencies: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


# Quest records intentionally live beside the other Aethryn compiler records rather than in the
# legacy seed TypedDict.  The runtime adapter accepts both shapes, so old authored quest files keep
# their ids and progress while packets can ship the complete structured form.
@dataclass(frozen=True)
class QuestStateSpec:
    stable_id: str
    display_name: str = ""
    terminal: bool = False
    failure: bool = False
    ongoing: bool = False


@dataclass(frozen=True)
class QuestGrammarSpec:
    stable_id: str
    required_states: tuple[str, ...] = ()
    optional_states: tuple[str, ...] = ()
    allowed_event_types: tuple[str, ...] = ()
    required_references: tuple[str, ...] = ()
    failure_behavior: str = ""
    completion_behavior: str = ""
    valid_effect_types: tuple[str, ...] = ()
    validation_rules: tuple[str, ...] = ()


@dataclass(frozen=True)
class QuestTransitionSpec:
    source_state: str
    event_type: str
    destination_state: str
    target_id: str = ""
    condition: Mapping[str, Any] = field(default_factory=dict)
    effect_ids: tuple[str, ...] = ()
    idempotency: str = "once"


@dataclass(frozen=True)
class QuestObjectiveSpec:
    stable_id: str
    label: str = ""
    objective_type: str = ""
    target_ids: tuple[str, ...] = ()
    quantity: int = 1
    quality: str = ""
    locations: tuple[str, ...] = ()
    party_credit: str = "individual"
    optional: bool = False
    hidden: bool = False
    completion_event: str = ""
    failure_condition: str = ""


@dataclass(frozen=True)
class QuestTriggerSpec:
    event_type: str
    target_id: str = ""
    required_state: str = ""
    scope: str = "personal"
    conditions: Mapping[str, Any] = field(default_factory=dict)
    transition_id: str = ""
    idempotency: str = "once"


@dataclass(frozen=True)
class QuestConditionSpec:
    stable_id: str
    condition_type: str = ""
    target: str = ""
    values: tuple[str, ...] = ()
    negate: bool = False


@dataclass(frozen=True)
class QuestChoiceSpec:
    stable_id: str
    text: str = ""
    destination_state: str = ""
    entry_condition: Mapping[str, Any] = field(default_factory=dict)
    effect_ids: tuple[str, ...] = ()
    reward_ids: tuple[str, ...] = ()
    reputation_changes: Mapping[str, int] = field(default_factory=dict)
    follow_up_ids: tuple[str, ...] = ()
    reversible: bool = False
    consequence_scope: str = "personal"


@dataclass(frozen=True)
class QuestBranchSpec:
    stable_id: str
    choices: tuple[QuestChoiceSpec, ...] = ()
    convergence_state: str = ""


@dataclass(frozen=True)
class QuestFailureSpec:
    state: str
    text: str = ""
    retry: str = "restart"
    restart_location: str = ""
    cooldown: int = 0
    retain_progress: bool = False
    world_effect_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class QuestRewardSpec:
    stable_id: str
    reward_type: str = "xp"
    amount: int = 0
    item_id: str = ""
    budget: int = 0
    repeatable: bool = False
    party_distribution: str = "individual"
    contribution_required: int = 0


@dataclass(frozen=True)
class QuestWorldEffectSpec:
    stable_id: str
    effect_type: str = ""
    target: str = ""
    scope: str = "personal"
    duration: str = ""
    persistence: str = "session"
    reversible: bool = False
    reset_behavior: str = ""
    conflict_behavior: str = ""


@dataclass(frozen=True)
class QuestProseSpec:
    title: str = ""
    summary: str = ""
    discovery: str = ""
    acceptance: str = ""
    journal: str = ""
    current_objective: str = ""
    progress: str = ""
    optional_objective: str = ""
    branch_choice: str = ""
    success: str = ""
    failure: str = ""
    abandonment: str = ""
    reward_summary: str = ""
    aftermath: str = ""
    unresolved_remainder: str = ""


@dataclass(frozen=True)
class QuestSpec:
    stable_id: str
    display_name: str = ""
    canon_status: CanonStatus = "GENERATED_LOCAL"
    quest_type: str = ""
    scope: str = "personal"
    region: str = ""
    zone: str = ""
    pressure_id: str = ""
    threat_range: tuple[int, int] = (0, 0)
    recommended_party_size: int = 1
    repeatability: str = "one_shot"
    start_state: str = "offered"
    states: tuple[QuestStateSpec, ...] = ()
    transitions: tuple[QuestTransitionSpec, ...] = ()
    objectives: tuple[QuestObjectiveSpec, ...] = ()
    triggers: tuple[QuestTriggerSpec, ...] = ()
    failures: tuple[QuestFailureSpec, ...] = ()
    rewards: tuple[QuestRewardSpec, ...] = ()
    consequences: tuple[QuestWorldEffectSpec, ...] = ()
    prose: QuestProseSpec = field(default_factory=QuestProseSpec)
    source_design_ids: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)
    generation_seed: int = 0
    generator_version: str = ""


@dataclass(frozen=True)
class QuestInstance:
    quest_id: str
    owner_id: str
    state: str
    scope: str = "personal"
    history: tuple[Mapping[str, Any], ...] = ()
    reward_claimed: bool = False
    abandoned: bool = False


@dataclass(frozen=True)
class PartyQuestState:
    quest_id: str
    party_id: str
    members: tuple[str, ...] = ()
    state: str = ""
    contributions: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ContributionRecord:
    event_id: str
    participant_id: str
    amount: int = 1
    kind: str = "progress"
    timestamp: int = 0


@dataclass(frozen=True)
class QuestArcSpec:
    stable_id: str
    quest_ids: tuple[str, ...] = ()
    prerequisites: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    branch_points: tuple[str, ...] = ()
    mutually_exclusive_paths: tuple[tuple[str, ...], ...] = ()
    convergence_points: tuple[str, ...] = ()
    finale: str = ""
    post_arc_state: str = ""
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContractTemplateSpec:
    stable_id: str
    regions: tuple[str, ...] = ()
    zones: tuple[str, ...] = ()
    pressure_types: tuple[str, ...] = ()
    objective_pool: tuple[str, ...] = ()
    target_pool: tuple[str, ...] = ()
    threat_range: tuple[int, int] = (0, 0)
    reward_budget: int = 0
    cooldown: int = 0
    anti_repetition: Mapping[str, int] = field(default_factory=dict)
    narrative_variants: tuple[str, ...] = ()
    consequence_duration: str = ""
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PublicEventSpec:
    stable_id: str
    trigger_conditions: Mapping[str, Any] = field(default_factory=dict)
    announcement: str = ""
    preparation_state: str = "preparation"
    active_state: str = "active"
    escalation: tuple[str, ...] = ()
    success_threshold: int = 1
    failure_threshold: int = 0
    participant_reward_ids: tuple[str, ...] = ()
    cooldown: int = 0
    aftermath_effect_ids: tuple[str, ...] = ()
    persistence_scope: str = "regional"
    contribution_policy: str = "meaningful"


@dataclass(frozen=True)
class QuestGenerationProfile:
    stable_id: str
    regions: tuple[str, ...] = ()
    zones: tuple[str, ...] = ()
    allowed_grammars: tuple[str, ...] = ()
    prohibited_grammars: tuple[str, ...] = ()
    complexity: str = "local"
    quest_count_ceiling: int = 0
    threat_range: tuple[int, int] = (0, 0)
    reward_budget: int = 0
    repeatability_limits: Mapping[str, int] = field(default_factory=dict)
    consequence_profiles: tuple[str, ...] = ()
    prose_profile: str = ""


@dataclass(frozen=True)
class QuestGenerationManifest:
    packet_id: str
    quest_ids: tuple[str, ...] = ()
    pressure_ids: tuple[str, ...] = ()
    contract_ids: tuple[str, ...] = ()
    arc_ids: tuple[str, ...] = ()
    public_event_ids: tuple[str, ...] = ()
    digest: str = ""
    generator_version: str = ""


@dataclass(frozen=True)
class WorldStateSpec(WorldRecord):
    key: str = ""
    initial_value: str = ""
    reversible_values: tuple[str, ...] = ()
    visible_projection: str = ""
    persistence_scope: str = ""
    state_gate: StateGateSpec | None = None
    actions: tuple[StateActionSpec, ...] = ()


@dataclass(frozen=True)
class StateGateSpec:
    """A packet-declared condition that keeps a runtime signal active."""

    key: str
    active_values: tuple[str, ...]


@dataclass(frozen=True)
class StateActionSpec:
    """One reversible player action declared by a world-state record."""

    command: str
    target: str
    from_value: str
    to_value: str
    aliases: tuple[str, ...] = ()
    required_item: str = ""
    consume_item: bool = False
    room_id: str = ""
    success_message: str = ""
    already_message: str = ""


@dataclass(frozen=True)
class ActionOutcome:
    """Structured evidence for one attempted packet-declared action."""

    status: ActionStatus
    message: str
    state_key: str = ""
    previous_value: str = ""
    new_value: str = ""
    consumed_item: str = ""


@dataclass(frozen=True)
class GenerationPacket:
    packet_id: str
    target_type: str
    parent_region: str
    parent_zone: str
    canon_status: CanonStatus
    world_purpose: str
    gameplay_purpose: str
    narrative_purpose: str
    inherited_constraints: tuple[str, ...]
    threat_range: tuple[int, int]
    geography_profile: Mapping[str, Any]
    climate_profile: Mapping[str, Any]
    architecture_profile: Mapping[str, Any]
    cultural_profile: Mapping[str, Any]
    economy_profile: Mapping[str, Any]
    ecology_profile: Mapping[str, Any]
    required_connections: tuple[str, ...]
    required_content_counts: Mapping[str, int]
    state_scope: str
    forbidden_content: tuple[str, ...]
    generation_seed: int
    expected_output_paths: tuple[str, ...]
    generator_name: str
    generator_version: str
    source_design_ids: tuple[str, ...]
    records: Mapping[str, tuple[Mapping[str, Any], ...]] = field(default_factory=dict)
    authorization: str = ""
    batch_sequence: int = 1
    source_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationIssue:
    category: str
    code: str
    path: str
    message: str
    authority: str
    action: str
    severity: str = "error"


@dataclass(frozen=True)
class ValidationReport:
    verdict: ValidationVerdict
    issues: tuple[ValidationIssue, ...] = ()
    input_digest: str = ""
    output_digest: str = ""

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")


@dataclass(frozen=True)
class GenerationManifest:
    packet_id: str
    generator_name: str
    generator_version: str
    generation_seed: int
    input_digest: str
    output_digest: str
    records: Mapping[str, int]
    output_paths: tuple[str, ...]
    provenance: Provenance
    validation_verdict: ValidationVerdict
    previous_package: str = ""
    package_schema_version: str = "aethryn-package/1"
    compiler_version: str = "aethryn-compiler/1"
    content_schema_versions: Mapping[str, str] = field(default_factory=dict)
    migration_plan: Mapping[str, Any] = field(default_factory=dict)
    build_cache_key: str = ""


def canonical_payload(value: Any) -> str:
    """Serialize a model or mapping into stable JSON for digesting."""
    payload = asdict(value) if hasattr(value, "__dataclass_fields__") else value
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def content_digest(value: Any) -> str:
    return hashlib.sha256(canonical_payload(value).encode("utf-8")).hexdigest()


def common_metadata(raw: Mapping[str, Any], *, packet: GenerationPacket) -> dict[str, Any]:
    """Return inherited metadata for a generated record without mutating the input mapping."""
    source_ids = _tuple_text(raw.get("source_design_ids", packet.source_design_ids))
    provenance = Provenance(
        source_design_ids=source_ids,
        source_paths=_tuple_text(
            raw.get("source_paths", packet.source_paths or ("content/seeds/aethryn/design",))
        ),
        packet_id=packet.packet_id,
        generation_seed=packet.generation_seed,
        generator_name=packet.generator_name,
        generator_version=packet.generator_version,
        authority=str(raw.get("authority", packet.canon_status)),
        note=str(raw.get("provenance_note", "")),
    )
    return {
        "stable_id": str(raw.get("id", "")),
        "display_name": str(raw.get("display_name", raw.get("name", ""))),
        "canon_status": str(raw.get("canon_status", packet.canon_status)),
        "parent_region": str(raw.get("parent_region", packet.parent_region)),
        "parent_zone": str(raw.get("parent_zone", packet.parent_zone)),
        "source_design_ids": source_ids,
        "generation_seed": packet.generation_seed,
        "generator_name": packet.generator_name,
        "generator_version": packet.generator_version,
        "provenance": provenance,
    }
