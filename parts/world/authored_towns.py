"""CARD: authored_towns -- the content pipeline for hand-authored settlement interiors.

The map places each settlement as a single hub room; a hand-authored town gives that hub an interior
(subareas, residents, an item or two) and, with a quest file, a local story. Greenhold proved the
pattern; this generalises it so a NEW town is PURE DATA: drop a file in seeds/aethryn/authored/ and
it installs itself. No new module per town, so authored content scales without code.

Each town file (seeds/aethryn/authored/<town>.yaml) declares its `rooms`, the `hub` it hangs off,
its `npcs`, and its `items`. This module builds them as Room/Npc/Item records directly (so a
boundary exit `out: <hub>` does not trip load_rooms' per-file exit-closure gate) and, for every town
whose hub is present in the world, merges the interior and wires the hub's exit. It is a no-op for a
town whose hub is absent, so a non-aethryn seed installs nothing. Content is data; this is the
factory. Merged before the world's link audit, so every authored room/NPC/item passes the same gate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from parts.world.seed import SEED_DIR, Item, Npc, Room, SeedError, _UniqueKeyLoader

# Each *.yaml here is one authored town, keyed off a hub room the map already places.
AUTHORED_DIR = SEED_DIR / "authored"


def town_files(directory: Path | None = None) -> list[Path]:
    """Every authored-town file, in name order (a stable install order across seeds)."""
    where = directory if directory is not None else AUTHORED_DIR
    return sorted(where.glob("*.yaml")) if where.is_dir() else []


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SeedError(f"Authored town file not found: {path}")
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(data, dict):
        raise SeedError(f"Authored town file is not a mapping: {path}")
    for section in ("rooms", "hub", "npcs", "items"):
        if not data.get(section):
            raise SeedError(f"authored town {path.stem!r}: missing or empty section {section!r}")
    return data


def raise_town(path: Path) -> tuple[dict[str, Room], dict[str, Npc], dict[str, Item]]:
    """Build one authored town's interior: (rooms, npcs, items) to merge. Fails loud on a malformed
    record. Every interior exit, NPC location, and item location must reference an interior room or
    the town's hub, so a typo cannot strand a room or a resident."""
    data = _load(path)
    town = path.stem
    hub = data["hub"]["room"]
    rooms = _build_rooms(town, data["rooms"])
    interior = set(rooms) | {hub}
    for label, room in rooms.items():
        for direction, dest in room["exits"].items():
            if dest not in interior:
                raise SeedError(
                    f"authored town {town!r} room '{label}' exit '{direction}' -> '{dest}': "
                    "not a room of this town"
                )
    npcs = _build_npcs(town, data["npcs"], rooms)
    items = _build_items(town, data["items"], rooms)
    return rooms, npcs, items


# Optional Room fields an authored town may carry beyond name/desc/exits: a GATHER node (a material
# prototype harvested here) and a `dynamic` live-capability the room surfaces on look.
_ROOM_OPTS = ("node", "dynamic")


def _build_rooms(town: str, records: dict[str, Any]) -> dict[str, Room]:
    rooms: dict[str, Room] = {}
    for label, rec in records.items():
        if not rec.get("name") or not rec.get("desc") or not isinstance(rec.get("exits"), dict):
            raise SeedError(f"authored town {town!r} room '{label}': needs a name, desc, and exits")
        room = Room(name=rec["name"], desc=rec["desc"], exits=dict(rec["exits"]))
        for opt in _ROOM_OPTS:
            if opt in rec:
                room[opt] = rec[opt]  # type: ignore[literal-required]
        rooms[label] = room
    return rooms


# Optional Npc fields an authored town may carry beyond the core set: combat flavour (element, its
# own resistances, an affliction, a telegraphed special, lethal/raid gating), loot (drops/loot), a
# vendor's `shop`, and ambient roaming (wander). Boot's link audit cross-checks drops/shop/loot.
_NPC_OPTS = (
    "aggressive",
    "level",
    "tier",
    "topics",
    "wander",
    "attack_element",
    "resistances",
    "inflicts",
    "special",
    "lethal",
    "raid",
    "drops",
    "loot",
    "shop",
    "ambient",
)


def _build_npcs(town: str, records: dict[str, Any], rooms: dict[str, Room]) -> dict[str, Npc]:
    npcs: dict[str, Npc] = {}
    for label, rec in records.items():
        location = rec.get("location")
        if location not in rooms:
            raise SeedError(
                f"authored town {town!r} npc '{label}': location '{location}' is not a town room"
            )
        if not rec.get("name") or not rec.get("keywords"):
            raise SeedError(f"authored town {town!r} npc '{label}': needs a name and keywords")
        hp = int(rec.get("hp", 0))
        atk = int(rec.get("atk", 0))
        if rec.get("aggressive") and (hp <= 0 or atk <= 0):
            raise SeedError(
                f"authored town {town!r} npc '{label}': an aggressive foe needs hp > 0 and atk > 0"
            )
        npc: Npc = Npc(
            name=rec["name"],
            keywords=list(rec["keywords"]),
            location=location,
            dialogue=list(rec.get("dialogue", [])),
            next_line=0,
            hp=hp,
            hp_now=hp,
            xp=int(rec.get("xp", 0)),
            atk=atk,
        )
        for opt in _NPC_OPTS:
            if opt in rec:
                npc[opt] = rec[opt]  # type: ignore[literal-required]
        npcs[label] = npc
    return npcs


def _build_items(town: str, records: dict[str, Any], rooms: dict[str, Room]) -> dict[str, Item]:
    items: dict[str, Item] = {}
    for label, rec in records.items():
        location = rec.get("location")
        if location not in rooms:
            raise SeedError(
                f"authored town {town!r} item '{label}': location '{location}' is not a town room"
            )
        if not rec.get("name") or not rec.get("keywords"):
            raise SeedError(f"authored town {town!r} item '{label}': needs a name and keywords")
        item: Item = Item(
            name=rec["name"],
            keywords=list(rec["keywords"]),
            location=f"room:{location}",  # the engine's tagged-location form
            slot=rec.get("slot", ""),
            mods=dict(rec.get("mods", {})),
        )
        if "lore" in rec:
            item["lore"] = rec["lore"]
        items[label] = item
    return items


def wire_town(world: dict[str, Room], path: Path) -> None:
    """Open a town hub's exit into its interior, in place. A no-op if the hub is absent, so this is
    safe to call for a town whose hub this world does not have."""
    hub = _load(path)["hub"]
    if hub["room"] in world:
        world[hub["room"]]["exits"].setdefault(hub["keyword"], hub["entry"])


def install_authored_towns(
    world: dict[str, Room], npcs: dict[str, Npc], directory: Path | None = None
) -> dict[str, Item]:
    """Install every authored town whose hub is present in the world: merge its interior + residents
    and wire its hub exit, returning the items to register. A town whose hub is absent is skipped
    (never even fully built), so a non-aethryn world installs nothing."""
    items: dict[str, Item] = {}
    for path in town_files(directory):
        hub = _load(path)["hub"]["room"]
        if hub not in world:
            continue
        rooms, town_npcs, town_items = raise_town(path)
        world.update(rooms)
        npcs.update(town_npcs)
        wire_town(world, path)
        items.update(town_items)
    return items
