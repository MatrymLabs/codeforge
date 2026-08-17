"""Offline world-overlay generation and read-only runtime loading for Engine-2D.

The canonical room graph remains YAML.  This module projects that graph into a deterministic
coordinate overlay before a world boots.  Runtime callers only use :func:`load_overlay`; the
generator is an explicit build-step function and is never called by the engine.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypedDict, cast

import yaml

CHUNK_SIZE = 16


class OverlayEntry(TypedDict):
    chunk_x: int
    chunk_y: int
    x: int
    y: int
    room: str


Overlay = Mapping[str, Mapping[str, int | str]]

_DIRECTIONS: dict[str, tuple[int, int]] = {
    "north": (0, 1),
    "south": (0, -1),
    "east": (1, 0),
    "west": (-1, 0),
    "up": (0, 1),
    "down": (0, -1),
}


def _rooms(seed_rooms: Path) -> dict[str, dict[str, object]]:
    data = cast(dict[str, Any], yaml.safe_load(seed_rooms.read_text(encoding="utf-8")) or {})
    return {label: value or {} for label, value in data.items() if label != "template"}


def _grid(rooms: Mapping[str, Mapping[str, object]]) -> dict[str, tuple[int, int]]:
    """Lay out rooms from exits, with stable ordering and no label hashing."""
    if not rooms:
        return {}
    root = sorted(rooms)[0]  # noqa: FURB192
    positions: dict[str, tuple[int, int]] = {root: (0, 0)}
    occupied = {(0, 0)}
    queue = [root]
    while queue:
        source = queue.pop(0)
        sx, sy = positions[source]
        exits = cast(dict[str, str], rooms[source].get("exits", {}))
        for direction, target in sorted(exits.items()):
            if target not in rooms or target in positions:
                continue
            dx, dy = _DIRECTIONS.get(direction, (0, 0))
            candidate = (sx + dx, sy + dy)
            if candidate in occupied:
                # Keep topology as the primary signal while making collisions deterministic.
                radius = 1
                while candidate in occupied:
                    candidate = (sx + dx + radius, sy + dy + radius)
                    radius += 1
            positions[target] = candidate
            occupied.add(candidate)
            queue.append(target)
    # A disconnected room is still represented, placed deterministically after the graph.
    for label in sorted(rooms):
        if label not in positions:
            positions[label] = (len(positions), 0)
    return positions


def _entry(room: str, coordinate: tuple[int, int]) -> OverlayEntry:
    gx, gy = coordinate
    # Each graph cell starts a chunk.  This keeps adjacency visible in chunk coordinates while
    # leaving room for future within-chunk placement without changing the projection contract.
    return {
        "chunk_x": gx,
        "chunk_y": gy,
        "x": 0,
        "y": 0,
        "room": room,
    }


def generate_overlay(seed_rooms: Path, output: Path) -> bytes:
    """Generate and write a byte-stable overlay from a Seed's ``rooms.yaml``.

    This function is an offline build step.  It is intentionally separate from ``load_overlay``
    so runtime Engine-2D cannot regenerate or mutate canonical data.
    """
    rooms = _rooms(seed_rooms)
    payload = {room: _entry(room, coordinate) for room, coordinate in sorted(_grid(rooms).items())}
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output.write_bytes(encoded)
    return encoded


def load_overlay(path: Path) -> Overlay:
    """Load a generated overlay as an immutable runtime mapping."""
    payload = json.loads(path.read_bytes())
    if not isinstance(payload, dict):
        raise ValueError("overlay root must be an object")  # noqa: TRY004
    entries: dict[str, OverlayEntry] = {}
    for room, value in payload.items():
        if not isinstance(room, str) or not isinstance(value, dict):
            raise ValueError("overlay entries must map room labels to objects")  # noqa: TRY004
        entries[room] = {
            "chunk_x": int(value["chunk_x"]),
            "chunk_y": int(value["chunk_y"]),
            "x": int(value["x"]),
            "y": int(value["y"]),
            "room": str(value["room"]),
        }
    return MappingProxyType(
        {
            room: MappingProxyType(cast(dict[str, int | str], entry))
            for room, entry in entries.items()
        }
    )
