"""CARD: delve -- expand the map's dungeon mouths into multi-room delves with a boss ladder.

The map marks 16 dungeons, but each shipped as a single room with one guardian at the mouth -- a
door, not a dungeon. This is the world-generation lever (rooms via wildlands, creatures via
bestiary, gear via armory) pointed at DUNGEONS: it reads a compact manifest (dungeons.yaml, one row
per mouth: name, zone, level, biome) and sinks a DESCENT below each mouth -- a chain of chambers,
each with a foe that grows deadlier as you descend, ending in a deep BOSS out-levelling the mouth's
own guardian and drops real gear. So a dungeon becomes a delve: a boss ladder from the door to the
depths, with a payoff at the bottom.

The descent's trash foes are ambient (a fight, no bounty flood); the deep boss is a named notable
(a hunt bounty + armory gear, wired in world assembly). Pure and deterministic like the other
generators -- the same dungeon always sinks the same delve -- merged through the same loader gates
as authored rooms. `generate_delves` returns rooms/npcs; `wire_delve_mouths` opens each mouth
`down` into its descent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from parts.world.bestiary import make_beast, make_notable
from parts.world.seed import Npc, Room, SeedError

_DEPTH = 4  # chambers in a delve's descent below the mouth
_BOSS_BUMP = 5  # the deep boss out-levels the dungeon's mouth guardian by this many levels

_CHAMBER_DESC = (
    "The way sinks into {name}. {mood} Rough walls close around a chamber where something waits.",
)
_MOODS = (
    "Cold air breathes up from below.",
    "The dark thickens; your lamp gutters.",
    "Old bones crunch underfoot.",
    "A wet dripping echoes from deeper still.",
    "The stone itself seems to hold its breath.",
)


def load_dungeons(path: Path) -> list[dict[str, Any]] | None:
    """Read a seed's optional dungeons.yaml (room-id -> {name, zone, level, biome}). Returns None
    when the seed ships none. Fails loud on a malformed row (missing field, bad level)."""
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise SeedError("dungeons.yaml must be a mapping of room-id to dungeon config.")
    configs: list[dict[str, Any]] = []
    for room, cfg in raw.items():
        if not isinstance(cfg, dict):
            raise SeedError(f"dungeon {room!r} must be a mapping of config keys.")
        merged = {**cfg, "room": room}
        for key in ("name", "zone", "level", "biome"):
            if key not in merged:
                raise SeedError(f"dungeon {room!r} is missing required key {key!r}.")
        level = merged["level"]
        if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 300:
            raise SeedError(f"dungeon {room!r}: 'level' must be an int 1..300, got {level!r}.")
        configs.append(merged)
    return configs


def _chamber(name: str, idx: int) -> Room:
    """One chamber of a delve: themed by the dungeon and how deep the chamber sits."""
    mood = _MOODS[idx % len(_MOODS)]
    desc = _CHAMBER_DESC[0].format(name=name, mood=mood)
    return Room(name=f"{name}, depth {idx}", desc=desc, exits={})


def generate_delves(
    configs: list[dict[str, Any]],
) -> tuple[dict[str, Room], dict[str, Npc]]:
    """Sink a descent below every dungeon mouth: `_DEPTH` chambers, each with a foe that deepens in
    level, ending in a named deep boss (non-ambient -> a bounty; armed with gear in world assembly).
    Returns (rooms, npcs) to merge; `wire_delve_mouths` opens each mouth into its first chamber."""
    rooms: dict[str, Room] = {}
    npcs: dict[str, Npc] = {}
    for cfg in configs:
        mouth, name = cfg["room"], str(cfg["name"])
        biome, base = str(cfg["biome"]), int(cfg["level"])
        prev = mouth
        for i in range(1, _DEPTH + 1):
            label = f"{mouth}_delve_{i}"
            room = _chamber(name, i)
            room["exits"]["up"] = prev  # back toward the mouth
            if i < _DEPTH:
                room["exits"]["down"] = f"{mouth}_delve_{i + 1}"
                # a trash foe, deadlier the deeper you go (ambient: a fight, but no bounty)
                npcs[f"{label}_foe"] = make_beast(biome, base + i, i, label)
            else:
                # the deep boss: a named notable, boss-tier and lethal, out-levelling the mouth
                boss = make_notable(biome, base + _BOSS_BUMP, i, label, 5)
                boss["tier"] = "boss"
                boss["lethal"] = True
                boss["aggressive"] = False  # a hunt at the bottom, not an ambush at the door
                npcs[f"{mouth}_deep_boss"] = boss
            rooms[label] = room
            prev = label
    return rooms, npcs


def wire_delve_mouths(world: dict[str, Room], configs: list[dict[str, Any]]) -> None:
    """Open each dungeon mouth `down` into its descent's first chamber, in place. The mouth room is
    the authored place room; its guardian stays at the door, the delve sinks below."""
    for cfg in configs:
        mouth = cfg["room"]
        if mouth in world:  # a seed may omit a dungeon's mouth room; skip rather than fail the boot
            world[mouth]["exits"].setdefault("down", f"{mouth}_delve_1")
