"""Manifest-driven Aethryn region compiler.

This is the first connected Seed Compiler slice: a deployment ``BuildManifest`` becomes a
deterministic Aethryn region, the region is populated by the real world generator, and the result
can be installed as a validated World Package.  The compiler deliberately emits one region per
invocation.  A full MMO build still needs the later domain compilers (quests, economy, crafting,
and multi-region assembly); this module makes that boundary explicit instead of claiming that
manifest sizing alone is a complete game compiler.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from kernel.domains.game_linker import GameSpec, RoomSpec
from kernel.domains.hosted_world import HOSTABLE, UNHOSTABLE, HostedWorld, install_world
from kernel.seed_package import BuildManifest
from kernel.world.seed import BlueprintError, Npc, load_npcs, load_rooms, load_zones
from kernel.world.worldgen import (
    Landmark,
    LifeSpec,
    Region,
    RegionSpec,
    generate_region,
    populate_region,
)


class ManifestCompilerError(ValueError):
    """A manifest or Aethryn compiler profile cannot produce a valid region."""


@dataclass(frozen=True)
class AethrynRegionProfile:
    """The authored domain choices that shape one generated Aethryn region.

    Geometry is scaled from the manifest's per-region room budget.  Landmark positions are
    normalized fractions so the same profile remains valid at different deployment tiers.
    """

    region_id: str = "veridia"
    display_name: str = "The Veridia Wilds"
    biome: str = "temperate-meadow"
    level_min: int = 1
    level_max: int = 30
    seed: int = 9
    base_width: int = 28
    base_height: int = 22
    river_at: tuple[float, float] = (0.5, 0.9)
    landmarks: tuple[tuple[float, float, str, str], ...] = (
        (0.15, 0.18, "The Cradle Cairn", "site"),
        (0.48, 0.48, "Meadowmoot", "site"),
        (0.82, 0.78, "The Old Watchtower", "dungeon"),
    )

    def validate(self) -> None:
        if not self.region_id.strip() or not self.display_name.strip():
            raise ManifestCompilerError("an Aethryn region needs an id and display name")  # noqa: TRY003
        if not self.biome.strip():
            raise ManifestCompilerError("an Aethryn region needs a biome")  # noqa: TRY003
        if not 1 <= self.level_min <= self.level_max <= 300:  # noqa: PLR2004
            raise ManifestCompilerError("an Aethryn region level band must be within 1-300")  # noqa: TRY003
        if self.base_width < 8 or self.base_height < 8:  # noqa: PLR2004
            raise ManifestCompilerError(  # noqa: TRY003
                "an Aethryn region profile needs a base size of at least 8x8"
            )
        for x, y, name, kind in self.landmarks:
            if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
                raise ManifestCompilerError(f"landmark {name!r} must use normalized coordinates")  # noqa: TRY003
            if not name.strip() or not kind.strip():
                raise ManifestCompilerError("Aethryn landmarks need names and kinds")  # noqa: TRY003


VERIDIA_PROFILE = AethrynRegionProfile()


@dataclass(frozen=True)
class CompiledAethrynRegion:
    """The compiler result before installation as a World Package."""

    manifest: BuildManifest
    profile: AethrynRegionProfile
    region: Region
    npcs: dict[str, Npc]
    target_rooms: int
    target_monsters: int
    width: int
    height: int

    @property
    def actual_rooms(self) -> int:
        return len(self.region.rooms)

    @property
    def actual_monsters(self) -> int:
        return len(self.npcs)

    def game_spec(self) -> GameSpec:
        """Project the generated rooms into the existing region linker contract."""
        rooms = tuple(
            RoomSpec(
                label=label,
                name=str(room.get("name", "")),
                desc=str(room.get("desc", "")),
                exits=dict(room.get("exits", {})),
            )
            for label, room in self.region.rooms.items()
        )
        return GameSpec(
            region=f"Aethryn {self.profile.display_name}",
            rooms=rooms,
            start=self.region.start,
        )


def _region_budget(manifest: BuildManifest) -> int:
    """Return the manifest's derived room budget for one region."""
    regions = max(manifest.sizing.regions, 1)
    return max(1, math.ceil(manifest.sizing.rooms / regions))


def _dimensions(room_budget: int, profile: AethrynRegionProfile) -> tuple[int, int]:
    """Choose a stable, roughly profile-shaped rectangle large enough for the budget."""
    aspect = profile.base_width / profile.base_height
    minimum = profile.base_width * profile.base_height
    requested = max(room_budget, minimum)
    height = max(profile.base_height, math.ceil(math.sqrt(requested / aspect)))
    width = max(profile.base_width, math.ceil(requested / height))
    return width, height


def _room_coordinates(region: Region) -> dict[tuple[int, int], str]:
    """Index generated field room ids by their deterministic x/y suffix."""
    coordinates: dict[tuple[int, int], str] = {}
    for label in region.rooms:
        try:
            _, x, y = label.rsplit("_", 2)
            coordinates[(int(x), int(y))] = label
        except (ValueError, IndexError):
            continue
    return coordinates


def _nearest_anchor(
    coordinates: dict[tuple[int, int], str], x: int, y: int, taken: set[str]
) -> tuple[int, int]:
    """Resolve a normalized anchor to the nearest generated passable cell."""
    choices = sorted(
        (
            (abs(cx - x) + abs(cy - y), cx, cy, label)
            for (cx, cy), label in coordinates.items()
            if label not in taken
        )
    )
    if not choices:
        raise ManifestCompilerError("Aethryn compiler could not place a unique landmark")  # noqa: TRY003
    _, cx, cy, _ = choices[0]
    return cx, cy


def _life_for(
    manifest: BuildManifest, profile: AethrynRegionProfile, room_count: int, landmark_count: int
) -> LifeSpec:
    """Translate manifest density targets into the current field life controls.

    The current field generator supports at most one ambient creature per wild cell, so the
    compiler caps density at that physical capacity and leaves the target visible in the result.
    That is an explicit follow-up for the higher-density MMORPG population compiler.
    """
    regions = max(manifest.sizing.regions, 1)
    target_monsters = max(1, math.ceil(manifest.sizing.monsters / regions))
    wild_cells = max(1, room_count - landmark_count)
    foe_every = max(1, math.ceil(wild_cells / target_monsters))
    target_recipes = max(1, math.ceil(manifest.sizing.crafting_recipes / regions))
    gather_every = max(1, math.ceil(wild_cells / target_recipes))
    target_bosses = max(1, math.ceil(manifest.sizing.bosses / regions))
    notable_every = max(1, math.ceil(wild_cells / target_bosses))
    return LifeSpec(
        biome=profile.biome,
        level_min=profile.level_min,
        level_max=profile.level_max,
        foe_every=foe_every,
        gather_every=gather_every,
        notable_every=notable_every,
        notable_cap=min(16, target_bosses),
    )


def compile_aethryn_region(
    manifest: BuildManifest, profile: AethrynRegionProfile = VERIDIA_PROFILE
) -> CompiledAethrynRegion:
    """Compile one deterministic, living Aethryn region from a deployment manifest."""
    if manifest.project.strip().lower() != "aethryn":
        raise ManifestCompilerError(  # noqa: TRY003
            f"the Aethryn compiler requires project 'Aethryn', got {manifest.project!r}"
        )
    profile.validate()
    target_rooms = _region_budget(manifest)
    width, height = _dimensions(target_rooms, profile)
    river_source = (
        min(width - 1, max(0, round(profile.river_at[0] * (width - 1)))),
        min(height - 1, max(0, round(profile.river_at[1] * (height - 1)))),
    )

    # First generate the terrain without anchors. This lets the compiler place authored landmarks
    # on the nearest actual passable cells instead of guessing whether noise made a cell a wall.
    base = RegionSpec(
        name=profile.region_id,
        width=width,
        height=height,
        seed=profile.seed,
        river_source=river_source,
    )
    preview = generate_region(base)
    if not preview.world_shaped:
        raise ManifestCompilerError(  # noqa: TRY003
            f"generated region {profile.region_id!r} failed the topology gate: "
            f"{preview.topology.verdict}"
        )

    coordinates = _room_coordinates(preview)
    anchors: list[Landmark] = []
    taken: set[str] = set()
    for fx, fy, name, kind in profile.landmarks:
        x, y = _nearest_anchor(
            coordinates, round(fx * (width - 1)), round(fy * (height - 1)), taken
        )
        label = f"{profile.region_id}_{x}_{y}"
        taken.add(label)
        anchors.append(Landmark((x, y), name, kind))

    region = generate_region(replace(base, landmarks=tuple(anchors)))
    if not region.ok:
        raise ManifestCompilerError(  # noqa: TRY003
            f"generated region {profile.region_id!r} failed validation: "
            f"topology={region.topology.verdict}, landmarks_reachable={region.landmarks_reachable}"
        )
    life = _life_for(manifest, profile, len(region.rooms), len(anchors))
    npcs = populate_region(region, life)
    return CompiledAethrynRegion(
        manifest=manifest,
        profile=profile,
        region=region,
        npcs=npcs,
        target_rooms=target_rooms,
        target_monsters=max(
            1, math.ceil(manifest.sizing.monsters / max(manifest.sizing.regions, 1))
        ),
        width=width,
        height=height,
    )


def _zone_record(compiled: CompiledAethrynRegion) -> dict[str, Any]:
    """Build the loader-shaped zone record for the emitted region."""
    return {
        "name": compiled.profile.display_name,
        "rooms": list(compiled.region.rooms),
        "reset_mode": "empty_only",
        "beats_between": 12,
        "region": compiled.profile.display_name.removesuffix(" Wilds"),
        "level_min": compiled.profile.level_min,
        "level_max": compiled.profile.level_max,
        "biome": compiled.profile.biome,
    }


def _validate_artifact(seed_dir: Path, zone_id: str) -> None:
    """Run the seed loaders against every file this compiler adds beyond the linker output."""
    rooms = load_rooms(seed_dir / "rooms.yaml")
    load_npcs(seed_dir / "npcs.yaml")
    load_zones(seed_dir / "zones.yaml", set(rooms))
    if not rooms or zone_id not in yaml.safe_load(
        (seed_dir / "zones.yaml").read_text(encoding="utf-8")
    ):
        raise ManifestCompilerError("compiled artifact did not emit its complete zone record")  # noqa: TRY003


def install_compiled_region(
    compiled: CompiledAethrynRegion,
    blueprint_root: Path,
    *,
    seed_name: str = "aethryn-veridia",
) -> HostedWorld:
    """Install and validate a compiled region as a World Package.

    ``install_world`` owns the room/linker/identity gates. This function adds the compiler-owned
    NPCs, zone metadata, and manifest artifact, then runs their loaders before returning HOSTABLE.
    """
    hosted = install_world(
        compiled.game_spec(),
        blueprint_root,
        seed_name=seed_name,
        title=f"Aethryn - {compiled.profile.display_name}",
    )
    if hosted.verdict != HOSTABLE:
        return hosted
    seed_dir = Path(hosted.seed_dir)
    zone_id = f"compiled_{compiled.profile.region_id}"
    (seed_dir / "npcs.yaml").write_text(
        yaml.safe_dump(compiled.npcs, sort_keys=True, allow_unicode=True), encoding="utf-8"
    )
    (seed_dir / "zones.yaml").write_text(
        yaml.safe_dump({zone_id: _zone_record(compiled)}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    (seed_dir / "build_manifest.json").write_text(
        compiled.manifest.to_json() + "\n", encoding="utf-8"
    )
    try:
        _validate_artifact(seed_dir, zone_id)
    except (ManifestCompilerError, BlueprintError, TypeError, ValueError) as exc:
        return replace(
            hosted,
            verdict=UNHOSTABLE,
            problems=(f"compiled artifact failed its seed gates: {exc}",),
        )
    return replace(
        hosted,
        files=tuple(sorted((*hosted.files, "build_manifest.json", "npcs.yaml", "zones.yaml"))),
    )
