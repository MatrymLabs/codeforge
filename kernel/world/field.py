"""CARD: field -- a coordinate-backed FIELD backing: turn a terrain map into a WORLD-shaped graph of
rooms. The spatial-fill half of the World Topology Doctrine (Phase 2).

A field is a dict of (x, y) -> Cell(terrain, elevation). `build_field` derives a walkable room graph
from terrain ADJACENCY + the passability matrix (content/world/topology.yaml): open cells connect to
their 8 neighbours (cardinal + intercardinal, no corner-cutting across a wall); an impassable cell
(river, cliff, water, wall) is a gap no room, so terrain SHAPES movement (a river blocks east-west
except where a ford or bridge cell is passable). A crossing carries a NAMED exit (ford river, cross
bridge). Vertical is real: a Stack rises above a cell (a summit reached by `up`/`climb`) or drops
below it (a cave by `down`/`enter cave`), so the world has elevation, not just a plane.

  * `build_field(name, cells, *, stacks=())` -> rooms (the engine's Room dicts, name/desc/exits),
    ready to merge into a world. The trail a player walks is one path THROUGH the field, never the
    field itself. Descriptions are terrain-driven with local features (a visible river/hill), not
    400 identical "You are in a field." rooms.

Fails loud on an empty field or an unknown terrain. Verdicts on the RESULT come from the topology
gate (kernel/topology.py). Status: PROTOTYPED (World Topology Doctrine, Phase 2).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent  # kernel/world/ -> repo root

# --- direction geometry (the full vocabulary the doctrine mandates) ------------------------------
_CARDINAL = {"north": (0, 1), "south": (0, -1), "east": (1, 0), "west": (-1, 0)}
_INTERCARDINAL = {
    "northeast": (1, 1),
    "northwest": (-1, 1),
    "southeast": (1, -1),
    "southwest": (-1, -1),
}
_STEPS = {**_CARDINAL, **_INTERCARDINAL}
_OPPOSITE = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "northeast": "southwest",
    "southwest": "northeast",
    "northwest": "southeast",
    "southeast": "northwest",
    "up": "down",
    "down": "up",
}
# a terrain crossing exposes a NAMED exit in addition to the compass one
_CROSSING_VERB = {"ford": "ford river", "bridge": "cross bridge"}


class FieldError(ValueError):
    """A field that cannot be built (empty, or an unknown terrain). Fails loud."""


@dataclass(frozen=True)
class Cell:
    """One coordinate of a field: its terrain type and elevation (a label for the description; true
    vertical movement is a Stack, not an elevation number, so up/down never collide)."""

    terrain: str
    elevation: int = 0


@dataclass(frozen=True)
class Stack:
    """A vertical feature stacked on a field cell: a summit ABOVE (direction 'up') or a cave BELOW
    ('down'), reached by the compass vertical AND a noun alias (climb / enter cave). This is how the
    world gains elevation the flat plane cannot express."""

    at: tuple[int, int]  # the field cell it rises from / drops below
    room_id: str
    name: str
    desc: str
    direction: str = "up"  # 'up' (a summit) or 'down' (a cave)
    verb: str = "climb"  # the noun alias exit (e.g. 'climb', 'enter cave')
    back_verb: str = "descend"  # the return noun alias from the stacked room


@lru_cache(maxsize=1)
def _passable_terrain() -> frozenset[str]:
    """The terrain types a player may stand on, read from the doctrine's passability matrix."""
    import yaml

    spec = _ROOT / "content" / "world" / "topology.yaml"
    data = yaml.safe_load(spec.read_text(encoding="utf-8"))
    terrain = data["terrain"]
    return frozenset(t for t, props in terrain.items() if props.get("passable"))


def _describe(cell: Cell, neighbours: dict[str, Cell]) -> str:
    """A terrain-driven room description with a local feature or two, so a field feels like space,
    not a corridor of identical rooms."""
    base = {
        "plain": "Open grass runs to every horizon under a wide sky",
        "meadow": "Wildflowers nod across an open meadow",
        "road": "A packed-earth road runs straight through the open country",
        "forest": "Close-standing trees filter the light to green",
        "hill": "The ground rises here into rolling hills",
        "desert": "Dry sand stretches in wind-carved dunes under a hard sun",
        "snow": "Wind-scoured snow crunches underfoot across a white waste",
        "ash": "Black volcanic ash drifts over cracked and steaming ground",
        "marsh": "Boggy ground sucks at your boots between reed and pool",
        "shore": "Reeds and wet sand mark the water's edge",
        "ford": "The river shallows over a stony ford, ankle-deep and crossable",
        "bridge": "A timber bridge carries the road over the running water",
    }.get(cell.terrain, f"{cell.terrain.capitalize()} stretches around you")
    features: list[str] = []
    # if this is a road/crossing, say where the road runs on -- so a player can FOLLOW the trail
    # through the open field (the mixture of trail and field a living world wants), not just wander.
    if cell.terrain in ("road", "ford", "bridge"):
        run = [d for d in ("north", "south", "east", "west") if _is_road(neighbours.get(d))]
        if run:
            features.append(f"the road runs on {' and '.join(run)}")
    for d in ("north", "east", "south", "west"):
        nb = neighbours.get(d)
        if nb and nb.terrain in ("river", "water"):
            features.append(f"water runs to the {d}")
        elif nb and nb.terrain == "hill":
            features.append(f"hills rise to the {d}")
    tail = f"; {', '.join(features[:3])}." if features else "."
    return f"{base}{tail}"


def _is_road(cell: Cell | None) -> bool:
    return cell is not None and cell.terrain in ("road", "ford", "bridge")


def build_field(  # noqa: PLR0912
    name: str,
    cells: dict[tuple[int, int], Cell],
    *,
    stacks: Iterable[Stack] = (),
) -> dict[str, dict[str, Any]]:
    """Build the walkable room graph of a field. `cells` maps (x, y) -> Cell; `stacks` add vertical
    features. Returns room_id -> {name, desc, exits}. An impassable cell yields NO room (terrain is
    a wall). Fails loud on an empty field or an unknown terrain."""
    if not cells:
        raise FieldError("a field needs at least one cell")
    passable = _passable_terrain()
    known = passable | {"river", "water", "cliff", "wall"}  # impassable terrain is still valid
    for (x, y), cell in cells.items():
        if cell.terrain not in known:
            raise FieldError(f"cell ({x},{y}): unknown terrain {cell.terrain!r}")

    def rid(x: int, y: int) -> str:
        return f"{name}_{x}_{y}"

    rooms: dict[str, dict[str, Any]] = {}
    for (x, y), cell in cells.items():
        if cell.terrain not in passable:
            continue  # a river/cliff/water/wall cell is a gap: no room, so movement is blocked here
        exits: dict[str, str] = {}
        # every adjacent cell (passable or not) feeds the description; only passable ones become
        # exits -- so a room can SEE the river to its east even though it cannot walk there.
        neighbours = {
            d: cells[(x + dx, y + dy)]
            for d, (dx, dy) in _STEPS.items()
            if (x + dx, y + dy) in cells
        }
        for d, (dx, dy) in _STEPS.items():
            nb = cells.get((x + dx, y + dy))
            if nb is None or nb.terrain not in passable:
                continue
            if d in _INTERCARDINAL:
                # no corner-cutting: a diagonal needs BOTH orthogonal cells passable
                o1 = cells.get((x + dx, y))
                o2 = cells.get((x, y + dy))
                if not (o1 and o1.terrain in passable and o2 and o2.terrain in passable):
                    continue
            exits[d] = rid(x + dx, y + dy)
            if nb.terrain in _CROSSING_VERB:  # a named crossing exit beside the compass one
                exits[_CROSSING_VERB[nb.terrain]] = rid(x + dx, y + dy)
        rooms[rid(x, y)] = {
            "name": f"{name.replace('_', ' ').title()} ({x},{y})",
            "desc": _describe(cell, neighbours),
            "exits": exits,
        }

    for stack in stacks:
        base_id = rid(*stack.at)
        if base_id not in rooms:
            raise FieldError(f"stack at {stack.at}: no passable field cell to stack on")
        if stack.direction not in ("up", "down"):
            raise FieldError(f"stack {stack.room_id!r}: direction must be 'up' or 'down'")
        rooms[base_id]["exits"][stack.direction] = stack.room_id
        rooms[base_id]["exits"][stack.verb] = stack.room_id
        back = _OPPOSITE[stack.direction]
        rooms[stack.room_id] = {
            "name": stack.name,
            "desc": stack.desc,
            "exits": {back: base_id, stack.back_verb: base_id},
        }
    return rooms
