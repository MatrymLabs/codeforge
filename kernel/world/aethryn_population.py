"""Deterministic ecology primitives for Aethryn generation packets.

This module is deliberately a sidecar to the existing NPC and combat registries.  A population
record describes a group or a pressure on a zone; only an explicitly materialized individual is
put in ``NPCS`` and therefore becomes a combat target.  The same pure functions are used by the
builder commands, compilation, tests, and read-only runtime projection.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Any

from kernel.world.aethryn_models import (
    AmbientPresenceSpec,
    CreatureSpec,
    CrowdSpec,
    EncounterGroupSpec,
    PopulationManifest,
    PopulationProfile,
    PopulationState,
    RoamingRoute,
    SpawnPool,
    content_digest,
)

POPULATION_RECORD_KINDS = (
    "creatures",
    "creature_specs",
    "population_profiles",
    "spawn_pools",
    "roaming_routes",
    "migration_rules",
    "encounter_groups",
    "crowd_specs",
    "ambient_presence",
    "population_states",
    "population_manifests",
)
GROUP_FORMATIONS = {
    "pack",
    "herd",
    "flock",
    "school",
    "swarm",
    "patrol",
    "caravan",
    "work_crew",
    "hunting_party",
    "raiding_party",
    "warband",
    "civilian_crowd",
}
RARITIES = {"common", "uncommon", "rare", "very_rare", "legendary", "state_dependent"}
NON_BIOLOGICAL_CATEGORIES = {
    "construct",
    "undead",
    "artificial_organism",
    "anomalous_entity",
    "metaphysical_phenomenon",
}


def _texts(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value) if isinstance(value, (list, tuple)) else ()


def _rooms(row: Mapping[str, Any]) -> tuple[str, ...]:
    values = row.get("candidate_rooms", row.get("rooms", ()))
    if isinstance(values, str):
        return (values,)
    return tuple(str(value) for value in values or ())


def _bounds(value: Any, default: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), int(value[1])
    return default


def _mapping_bounds(value: Any) -> dict[str, tuple[int, int]]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _bounds(item) for key, item in value.items()}


def _condition_map(value: Any) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _texts(item) for key, item in value.items()}


def population_profile(row: Mapping[str, Any]) -> PopulationProfile:
    return PopulationProfile(
        stable_id=str(row.get("id", row.get("stable_id", ""))),
        creature_id=str(row.get("creature_id", row.get("archetype_id", ""))),
        region=str(row.get("region", row.get("parent_region", ""))),
        zone=str(row.get("zone", row.get("parent_zone", ""))),
        habitat=str(row.get("habitat", "")),
        allowed_room_types=_texts(row.get("allowed_room_types")),
        forbidden_room_types=_texts(row.get("forbidden_room_types")),
        candidate_rooms=_rooms(row),
        population_min=int(row.get("population_min", row.get("minimum", 0))),
        population_max=int(row.get("population_max", row.get("maximum", 0))),
        carrying_capacity=int(row.get("carrying_capacity", 0)),
        spawn_rules=dict(row.get("spawn_rules", row.get("spawn", {})) or {}),
        reset_rules=dict(row.get("reset_rules", row.get("reset", {})) or {}),
        depletion_rules=dict(row.get("depletion_rules", row.get("depletion", {})) or {}),
        recovery_rules=dict(row.get("recovery_rules", row.get("recovery", {})) or {}),
        time_of_day=_texts(row.get("time_of_day")),
        seasons=_texts(row.get("seasons")),
        weather=_texts(row.get("weather")),
        state_conditions=_condition_map(row.get("state_conditions")),
        player_pressure_effects=dict(row.get("player_pressure_effects", {}) or {}),
        migration_routes=_texts(row.get("migration_routes")),
        rarity=str(row.get("rarity", "common")),
        direct_presence_probability=float(row.get("direct_presence_probability", 0.0)),
        ambient_evidence_probability=float(row.get("ambient_evidence_probability", 0.0)),
        hostile_presence_probability=float(row.get("hostile_presence_probability", 0.0)),
        provenance=dict(row.get("provenance", {}) or {}),
    )


def spawn_pool(row: Mapping[str, Any]) -> SpawnPool:
    return SpawnPool(
        stable_id=str(row.get("id", row.get("stable_id", ""))),
        population_id=str(row.get("population_id", "")),
        rooms=_rooms(row),
        forbidden_rooms=_texts(row.get("forbidden_rooms")),
        max_active=int(row.get("max_active", row.get("population_cap", 0))),
        reset_interval=int(row.get("reset_interval", 0)),
        spawn_probability=float(row.get("spawn_probability", 0.0)),
        recurrence=str(row.get("recurrence", "")),
        provenance=dict(row.get("provenance", {}) or {}),
    )


def roaming_route(row: Mapping[str, Any]) -> RoamingRoute:
    return RoamingRoute(
        stable_id=str(row.get("id", row.get("stable_id", ""))),
        population_id=str(row.get("population_id", "")),
        rooms=_rooms(row),
        forbidden_rooms=_texts(row.get("forbidden_rooms")),
        home_room=str(row.get("home_room", row.get("origin_room", ""))),
        origin_area=str(row.get("origin_area", "")),
        movement_interval=max(1, int(row.get("movement_interval", 1))),
        movement_probability=float(row.get("movement_probability", 0.0)),
        max_distance=int(row.get("max_distance", 0)),
        destination_needs=_texts(row.get("destination_needs")),
        closed_exit_behavior=str(row.get("closed_exit_behavior", "return")),
        hazard_behavior=str(row.get("hazard_behavior", "avoid")),
        return_behavior=str(row.get("return_behavior", "return_home")),
        population_cap=int(row.get("population_cap", 0)),
        provenance=dict(row.get("provenance", {}) or {}),
    )


def encounter_group(row: Mapping[str, Any]) -> EncounterGroupSpec:
    composition = {
        str(key): _bounds(value, (1, 1))
        for key, value in (row.get("composition", {}) or {}).items()
    }
    return EncounterGroupSpec(
        stable_id=str(row.get("id", row.get("stable_id", ""))),
        formation=str(row.get("formation", "pack")),
        composition=composition,
        minimum_size=int(row.get("minimum_size", row.get("min_size", 1))),
        maximum_size=int(row.get("maximum_size", row.get("max_size", 1))),
        leader_id=str(row.get("leader_id", "")),
        formation_behavior=str(row.get("formation_behavior", "cohesive")),
        cohesion=float(row.get("cohesion", 1.0)),
        shared_aggression=bool(row.get("shared_aggression", False)),
        ally_assistance=bool(row.get("ally_assistance", False)),
        pursuit_distance=int(row.get("pursuit_distance", 0)),
        retreat_conditions=_texts(row.get("retreat_conditions")),
        leader_loss_behavior=str(row.get("leader_loss_behavior", "scatter")),
        casualty_behavior=str(row.get("casualty_behavior", "retreat_at_threshold")),
        reinforcement_behavior=str(row.get("reinforcement_behavior", "none")),
        loot_ownership=str(row.get("loot_ownership", "group")),
        spawn_rules=dict(row.get("spawn_rules", {}) or {}),
        recurrence=str(row.get("recurrence", "")),
        provenance=dict(row.get("provenance", {}) or {}),
    )


def crowd(row: Mapping[str, Any]) -> CrowdSpec:
    return CrowdSpec(
        stable_id=str(row.get("id", row.get("stable_id", ""))),
        rooms=_rooms(row),
        population_min=int(row.get("population_min", row.get("minimum", 0))),
        population_max=int(row.get("population_max", row.get("maximum", 0))),
        composition=_mapping_bounds(row.get("composition", {})),
        schedule=_texts(row.get("schedule")),
        density_states=_mapping_bounds(row.get("density_states", {})),
        collective_description=str(row.get("collective_description", "")),
        ambient_actions=_texts(row.get("ambient_actions")),
        mood=str(row.get("mood", "steady")),
        danger_reaction=str(row.get("danger_reaction", "disperse_to_shelter")),
        dispersal_behavior=str(row.get("dispersal_behavior", "return_on_next_schedule")),
        representative_npcs=_texts(row.get("representative_npcs")),
        accessibility_description=str(row.get("accessibility_description", "")),
        provenance=dict(row.get("provenance", {}) or {}),
    )


def ambient_presence(row: Mapping[str, Any]) -> AmbientPresenceSpec:
    return AmbientPresenceSpec(
        stable_id=str(row.get("id", row.get("stable_id", ""))),
        room=str(row.get("room", "")),
        rooms=_rooms(row),
        population_id=str(row.get("population_id", "")),
        evidence_type=str(row.get("evidence_type", "sign")),
        text=str(row.get("text", row.get("description", ""))),
        activity_lines=_texts(row.get("activity_lines")),
        probability=float(row.get("probability", 0.0)),
        time_of_day=_texts(row.get("time_of_day")),
        state_conditions=_condition_map(row.get("state_conditions")),
        provenance=dict(row.get("provenance", {}) or {}),
    )


def creature_spec(row: Mapping[str, Any]) -> CreatureSpec:
    """Adapt a packet creature row to the typed authoring model."""
    return CreatureSpec(
        stable_id=str(row.get("id", "")),
        display_name=str(row.get("display_name", row.get("name", ""))),
        canon_status=str(row.get("canon_status", "GENERATED_LOCAL")),  # type: ignore[arg-type]
        parent_region=str(row.get("parent_region", "")),
        parent_zone=str(row.get("parent_zone", "")),
        source_design_ids=_texts(row.get("source_design_ids")),
        generation_seed=int(row.get("generation_seed", 0)),
        generator_name=str(row.get("generator_name", "")),
        generator_version=str(row.get("generator_version", "")),
        provenance=dict(row.get("provenance", {}) or {}),  # type: ignore[arg-type]
        keywords=_texts(row.get("keywords")),
        creature_category=str(row.get("creature_category", "biological")),
        habitat=str(row.get("habitat", "")),
        allowed_regions=_texts(row.get("allowed_regions")),
        climate_tolerance=_texts(row.get("climate_tolerance")),
        threat_range=_bounds(row.get("threat_range")),
        description=str(row.get("description", "")),
        room_presence_description=str(row.get("room_presence_description", "")),
        examine_description=str(row.get("examine_description", "")),
        behavior=str(row.get("behavior", "")),
        intelligence=str(row.get("intelligence", "")),
        disposition=str(row.get("disposition", "")),
        social_organization=str(row.get("social_organization", "")),
        activity_period=str(row.get("activity_period", "")),
        movement_behavior=str(row.get("movement_behavior", "")),
        diet_or_energy_source=str(row.get("diet_or_energy_source", "")),
        predators=_texts(row.get("predators")),
        prey_or_resource_pressure=str(row.get("prey_or_resource_pressure", "")),
        reproduction_or_recurrence=str(row.get("reproduction_or_recurrence", "")),
        seasonal_behavior=str(row.get("seasonal_behavior", "")),
        ecological_role=str(row.get("ecological_role", "")),
        relationship_to_civilization=str(row.get("relationship_to_civilization", "")),
        reason_for_persistence=str(row.get("reason_for_persistence", "")),
        combat_role=str(row.get("combat_role", "")),
        abilities=_texts(row.get("abilities")),
        resistances=dict(row.get("resistances", {}) or {}),
        vulnerabilities=dict(row.get("vulnerabilities", {}) or {}),
        retreat_behavior=str(row.get("retreat_behavior", "")),
        pursuit_behavior=str(row.get("pursuit_behavior", "")),
        assistance_behavior=str(row.get("assistance_behavior", "")),
        loot_outputs=_texts(row.get("loot_outputs", row.get("loot", ()))),
        crafting_outputs=_texts(row.get("crafting_outputs")),
        rarity=str(row.get("rarity", "common")),
        provenance_note=str(row.get("provenance_note", "")),
    )


def _stable_roll(seed: int, key: str, tick: int = 0) -> float:
    digest = hashlib.sha256(f"{seed}:{key}:{tick}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64)


def _condition_active(conditions: Mapping[str, Sequence[str]], state: Mapping[str, str]) -> bool:
    return all(
        str(state.get(key)) in {str(value) for value in values}
        for key, values in conditions.items()
    )


def _cap(profile: PopulationProfile) -> int:
    maximum = max(0, profile.population_max)
    if profile.carrying_capacity > 0:
        maximum = min(maximum, profile.carrying_capacity) if maximum else profile.carrying_capacity
    return max(profile.population_min, maximum)


def simulate_population(
    records: Mapping[str, Sequence[Mapping[str, Any]]],
    zone: str,
    ticks: int = 1,
    seed: int = 0,
    *,
    state: Mapping[str, str] | None = None,
    previous: PopulationManifest | None = None,
) -> PopulationManifest:
    """Simulate only aggregate population state; never instantiate NPCs.

    The result is a stable manifest suitable for a preview command or a zone-scoped persistence
    store.  The simple pressure/recovery rule intentionally remains data-driven: ``depletion``
    may contain ``kill_threshold`` and ``recovery_per_tick`` without making the runtime invent
    biology that the packet did not declare.
    """
    state_values = state or {}
    profiles = [population_profile(row) for row in records.get("population_profiles", ())]
    routes = [roaming_route(row) for row in records.get("roaming_routes", ())]
    evidence_rows = [ambient_presence(row) for row in records.get("ambient_presence", ())]
    states: list[PopulationState] = []
    direct: dict[str, list[str]] = {}
    ambient: dict[str, list[str]] = {}
    roaming: dict[str, list[str]] = {}
    evidence: dict[str, list[str]] = {}
    previous_states = {item.population_id: item for item in previous.states} if previous else {}
    for profile in sorted(
        (p for p in profiles if not p.zone or p.zone == zone), key=lambda p: p.stable_id
    ):
        if profile.state_conditions and not _condition_active(
            profile.state_conditions, state_values
        ):
            continue
        rooms = tuple(sorted(profile.candidate_rooms))
        cap = _cap(profile)
        # Population size is deterministic, bounded, and never lower than the declared minimum.
        span = max(0, cap - profile.population_min)
        count = profile.population_min + (
            int(_stable_roll(seed, profile.stable_id, ticks) * (span + 1)) if span else 0
        )
        old = previous_states.get(profile.stable_id)
        if old is not None:
            recovery = int(profile.recovery_rules.get("recovery_per_tick", 0))
            count = min(cap, max(profile.population_min, old.current_count + max(0, recovery)))
        occupied = tuple(
            room
            for index, room in enumerate(rooms)
            if count
            and _stable_roll(seed, f"{profile.stable_id}:{room}", ticks)
            < profile.direct_presence_probability
            and index < count
        )
        ambient_rooms = tuple(
            room
            for room in rooms
            if _stable_roll(seed, f"ambient:{profile.stable_id}:{room}", ticks)
            < profile.ambient_evidence_probability
        )
        if occupied and profile.creature_id:
            direct.setdefault(profile.creature_id, []).extend(occupied)
        if ambient_rooms and profile.creature_id:
            ambient.setdefault(profile.creature_id, []).extend(ambient_rooms)
        depleted_until = 0
        states.append(
            PopulationState(
                population_id=profile.stable_id,
                zone=zone,
                tick=ticks,
                current_count=min(count, cap),
                occupied_rooms=occupied,
                ambient_rooms=ambient_rooms,
                depleted_until=depleted_until,
                persistence_scope=str(profile.reset_rules.get("persistence_scope", "zone")),
                seed=seed,
                generator_version=str(profile.provenance.get("generator_version", "")),
            )
        )
    for route in sorted(routes, key=lambda item: item.stable_id):
        if not route.rooms or route.population_id not in {p.stable_id for p in profiles}:
            continue
        if (
            ticks % route.movement_interval == 0
            and _stable_roll(seed, route.stable_id, ticks) < route.movement_probability
        ):
            index = int(
                _stable_roll(seed, f"destination:{route.stable_id}", ticks) * len(route.rooms)
            )
        else:
            index = 0
        destination = route.rooms[index % len(route.rooms)]
        if destination in set(route.forbidden_rooms):
            destination = route.home_room or route.rooms[0]
        roaming.setdefault(route.stable_id, []).append(destination)
    for row in evidence_rows:
        if row.state_conditions and not _condition_active(row.state_conditions, state_values):
            continue
        candidates = row.rooms or ((row.room,) if row.room else ())
        for room in candidates:
            if _stable_roll(seed, row.stable_id, ticks) <= row.probability:
                evidence.setdefault(room, []).append(row.text)

    def frozen(mapping: Mapping[str, list[str]]) -> dict[str, tuple[str, ...]]:
        return {key: tuple(value) for key, value in sorted(mapping.items())}

    payload = {
        "zone": zone,
        "tick": ticks,
        "states": [asdict(item) for item in states],
        "direct_presence": frozen(direct),
        "ambient_presence": frozen(ambient),
        "roaming_groups": frozen(roaming),
        "evidence": frozen(evidence),
    }
    return PopulationManifest(
        zone=zone,
        tick=ticks,
        states=tuple(states),
        direct_presence=frozen(direct),
        ambient_presence=frozen(ambient),
        roaming_groups=frozen(roaming),
        evidence=frozen(evidence),
        digest=content_digest(payload),
    )


class PopulationStateStore:
    """Small declared-scope store for aggregate state; it never stores individual NPC objects."""

    def __init__(self, records: Mapping[str, Sequence[Mapping[str, Any]]], *, seed: int = 0):
        self.records = records
        self.seed = seed
        self.manifests: dict[str, PopulationManifest] = {}

    def tick(
        self, zone: str, *, ticks: int = 1, state: Mapping[str, str] | None = None
    ) -> PopulationManifest:
        previous = self.manifests.get(zone)
        manifest = simulate_population(
            self.records, zone, ticks, self.seed, state=state, previous=previous
        )
        self.manifests[zone] = manifest
        return manifest

    def deplete(self, zone: str, population_id: str, amount: int = 1) -> PopulationManifest:
        current = self.manifests.get(zone) or self.tick(zone)
        states = []
        for item in current.states:
            if item.population_id == population_id:
                states.append(
                    PopulationState(
                        **{
                            **asdict(item),
                            "current_count": max(0, item.current_count - max(0, amount)),
                            "depleted_until": item.tick + 1,
                        }
                    )
                )
            else:
                states.append(item)
        manifest = PopulationManifest(
            zone=zone,
            tick=current.tick,
            states=tuple(states),
            direct_presence=current.direct_presence,
            ambient_presence=current.ambient_presence,
            roaming_groups=current.roaming_groups,
            evidence=current.evidence,
            digest=content_digest([asdict(item) for item in states]),
        )
        self.manifests[zone] = manifest
        return manifest

    def reset(self, zone: str | None = None, *, scope: str = "zone") -> None:
        if scope in {"world", "zone"}:
            if zone is None or scope == "world":
                self.manifests.clear()
            else:
                self.manifests.pop(zone, None)

    def snapshot(self) -> dict[str, PopulationManifest]:
        return dict(self.manifests)

    def restore(self, snapshot: Mapping[str, PopulationManifest]) -> None:
        self.manifests = dict(snapshot)


class PopulationFinding(tuple):
    """Small tuple-compatible finding so validators can use it without a second issue model."""

    __slots__ = ()

    def __new__(cls, code: str, path: str, message: str, action: str, severity: str = "error"):
        return tuple.__new__(cls, (code, path, message, action, severity))

    @property
    def code(self) -> str:
        return self[0]

    @property
    def path(self) -> str:
        return self[1]

    @property
    def message(self) -> str:
        return self[2]

    @property
    def action(self) -> str:
        return self[3]

    @property
    def severity(self) -> str:
        return self[4]


def validate_population_records(
    records: Mapping[str, Sequence[Mapping[str, Any]]],
    known_rooms: set[str] | frozenset[str],
) -> tuple[PopulationFinding, ...]:
    """Validate habitat, caps, group composition, bounded routes, and population references."""
    findings: list[PopulationFinding] = []
    creature_rows = {
        str(row.get("id")): row for row in records.get("creatures", ()) if row.get("id")
    }
    creature_rows.update(
        {str(row.get("id")): row for row in records.get("creature_specs", ()) if row.get("id")}
    )
    profile_rows = {
        str(row.get("id")): row for row in records.get("population_profiles", ()) if row.get("id")
    }
    for index, row in enumerate(creature_rows.values()):
        path = f"records.creatures[{index}]"
        category = str(row.get("creature_category", "biological"))
        if not row.get("habitat") and category not in NON_BIOLOGICAL_CATEGORIES:
            findings.append(
                PopulationFinding(
                    "missing_habitat",
                    f"{path}.habitat",
                    "biological creature has no habitat",
                    "declare a compatible habitat",
                )
            )
        if not row.get("diet_or_energy_source"):
            findings.append(
                PopulationFinding(
                    "missing_energy_input",
                    f"{path}.diet_or_energy_source",
                    "creature has no food, energy, or operating input",
                    "declare food, energy, or a supported input",
                )
            )
        if not row.get("reproduction_or_recurrence"):
            findings.append(
                PopulationFinding(
                    "missing_recurrence",
                    f"{path}.reproduction_or_recurrence",
                    "creature has no reproduction, manufacture, summoning, persistence, or "
                    "recurrence mechanism",
                    "declare an appropriate recurrence mechanism",
                )
            )
        if str(row.get("rarity", "common")) not in RARITIES:
            findings.append(
                PopulationFinding(
                    "invalid_rarity",
                    f"{path}.rarity",
                    "creature rarity is not supported",
                    f"use one of {sorted(RARITIES)}",
                )
            )
        forbidden_lore = " ".join(str(value).casefold() for value in row.values())
        if any(
            term in forbidden_lore
            for term in (
                "forge metaphysics",
                "ember metaphysics",
                "forge-born",
                "ember-born",
                "unforging",
            )
        ):
            findings.append(
                PopulationFinding(
                    "legacy_bestiary_metaphysics",
                    path,
                    "legacy bestiary metaphysics are not active Aethryn canon",
                    "remove obsolete Forge, Ember, or Unforging claims",
                )
            )
    for index, row in enumerate(profile_rows.values()):
        path = f"records.population_profiles[{index}]"
        profile = population_profile(row)
        if not profile.creature_id and not row.get("archetype_id"):
            findings.append(
                PopulationFinding(
                    "missing_population_subject",
                    f"{path}.creature_id",
                    "population profile has no creature or social archetype",
                    "reference a creature spec or NPC archetype",
                )
            )
        if profile.population_min < 0 or profile.population_max < profile.population_min:
            findings.append(
                PopulationFinding(
                    "invalid_population_bounds",
                    path,
                    "population bounds are inconsistent",
                    "set 0 <= population_min <= population_max",
                )
            )
        if profile.carrying_capacity and profile.population_max > profile.carrying_capacity:
            findings.append(
                PopulationFinding(
                    "over_capacity",
                    f"{path}.population_max",
                    "population maximum exceeds carrying capacity",
                    "lower the maximum or raise the declared carrying capacity",
                )
            )
        if set(profile.allowed_room_types) & set(profile.forbidden_room_types):
            findings.append(
                PopulationFinding(
                    "habitat_room_type_conflict",
                    path,
                    "population allows and forbids the same room type",
                    "remove the overlap from allowed_room_types or forbidden_room_types",
                )
            )
        subject = creature_rows.get(profile.creature_id)
        if (
            subject
            and subject.get("allowed_regions")
            and profile.region not in set(_texts(subject.get("allowed_regions")))
        ):
            findings.append(
                PopulationFinding(
                    "habitat_region_conflict",
                    f"{path}.region",
                    f"population region {profile.region!r} is outside the creature's "
                    "allowed regions",
                    "move the profile to an allowed region or correct the creature habitat",
                )
            )
        if not profile.candidate_rooms:
            findings.append(
                PopulationFinding(
                    "empty_candidate_rooms",
                    f"{path}.candidate_rooms",
                    "population profile has no bounded room pool",
                    "declare candidate rooms or a packet route",
                )
            )
        for room in profile.candidate_rooms:
            if room not in known_rooms:
                findings.append(
                    PopulationFinding(
                        "unknown_population_room",
                        f"{path}.candidate_rooms",
                        f"population names unknown room {room!r}",
                        "use a room emitted by the packet or authored seed",
                    )
                )
        for field_name in (
            "direct_presence_probability",
            "ambient_evidence_probability",
            "hostile_presence_probability",
        ):
            value = float(getattr(profile, field_name))
            if not 0.0 <= value <= 1.0:
                findings.append(
                    PopulationFinding(
                        "invalid_probability",
                        f"{path}.{field_name}",
                        "population probability must be between 0 and 1",
                        "use a normalized probability",
                    )
                )
    for index, row in enumerate(records.get("encounter_groups", ())):
        path = f"records.encounter_groups[{index}]"
        group = encounter_group(row)
        if group.formation not in GROUP_FORMATIONS:
            findings.append(
                PopulationFinding(
                    "invalid_group_formation",
                    f"{path}.formation",
                    f"formation {group.formation!r} is unsupported",
                    f"use one of {sorted(GROUP_FORMATIONS)}",
                )
            )
        if group.minimum_size < 1 or group.maximum_size < group.minimum_size:
            findings.append(
                PopulationFinding(
                    "invalid_group_size",
                    path,
                    "encounter group size bounds are inconsistent",
                    "set 1 <= minimum_size <= maximum_size",
                )
            )
        if not group.composition:
            findings.append(
                PopulationFinding(
                    "empty_group_composition",
                    f"{path}.composition",
                    "encounter group has no composition",
                    "name the related creatures or archetypes",
                )
            )
        for subject in group.composition:
            if subject not in creature_rows and subject not in {
                str(row.get("id")) for row in records.get("npcs", ())
            }:
                findings.append(
                    PopulationFinding(
                        "unknown_group_member",
                        f"{path}.composition",
                        f"group references unknown subject {subject!r}",
                        "reference a declared creature or NPC archetype",
                    )
                )
    for index, row in enumerate(records.get("roaming_routes", ())):
        path = f"records.roaming_routes[{index}]"
        route = roaming_route(row)
        if not route.rooms:
            findings.append(
                PopulationFinding(
                    "empty_roaming_route",
                    f"{path}.rooms",
                    "roaming route has no allowed room pool",
                    "declare a bounded route",
                )
            )
        for room in route.rooms + route.forbidden_rooms:
            if room not in known_rooms:
                findings.append(
                    PopulationFinding(
                        "unknown_roaming_room",
                        f"{path}.rooms",
                        f"roaming route names unknown room {room!r}",
                        "use a room emitted by the packet or authored seed",
                    )
                )
        if set(route.rooms) & set(route.forbidden_rooms):
            findings.append(
                PopulationFinding(
                    "roaming_allow_forbid_conflict",
                    path,
                    "roaming route allows and forbids the same room",
                    "remove the room from one side of the route",
                )
            )
        if not 0.0 <= route.movement_probability <= 1.0:
            findings.append(
                PopulationFinding(
                    "invalid_roaming_probability",
                    f"{path}.movement_probability",
                    "roaming probability must be between 0 and 1",
                    "use a normalized probability",
                )
            )
    for kind in ("crowd_specs", "ambient_presence"):
        for index, row in enumerate(records.get(kind, ())):
            path = f"records.{kind}[{index}]"
            rooms = _rooms(row)
            for room in rooms:
                if room not in known_rooms:
                    findings.append(
                        PopulationFinding(
                            "unknown_presence_room",
                            f"{path}.rooms",
                            f"presence record names unknown room {room!r}",
                            "use a room emitted by the packet or authored seed",
                        )
                    )
            if kind == "crowd_specs" and int(
                row.get("population_max", row.get("maximum", 0))
            ) < int(row.get("population_min", row.get("minimum", 0))):
                findings.append(
                    PopulationFinding(
                        "invalid_crowd_bounds",
                        path,
                        "crowd population bounds are inconsistent",
                        "set 0 <= minimum <= maximum",
                    )
                )
    return tuple(findings)


def population_record_kinds(records: Mapping[str, Sequence[Mapping[str, Any]]]) -> tuple[str, ...]:
    return tuple(kind for kind in POPULATION_RECORD_KINDS if kind in records)
