"""CARD: underground -- publish cave-forge output as playable Aethryn areas.

``caves.generate_cave`` deliberately returns an area record for the creator bench. This module is
the missing world seam: it takes a compact, authored underground manifest, namespaces each cave,
attaches its mouth to a real surface anchor, adds a light life layer, and publishes area metadata
for zone resets, culls, foraging, and region views.

The manifest is intentionally small. A cave's rooms, shape, regional vocabulary, history, and
provenance still come from the deterministic cave forge; the manifest author chooses where that
area belongs, what kind of underground space it is, and which local lore thread it carries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from kernel.world import canon, caves
from kernel.world.bestiary import make_beast, make_notable
from kernel.world.seed import Npc, Room, SeedError, Zone, _UniqueKeyLoader
from kernel.world.wildlands import _BIOMES, gatherable_materials

_REQUIRED = (
    "name",
    "region",
    "kind",
    "attach",
    "attach_exit",
    "biome",
    "level_min",
    "level_max",
    "seed",
    "size",
    "lore_anchor",
)
_KINDS = frozenset({"cave", "underzone"})


@dataclass(frozen=True)
class UndergroundZone:
    """The merged live content for all configured underground areas."""

    rooms: dict[str, Room]
    npcs: dict[str, Npc]
    zones: dict[str, Zone]


def load_underground_configs(path: Path) -> list[dict[str, Any]] | None:
    """Load and validate the authored underground expansion manifest."""
    if not path.is_file():
        return None
    raw = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(raw, dict) or not raw:
        raise SeedError(f"{path}: underground manifest must be a non-empty mapping")
    region_ids = {r["id"] for r in canon.regions()}
    configs: list[dict[str, Any]] = []
    for area_id, row in raw.items():
        if not isinstance(row, dict):
            raise SeedError(f"underground area {area_id!r} must be a mapping")
        merged = {**row, "id": str(area_id)}
        missing = [key for key in _REQUIRED if key not in merged]
        if missing:
            raise SeedError(f"underground area {area_id!r} missing key(s): {', '.join(missing)}")
        if merged["region"] not in region_ids:
            raise SeedError(
                f"underground area {area_id!r}: region {merged['region']!r} is not canon"
            )
        if merged["kind"] not in _KINDS:
            raise SeedError(f"underground area {area_id!r}: kind must be one of {sorted(_KINDS)}")
        if merged["biome"] not in _BIOMES:
            raise SeedError(f"underground area {area_id!r}: unknown life biome {merged['biome']!r}")
        if not isinstance(merged["attach_exit"], str) or not merged["attach_exit"]:
            raise SeedError(f"underground area {area_id!r}: attach_exit must be non-empty")
        for key in ("level_min", "level_max", "seed", "size"):
            value = merged[key]
            if not isinstance(value, int) or isinstance(value, bool):
                raise SeedError(f"underground area {area_id!r}: {key} must be an integer")
        if not 1 <= merged["level_min"] <= merged["level_max"] <= 300:
            raise SeedError(f"underground area {area_id!r}: invalid level band")
        if not 5 <= merged["size"] <= 18:
            raise SeedError(f"underground area {area_id!r}: size must be in the 5-18 cave band")
        configs.append(merged)
    return configs


def _prefix(area_id: str, room_id: str) -> str:
    return f"{area_id}_{room_id}"


def _room_records(cfg: dict[str, Any], area: dict[str, Any]) -> dict[str, Room]:
    """Convert a cave-forge record into live Room records under a stable namespace."""
    ids = {room["id"] for room in area["rooms"]}
    rooms: dict[str, Room] = {}
    for raw in area["rooms"]:
        room_id = _prefix(cfg["id"], raw["id"])
        exits = {
            direction: _prefix(cfg["id"], destination)
            for direction, destination in raw["exits"].items()
            if destination in ids
        }
        desc = str(raw["description"])
        if cfg["kind"] == "underzone":
            desc = f"{cfg['lore_anchor']} {desc}"
        room = Room(name=f"{area['display_name']}: {raw['display_name']}", desc=desc, exits=exits)
        rooms[room_id] = room
    return rooms


def _life(cfg: dict[str, Any], area: dict[str, Any], rooms: dict[str, Room]) -> dict[str, Npc]:
    """Place deterministic cave life without flooding the global bounty board."""
    ordered = [room for room in area["rooms"] if room["role"] != "entrance"]
    materials = gatherable_materials(cfg["biome"])
    npcs: dict[str, Npc] = {}
    for idx, raw in enumerate(ordered):
        live_id = _prefix(cfg["id"], raw["id"])
        if idx % 4 == 0:
            rooms[live_id]["node"] = materials[(idx // 4) % len(materials)]
        if idx % 3 == 0:
            label = f"{cfg['id']}_beast_{idx}"
            level = cfg["level_min"] + (cfg["level_max"] - cfg["level_min"]) * idx // max(
                1, len(ordered) - 1
            )
            npcs[label] = make_beast(cfg["biome"], level, idx, live_id)
    # Each underzone earns one named guardian, while ordinary caves stay light enough to read as
    # exploration content rather than another dungeon mouth.
    if cfg["kind"] == "underzone" and ordered:
        raw = ordered[-1]
        live_id = _prefix(cfg["id"], raw["id"])
        guardian = make_notable(cfg["biome"], cfg["level_max"], len(ordered), live_id, 0)
        guardian["tier"] = "elite"
        guardian["aggressive"] = False
        npcs[f"{cfg['id']}_guardian"] = guardian
    return npcs


def build_underground(configs: list[dict[str, Any]], existing_rooms: set[str]) -> UndergroundZone:
    """Build, attach, and publish all configured caves and underzones."""
    rooms: dict[str, Room] = {}
    npcs: dict[str, Npc] = {}
    zones: dict[str, Zone] = {}
    claimed = set(existing_rooms)
    for cfg in configs:
        if cfg["attach"] not in claimed:
            raise SeedError(
                f"underground area {cfg['id']!r} attaches to missing room {cfg['attach']!r}"
            )
        area = caves.generate_cave(cfg["region"], cfg["seed"], size=cfg["size"])
        generated = _room_records(cfg, area)
        clash = set(generated) & claimed
        if clash:
            raise SeedError(f"underground area {cfg['id']!r} collides on {sorted(clash)[:3]}")
        root = _prefix(cfg["id"], area["return_room"])
        if cfg["attach_exit"] in ("north", "south", "east", "west", "up", "down"):
            raise SeedError(
                f"underground area {cfg['id']!r}: use a named attach_exit, not a compass direction"
            )
        # The surface anchor is mutated by world.py after every generated area has passed its local
        # checks and has been merged into the global room map.
        generated[root]["exits"]["out"] = cfg["attach"]
        rooms.update(generated)
        cave_npcs = _life(cfg, area, generated)
        npcs.update(cave_npcs)
        zone = Zone(
            name=cfg["name"],
            rooms=list(generated),
            reset_mode="empty_only",
            beats_between=16,
            region=next(r["name"] for r in canon.regions() if r["id"] == cfg["region"]),
            level_min=cfg["level_min"],
            level_max=cfg["level_max"],
            biome=cfg["biome"],
        )
        zone["template"] = cfg["kind"]
        zone["canon_status"] = area["canon_status"]
        zone["provenance"] = area["provenance"]
        zones[f"underground_{cfg['id']}"] = zone
        claimed.update(generated)
    # The returned object cannot mutate the caller's surface rooms, so the world assembly wires the
    # named threshold immediately after merging. Keep the attachment map on the zone for that step.
    for cfg in configs:
        zone = zones[f"underground_{cfg['id']}"]
        root = zone["rooms"][0]
        zone["attach"] = cfg["attach"]
        zone["attach_exit"] = cfg["attach_exit"]
        zone["entrance"] = root
    return UndergroundZone(rooms, npcs, zones)
