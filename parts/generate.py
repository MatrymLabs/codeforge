"""CARD: generate -- @sg, the system item generator (wizard/owner only).

`@sg item <pattern>` stamps a known item pattern into the world at your feet. It
NEVER conjures from nothing: only patterns filed in catalog/items.yaml can be
generated (an unknown pattern is refused, with the known list). Each spawn is a live
instance in world state; the item PATTERN is the filed ITM-* designation it derives
from -- state is canonical, the registry files the design.

Authorization lives on the command (an ADMIN verb, wizard+); this card only forges.
"""

import os
from pathlib import Path
from typing import Any

import yaml

from parts.registry import load_collective
from parts.world.events import announce
from parts.world.items import ITEMS
from parts.world.seed import Item
from parts.world.session import Session, display_name

_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = Path(os.environ.get("CODEFORGE_ITEM_CATALOG", str(_ROOT / "catalog" / "items.yaml")))


class PatternError(ValueError):
    """The item catalog is malformed -- fail loud, never generate from a bad pattern."""


def load_patterns(path: Path | None = None) -> dict[str, Any]:
    """Read the item-generation catalog. A missing catalog is empty, not an error."""
    target = path if path is not None else CATALOG_PATH
    if not target.exists():
        return {}
    data: Any = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise PatternError("item catalog must be a mapping of pattern -> fields")
    return data


def _unique_label(base: str, taken: set[str]) -> str:
    """A fresh instance label, so generating Excalibur twice yields two instances."""
    if base not in taken:
        return base
    n = 2
    while f"{base}_{n}" in taken:
        n += 1
    return f"{base}_{n}"


def _pattern_designation(pattern: str) -> str:
    for record in load_collective():
        if record.type == "ITM" and record.label == pattern:
            return record.designation
    return "(unfiled)"


def generate_item(
    pattern: str, room_id: str, patterns: dict[str, Any] | None = None
) -> tuple[str | None, str]:
    """Spawn a known item pattern into a room. Returns (instance_label | None, message).
    A None label means nothing was generated (unknown pattern)."""
    catalog = load_patterns() if patterns is None else patterns
    key = pattern.strip().lower()
    if key not in catalog:
        known = ", ".join(sorted(catalog)) or "(none on file)"
        return None, f"[SYSTEM] No pattern '{pattern}' on file. Known patterns: {known}"
    spec = catalog[key]
    if not isinstance(spec, dict):
        raise PatternError(f"pattern '{key}' must be a mapping of fields")
    name = str(spec.get("name") or f"a {key.replace('_', ' ')}")
    keywords = list(spec.get("keywords") or [key])
    label = _unique_label(key, set(ITEMS))
    ITEMS[label] = Item(
        name=name, keywords=keywords, location=f"room:{room_id}", slot="", mods={}, prototype=label
    )
    return label, f"[SYSTEM] Forged: {name}  ({_pattern_designation(key)} / instance: {label})"


def system_generate(session: Session, argument: str) -> str:
    """`@sg item <pattern>` -- forge a filed item pattern at your feet."""
    parts = argument.split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "item":
        return "[SYSTEM] Usage: @sg item <pattern>   (try `registry type ITM` for patterns)"
    label, message = generate_item(parts[1], session.location)
    if label is not None:
        announce(
            session.location,
            f"The air ignites - {ITEMS[label]['name']} is forged into being by "
            f"{display_name(session.player_id)}.",
            exclude=session.player_id,
        )
    return message
