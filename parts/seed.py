"""CARD: seed -- load and validate room packs from YAML.

The world is a file. This loader is also a GATE: a seed that fails
validation never reaches the engine.

Identity rules:
- Every room has a LABEL (its YAML key): lowercase_snake_case, unique,
  permanent. Exits, saves, and code reference labels.
- Every room has a NAME: human display text. Free to change anytime.

The room template (everything is a room):
- Engine defaults make every room born complete: name is generated
  from the label, desc gets a placeholder, exits default to empty.
- An optional top-level 'template:' block sets file-wide defaults.
- A room's own fields always win.
  merge order: engine defaults -> template: block -> room fields.
"""

import re
from pathlib import Path
from typing import Any, TypedDict

import yaml

LABEL_RE = re.compile(r"^[a-z][a-z0-9_]*$")
DEFAULT_DESC = "There is nothing remarkable here yet."


class Room(TypedDict):
    """The shape every room must have. Structure, checked by machine."""

    name: str
    desc: str
    exits: dict[str, str]


class SeedError(Exception):
    """Raised when a seed file fails validation. Names the exact problem."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """A YAML loader that refuses duplicate keys instead of silently
    overwriting. Plain YAML keeps the LAST duplicate and says nothing --
    a world-corruption bug waiting for a builder."""


def _construct_unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in mapping:
            raise SeedError(
                f"Duplicate label '{key}' in seed file. "
                "Every label must be unique -- rename one of them."
            )
        mapping[key] = loader.construct_object(value_node, deep=True)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _check_label(label: str, what: str) -> None:
    if not isinstance(label, str) or not LABEL_RE.match(label):
        suggestion = re.sub(r"[^a-z0-9_]+", "_", str(label).lower()).strip("_") or "my_room"
        raise SeedError(
            f"{what} label '{label}' is invalid. Labels must be lowercase_snake_case "
            f"(letters, digits, underscores; starts with a letter). Try: '{suggestion}'."
        )


def _default_name(label: str) -> str:
    return label.replace("_", " ").title()


def load_rooms(path: Path) -> dict[str, Room]:
    """Read a rooms.yaml seed file, validate it, return the room graph."""
    if not path.exists():
        raise SeedError(f"Seed file not found: {path}")

    data = yaml.load(path.read_text(), Loader=_UniqueKeyLoader)
    if not isinstance(data, dict) or not data:
        raise SeedError(f"Seed file is empty or not a mapping: {path}")

    file_template = data.pop("template", None) or {}
    if not isinstance(file_template, dict):
        raise SeedError("'template:' must be a mapping of default room fields.")

    rooms: dict[str, Room] = {}
    for room_label, raw in data.items():
        _check_label(room_label, "Room")
        if raw is None:
            raw = {}  # a bare label is a valid room: all defaults
        if not isinstance(raw, dict):
            raise SeedError(f"Room '{room_label}' is not a mapping.")
        merged: dict[str, Any] = {
            "name": _default_name(room_label),
            "desc": DEFAULT_DESC,
            "exits": {},
            **file_template,
            **raw,
        }
        for field, kind in (("name", str), ("desc", str), ("exits", dict)):
            if not isinstance(merged[field], kind):
                raise SeedError(f"Room '{room_label}' field '{field}' must be {kind.__name__}.")
        rooms[room_label] = Room(name=merged["name"], desc=merged["desc"], exits=merged["exits"])

    # The graph gate: every exit must lead to a room label in this seed.
    for room_label, room in rooms.items():
        for direction, destination in room["exits"].items():
            if destination not in rooms:
                raise SeedError(
                    f"Room '{room_label}' has exit '{direction}' -> '{destination}', "
                    "which does not exist in this seed."
                )

    return rooms
