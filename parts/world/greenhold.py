"""CARD: greenhold -- the hand-authored interior of Greenhold, Veridia's polished starting town.

The map places Greenhold as a single hub room. This raises its interior: a market square, a smithy,
a granary, and the granary undercroft, with a keeper to meet, an old-world key to recover, and (via
a quest file) a story that ties them together. It is the prompt's "first polished playable slice":
a named location expanded per the seed recipe (preserve the name, give it a role, add subareas, one
livelihood, one conflict, one rumour, one clue to a larger mystery, one revisitable change). The
failing cistern under the granary is Veridia's canon identity made concrete: ordinary life built
over forgotten abundance infrastructure, shown through function and never explained away.

It follows the inns generator's pattern exactly: the interior rooms are built in code (so the
boundary exit `out: greenhold` does not trip the per-file exit-closure gate load_rooms enforces) and
merged before the world's link audit, and the hub's exit into the town is wired in place. Content is
data (greenhold.yaml); this module is only its factory. `install_greenhold` is a no-op unless the
Greenhold hub is present, so it does nothing on a world that is not aethryn.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from parts.world.seed import SEED_DIR, Item, Npc, Room, SeedError, _UniqueKeyLoader

_GREENHOLD_PATH = SEED_DIR / "greenhold.yaml"
HUB = "greenhold"  # the map's Greenhold room, the anchor the interior hangs off


def _load(path: Path | None) -> dict[str, Any]:
    where = path if path is not None else _GREENHOLD_PATH
    if not where.exists():
        raise SeedError(f"Greenhold file not found: {where}")
    data = yaml.load(where.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(data, dict):
        raise SeedError(f"Greenhold file is not a mapping: {where}")
    for section in ("rooms", "hub", "npcs", "items"):
        if not data.get(section):
            raise SeedError(f"greenhold: missing or empty section {section!r}")
    return data


def raise_greenhold(
    path: Path | None = None,
) -> tuple[dict[str, Room], dict[str, Npc], dict[str, Item]]:
    """Build Greenhold's interior from the authored seed: (rooms, npcs, items) to merge into the
    world. Fails loud on a malformed record. Every interior exit, NPC location, and item location
    must reference an interior room or the hub, so a typo cannot strand a room or a resident."""
    data = _load(path)
    rooms = _build_rooms(data["rooms"])
    interior = set(rooms) | {HUB}
    for label, room in rooms.items():
        for direction, dest in room["exits"].items():
            if dest not in interior:
                raise SeedError(
                    f"greenhold room '{label}' exit '{direction}' -> '{dest}': not a Greenhold room"
                )
    npcs = _build_npcs(data["npcs"], rooms)
    items = _build_items(data["items"], rooms)
    return rooms, npcs, items


def _build_rooms(records: dict[str, Any]) -> dict[str, Room]:
    rooms: dict[str, Room] = {}
    for label, rec in records.items():
        if not rec.get("name") or not rec.get("desc") or not isinstance(rec.get("exits"), dict):
            raise SeedError(f"greenhold room '{label}': needs a name, desc, and exits")
        rooms[label] = Room(name=rec["name"], desc=rec["desc"], exits=dict(rec["exits"]))
    return rooms


def _build_npcs(records: dict[str, Any], rooms: dict[str, Room]) -> dict[str, Npc]:
    npcs: dict[str, Npc] = {}
    for label, rec in records.items():
        location = rec.get("location")
        if location not in rooms:
            raise SeedError(
                f"greenhold npc '{label}': location '{location}' is not a Greenhold room"
            )
        if not rec.get("name") or not rec.get("keywords"):
            raise SeedError(f"greenhold npc '{label}': needs a name and keywords")
        hp = int(rec.get("hp", 0))
        atk = int(rec.get("atk", 0))
        if rec.get("aggressive") and (hp <= 0 or atk <= 0):
            raise SeedError(f"greenhold npc '{label}': an aggressive foe needs hp > 0 and atk > 0")
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
        for opt in ("aggressive", "level", "tier", "topics", "wander"):
            if opt in rec:
                npc[opt] = rec[opt]
        npcs[label] = npc
    return npcs


def _build_items(records: dict[str, Any], rooms: dict[str, Room]) -> dict[str, Item]:
    items: dict[str, Item] = {}
    for label, rec in records.items():
        location = rec.get("location")
        if location not in rooms:
            raise SeedError(
                f"greenhold item '{label}': location '{location}' is not a Greenhold room"
            )
        if not rec.get("name") or not rec.get("keywords"):
            raise SeedError(f"greenhold item '{label}': needs a name and keywords")
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


def wire_greenhold(world: dict[str, Room], path: Path | None = None) -> None:
    """Open the hub's exit into the town interior, in place. A no-op if the hub is absent (a world
    that is not aethryn), so this is safe to call on every boot."""
    data = _load(path)
    hub = data["hub"]
    if hub["room"] in world:
        world[hub["room"]]["exits"].setdefault(hub["keyword"], hub["entry"])


def install_greenhold(
    world: dict[str, Room], npcs: dict[str, Npc], path: Path | None = None
) -> dict[str, Item]:
    """The one call the world assembly makes: if the Greenhold hub is present (an aethryn world),
    merge the interior rooms and residents and wire the hub exit, and return the items to register.
    On any other world the hub is absent and this does nothing (never even reading the file),
    returning no items."""
    if HUB not in world:
        return {}
    rooms, gh_npcs, items = raise_greenhold(path)
    world.update(rooms)
    npcs.update(gh_npcs)
    wire_greenhold(world, path)
    return items
