"""CARD: fieldzone -- assemble a FIELD-backed wilderness zone from a compact seed config.

The field twin of `kernel.world.wildlands` for the trails: it bridges a `fields.yaml` row to the
two-layer worldgen generator + its life layer, and hands back everything `world.py` needs to graft
an OPEN FIELD onto its zone hub in place of a linear trail-chain:

  * the generated rooms (a WORLD-shaped graph -- open movement, rivers, elevation, roads), refused
    loud if the region is not world-shaped or a landmark is unreachable;
  * the living content (ambient foes, gather nodes, guardians), from worldgen.populate_region
    so the zone's cull/forage boards keep routing exactly as they did for the trail;
  * the GATE cell the zone hub grafts onto (an edge cell with a free reciprocal exit slot) and the
    zone AREA metadata (its rooms as members) so `zone_of` resolves every field cell.

A field config is validated on load and FAILS LOUD on a malformed row, the same discipline the
wildlands loader keeps. Deterministic: the same seed yields the same field, life and all. Status:
PROTOTYPED (Veridia pilot, branch aethryn/pilot-veridia-field).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from kernel.world.seed import Npc, Room, Zone
from kernel.world.worldgen import (
    Landmark,
    LifeSpec,
    RegionSpec,
    WorldgenError,
    generate_region,
    populate_region,
)

# The reciprocal of an attach direction, so the field's back exit home is the mirror of the hub's
# entry (mirrors kernel.world.wildlands._OPPOSITE; direction reciprocity, not domain logic).
_REVERSE = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "northeast": "southwest",
    "southwest": "northeast",
    "northwest": "southeast",
    "southeast": "northwest",
    "up": "down",  # a hub can climb UP into its wilderness; the field's door leads back down
    "down": "up",
}

# Every required key on a field row, with the loud message if it is missing or the wrong shape.
_REQUIRED = (
    "name",
    "region",
    "biome",
    "attach",
    "attach_dir",
    "level_min",
    "level_max",
    "width",
    "height",
)


class FieldZoneError(ValueError):
    """A field zone that cannot be assembled (a malformed config or a region that is not a real,
    reachable, world-shaped field). Fails loud -- a broken zone never ships silently."""


@dataclass(frozen=True)
class FieldZone:
    """A generated field wilderness, ready for `world.py` to graft onto its zone hub."""

    label: str  # the AREA label (field_<id>), so cull/forage scope keys match zone_of
    rooms: dict[str, Room]
    npcs: dict[str, Npc]
    gate: str  # the field cell the hub grafts onto (its `attach_dir` exit leads here)
    attach: str  # the hub room the field hangs off
    attach_dir: str  # the direction from the hub into the field
    zone: Zone  # the area metadata, its members every field room


def load_field_configs(path: Path) -> list[dict[str, Any]] | None:
    """Load + validate every field-zone row from a fields.yaml, injecting each row's `id` from its
    key. A missing file is None (the seed simply grows no fields); a malformed row FAILS LOUD."""
    if not path.is_file():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise FieldZoneError(f"{path}: a fields config must be a non-empty mapping of id -> row")  # noqa: TRY003
    configs: list[dict[str, Any]] = []
    for zone_id, row in raw.items():
        if not isinstance(row, dict):
            raise FieldZoneError(f"{path}: field {zone_id!r} must be a mapping")  # noqa: TRY003
        for key in _REQUIRED:
            if key not in row:
                raise FieldZoneError(f"{path}: field {zone_id!r} is missing required key {key!r}")  # noqa: TRY003
        if row["attach_dir"] not in _REVERSE:
            raise FieldZoneError(  # noqa: TRY003
                f"{path}: field {zone_id!r} attach_dir {row['attach_dir']!r} is not a compass dir"
            )
        configs.append({**row, "id": str(zone_id)})
    return configs


def _gate_cell(rooms: dict[str, Room], back: str) -> str:
    """The field cell the zone hub grafts onto: an EDGE cell whose `back` slot is free. An interior
    cell already spends all 8 exits on neighbours, so only an edge cell (no neighbour off the map on
    the `back` side) can hold the reciprocal exit home. Deterministic: the lowest such room id."""
    for rid in sorted(rooms):
        if back not in rooms[rid]["exits"]:
            return rid
    raise FieldZoneError(f"no edge cell free to graft a {back!r} exit home")  # pragma: no cover  # noqa: E501, TRY003


def build_field_zone(cfg: dict[str, Any], taken: set[str]) -> FieldZone:
    """Generate a field from one config row, breathe life into it, and wire the reciprocal exit
    back to its hub. Refuses loud if the region is not world-shaped + fully reachable, or if its
    room ids collide with the already-built world."""
    landmarks = tuple(
        Landmark(tuple(lm["at"]), lm["name"], lm.get("kind", "site"))
        for lm in cfg.get("landmarks", ())
    )
    river = tuple(cfg["river_source"]) if cfg.get("river_source") else None
    spec = RegionSpec(
        name=cfg["id"],
        width=int(cfg["width"]),
        height=int(cfg["height"]),
        seed=int(cfg.get("seed", 0)),
        biome=cfg["biome"],  # the terrain profile: sand, ice, jungle, moor, ash, shore
        landmarks=landmarks,
        river_source=river,
    )
    try:
        region = generate_region(spec)
    except WorldgenError as exc:
        raise FieldZoneError(f"field zone {cfg['id']!r}: {exc}") from exc  # noqa: TRY003
    if not region.ok:
        raise FieldZoneError(  # noqa: TRY003
            f"field zone {cfg['id']!r} is not a world-shaped, reachable field: "
            f"{region.topology.verdict}, landmarks_reachable={region.landmarks_reachable}"
        )
    clash = set(region.rooms) & taken
    if clash:
        raise FieldZoneError(  # noqa: TRY003
            f"field zone {cfg['id']!r} room ids collide with the world: {sorted(clash)[:3]}"
        )

    rooms = cast(
        "dict[str, Room]", region.rooms
    )  # worldgen types rooms loosely; they are Room dicts
    back = _REVERSE[cfg["attach_dir"]]
    gate = _gate_cell(rooms, back)
    # Life deepens from the GATE (the field's door), so a newcomer meets the gentlest level-1 wild
    # where they enter -- the trail's on-ramp, preserved for the open field.
    npcs = populate_region(
        region, LifeSpec(cfg["biome"], int(cfg["level_min"]), int(cfg["level_max"])), origin=gate
    )
    rooms[gate]["exits"][back] = cfg["attach"]  # the field's door back to its hub
    zone = Zone(
        name=cfg["name"],
        rooms=list(rooms),
        reset_mode="empty_only",
        beats_between=12,
        region=cfg["region"],
        level_min=int(cfg["level_min"]),
        level_max=int(cfg["level_max"]),
        biome=cfg["biome"],
    )
    return FieldZone(
        f"field_{cfg['id']}", rooms, npcs, gate, cfg["attach"], cfg["attach_dir"], zone
    )
