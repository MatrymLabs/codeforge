"""Multi-region Aethryn World Package compiler.

This is the second Seed Compiler milestone. It composes the existing manifest-driven region
compiler into one connected world: canonical Aethryn region profiles are loaded from seed data,
regions are generated deterministically, the canonical land/sea graph is induced over the selected
profiles, and cross-region routes are emitted into one hostable World Package.

The compiler still deliberately stops at the domain surface it can prove today. Quests, economy,
crafting, and authored item packs remain later compiler phases; the assembled artifact contains the
generated rooms, life, zones, graph, and build/assembly manifests that its current loaders
can prove.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from kernel.domains.game_linker import GameSpec, RoomSpec
from kernel.domains.hosted_world import HOSTABLE, UNHOSTABLE, HostedWorld, install_world
from kernel.domains.manifest_compiler import (
    AethrynRegionProfile,
    CompiledAethrynRegion,
    ManifestCompilerError,
    compile_aethryn_region,
)
from kernel.seed_package import BuildManifest
from kernel.world import worldgraph
from kernel.world.seed import (
    SEEDS_ROOT,
    BlueprintError,
    Npc,
    inspect_world_links,
    load_items,
    load_npcs,
    load_rooms,
    load_zones,
)


class WorldCompilerError(ValueError):
    """A selected region set cannot be assembled into one connected world."""


@dataclass(frozen=True)
class CompiledAethrynWorld:
    """A complete current-surface Aethryn World Package before installation."""

    manifest: BuildManifest
    profiles: tuple[AethrynRegionProfile, ...]
    regions: tuple[CompiledAethrynRegion, ...]
    graph: dict[str, Any]
    rooms: dict[str, dict[str, Any]]
    npcs: dict[str, Npc]
    items: dict[str, dict[str, Any]]
    zones: dict[str, dict[str, Any]]
    start_region: str

    @property
    def actual_rooms(self) -> int:
        return len(self.rooms)

    @property
    def actual_monsters(self) -> int:
        return len(self.npcs)

    def game_spec(self) -> GameSpec:
        """Project the assembled room graph into the existing World Package linker."""
        return GameSpec(
            region="Aethryn",
            rooms=tuple(
                RoomSpec(
                    label=label,
                    name=str(room.get("name", "")),
                    desc=str(room.get("desc", "")),
                    exits=dict(room.get("exits", {})),
                )
                for label, room in self.rooms.items()
            ),
            start=next(
                region.region.start
                for region in self.regions
                if region.profile.region_id == self.start_region
            ),
        )

    def assembly_manifest(self) -> dict[str, Any]:
        """Return the auditable machine-readable assembly summary."""
        return {
            **self.manifest.to_dict(),
            "assembly": {
                "start_region": self.start_region,
                "regions": [profile.region_id for profile in self.profiles],
                "actual_rooms": self.actual_rooms,
                "actual_monsters": self.actual_monsters,
                "graph": self.graph,
            },
        }


def _default_seed(region_id: str) -> int:
    """Derive a stable, process-independent generator seed from a canon region id."""
    return int.from_bytes(hashlib.sha256(region_id.encode("utf-8")).digest()[:4], "big")


def load_aethryn_profiles(path: Path | None = None) -> tuple[AethrynRegionProfile, ...]:
    """Build compiler profiles from the shipped Aethryn zone data.

    This keeps the compiler's region roster aligned with the existing seed rather than duplicating
    a second list of 14 names, level bands, and biomes in Python. Geometry and anchor fractions are
    compiler defaults until each region receives deeper authored profile data.
    """
    where = path or (SEEDS_ROOT / "aethryn" / "zones.yaml")
    raw = yaml.safe_load(where.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise WorldCompilerError(f"Aethryn zones file is not a mapping: {where}")
    profiles: list[AethrynRegionProfile] = []
    for zone_id, row in raw.items():
        if not isinstance(zone_id, str) or not zone_id.endswith("_zone"):
            continue
        if not isinstance(row, dict):
            raise WorldCompilerError(f"Aethryn zone {zone_id!r} must be a mapping")
        region_id = zone_id.removesuffix("_zone")
        try:
            display = str(row["region"])
            biome = str(row["biome"])
            level_min = int(row["level_min"])
            level_max = int(row["level_max"])
        except (KeyError, TypeError, ValueError) as exc:
            raise WorldCompilerError(
                f"Aethryn zone {zone_id!r} is missing compiler fields"
            ) from exc
        display_name = "The Veridia Wilds" if region_id == "veridia" else f"{display} Wilds"
        profiles.append(
            AethrynRegionProfile(
                region_id=region_id,
                display_name=display_name,
                biome=biome,
                level_min=level_min,
                level_max=level_max,
                seed=_default_seed(region_id),
                landmarks=(
                    (0.15, 0.18, f"{display} Cairn", "site"),
                    (0.48, 0.48, f"{display} Moot", "site"),
                    (0.82, 0.78, f"{display} Keep", "dungeon"),
                ),
            )
        )
    if not profiles:
        raise WorldCompilerError(f"Aethryn zones file contains no compiler profiles: {where}")
    return tuple(profiles)


def _validate_graph(graph: dict[str, Any], selected: set[str], start_region: str) -> None:
    """Validate the induced graph without requiring unselected canon regions to be present."""
    rows = graph.get("regions")
    seas = graph.get("seas")
    if not isinstance(rows, dict) or set(rows) != selected:
        raise WorldCompilerError("assembled graph rows must exactly match selected region profiles")
    if not isinstance(seas, list) or not seas:
        raise WorldCompilerError("assembled graph needs at least one sea or land route")
    if start_region not in selected:
        raise WorldCompilerError(f"assembled graph has no start region {start_region!r}")
    for region_id, row in rows.items():
        if not isinstance(row, dict):
            raise WorldCompilerError(f"assembled graph row {region_id!r} must be a mapping")
        for neighbour in row.get("land", []):
            if neighbour == region_id or neighbour not in selected:
                raise WorldCompilerError(
                    f"assembled graph {region_id!r} has invalid land neighbour {neighbour!r}"
                )
        for sea in row.get("seas", []):
            if sea not in seas:
                raise WorldCompilerError(f"assembled graph {region_id!r} has unknown sea {sea!r}")
    unreachable = worldgraph.unreachable_regions(start_region, graph)
    if unreachable:
        raise WorldCompilerError(f"assembled graph has unreachable regions: {unreachable}")


def _induced_graph(
    profiles: tuple[AethrynRegionProfile, ...], start_region: str, source: dict[str, Any] | None
) -> dict[str, Any]:
    """Select the canonical graph rows for the profiles being compiled."""
    canonical = source or worldgraph.load_graph()
    rows = canonical.get("regions")
    if not isinstance(rows, dict):
        raise WorldCompilerError("canonical Aethryn graph has no region rows")
    selected = {profile.region_id for profile in profiles}
    if len(selected) != len(profiles):
        raise WorldCompilerError("Aethryn region profile ids must be unique")
    missing = sorted(selected - set(rows))
    if missing:
        raise WorldCompilerError(f"selected regions are absent from the canonical graph: {missing}")
    graph = {
        "seas": sorted({sea for region_id in selected for sea in rows[region_id].get("seas", [])}),
        "regions": {
            region_id: {
                "land": [n for n in rows[region_id].get("land", []) if n in selected],
                "seas": list(rows[region_id].get("seas", [])),
            }
            for region_id in sorted(selected)
        },
    }
    _validate_graph(graph, selected, start_region)
    return graph


def _zone_records(regions: Iterable[CompiledAethrynRegion]) -> dict[str, dict[str, Any]]:
    """Build disjoint loader-shaped zone records for every compiled region."""
    records: dict[str, dict[str, Any]] = {}
    for compiled in regions:
        profile = compiled.profile
        zone_id = f"compiled_{profile.region_id}"
        records[zone_id] = {
            "name": profile.display_name,
            "rooms": list(compiled.region.rooms),
            "reset_mode": "empty_only",
            "beats_between": 12,
            "region": profile.region_id,
            "level_min": profile.level_min,
            "level_max": profile.level_max,
            "biome": profile.biome,
        }
    return records


def _generated_item_records(npcs: dict[str, Npc]) -> dict[str, dict[str, Any]]:
    """Carry the canonical prototypes required by generated NPC loot into the package."""
    required = {
        item
        for npc in npcs.values()
        for item in (
            *npc.get("drops", []),
            *(name for name in npc.get("loot", {}) if name != "nothing"),
        )
    }
    source = SEEDS_ROOT / "aethryn" / "items.yaml"
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not required.issubset(raw):
        missing = sorted(required - set(raw or {})) if isinstance(raw, dict) else sorted(required)
        raise WorldCompilerError(
            f"canonical Aethryn item pack is missing generated loot: {missing}"
        )
    return {label: dict(raw[label]) for label in sorted(required)}


def _connect_regions(
    rooms: dict[str, dict[str, Any]],
    regions: dict[str, CompiledAethrynRegion],
    graph: dict[str, Any],
) -> None:
    """Add explicit route exits between each selected graph edge's region starts."""
    for source in sorted(regions):
        for destination in sorted(worldgraph.neighbors(source, graph)):
            if source >= destination:
                continue
            source_room = regions[source].region.start
            destination_room = regions[destination].region.start
            rooms[source_room]["exits"][f"route_{destination}"] = destination_room
            rooms[destination_room]["exits"][f"route_{source}"] = source_room


def compile_aethryn_world(
    manifest: BuildManifest,
    profiles: Iterable[AethrynRegionProfile] | None = None,
    *,
    start_region: str = "veridia",
    graph: dict[str, Any] | None = None,
) -> CompiledAethrynWorld:
    """Compile and connect a selected set of Aethryn regions from one manifest."""
    if manifest.project.strip().lower() != "aethryn":
        raise WorldCompilerError("the Aethryn world compiler requires project 'Aethryn'")
    selected_profiles = tuple(profiles or load_aethryn_profiles())
    if not selected_profiles:
        raise WorldCompilerError("an Aethryn world needs at least one region profile")
    induced = _induced_graph(selected_profiles, start_region, graph)
    compiled_regions = tuple(
        compile_aethryn_region(manifest, profile) for profile in selected_profiles
    )
    by_region = {compiled.profile.region_id: compiled for compiled in compiled_regions}
    rooms: dict[str, dict[str, Any]] = {}
    npcs: dict[str, Npc] = {}
    for compiled in compiled_regions:
        for label, room in compiled.region.rooms.items():
            if label in rooms:
                raise WorldCompilerError(f"compiled room id collision: {label!r}")
            rooms[label] = {**room, "exits": dict(room.get("exits", {}))}
        for label, npc in compiled.npcs.items():
            if label in npcs:
                raise WorldCompilerError(f"compiled NPC id collision: {label!r}")
            npcs[label] = npc
    _connect_regions(rooms, by_region, induced)
    return CompiledAethrynWorld(
        manifest=manifest,
        profiles=selected_profiles,
        regions=compiled_regions,
        graph=induced,
        rooms=rooms,
        npcs=npcs,
        items=_generated_item_records(npcs),
        zones=_zone_records(compiled_regions),
        start_region=start_region,
    )


def _validate_assembled_artifact(seed_dir: Path, world: CompiledAethrynWorld) -> None:
    """Run the existing seed loaders and the induced graph gate over an installed assembly."""
    rooms = load_rooms(seed_dir / "rooms.yaml")
    items = load_items(seed_dir / "items.yaml")
    npcs = load_npcs(seed_dir / "npcs.yaml")
    load_zones(seed_dir / "zones.yaml", set(rooms))
    inspect_world_links(rooms, items, npcs)
    raw_graph = yaml.safe_load((seed_dir / "world_graph.yaml").read_text(encoding="utf-8"))
    if not isinstance(raw_graph, dict):
        raise WorldCompilerError("assembled world_graph.yaml is not a mapping")
    _validate_graph(
        raw_graph, {profile.region_id for profile in world.profiles}, world.start_region
    )
    if set(rooms) != set(world.rooms):
        raise WorldCompilerError("installed rooms differ from the compiler's assembled rooms")


def install_compiled_world(
    world: CompiledAethrynWorld,
    blueprint_root: Path,
    *,
    seed_name: str = "aethryn-compiled",
) -> HostedWorld:
    """Install one assembled Aethryn world and prove all current seed gates pass."""
    hosted = install_world(
        world.game_spec(),
        blueprint_root,
        seed_name=seed_name,
        title="Aethryn - Compiled World",
    )
    if hosted.verdict != HOSTABLE:
        return hosted
    seed_dir = Path(hosted.seed_dir)
    (seed_dir / "items.yaml").write_text(
        yaml.safe_dump(world.items, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (seed_dir / "npcs.yaml").write_text(
        yaml.safe_dump(world.npcs, sort_keys=True, allow_unicode=True), encoding="utf-8"
    )
    (seed_dir / "zones.yaml").write_text(
        yaml.safe_dump(world.zones, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (seed_dir / "world_graph.yaml").write_text(
        yaml.safe_dump(world.graph, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (seed_dir / "build_manifest.json").write_text(world.manifest.to_json() + "\n", encoding="utf-8")
    (seed_dir / "assembly_manifest.json").write_text(
        json.dumps(world.assembly_manifest(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    try:
        _validate_assembled_artifact(seed_dir, world)
    except (ManifestCompilerError, BlueprintError, TypeError, ValueError) as exc:
        return replace(
            hosted,
            verdict=UNHOSTABLE,
            problems=(f"assembled artifact failed its seed gates: {exc}",),
        )
    return replace(
        hosted,
        files=tuple(
            sorted(
                (
                    *hosted.files,
                    "assembly_manifest.json",
                    "build_manifest.json",
                    "items.yaml",
                    "npcs.yaml",
                    "world_graph.yaml",
                    "zones.yaml",
                )
            )
        ),
    )
