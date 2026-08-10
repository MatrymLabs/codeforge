"""CARD: room_category -- the bracketed category a room shows under its title.

The Green Build Directive's room-output standard names a hierarchy: title, BRACKETED CATEGORY,
authored prose, environmental prose, visible NPC and object sentences, then a horizontal
obvious-exits line. Every element of that was present except the category, which no room declared
and no renderer emitted.

It is NOT a new seed field. The world already knows this: `zones.yaml` groups rooms and gives each
zone a `biome` and a `region`, so a room's category is derivable from data that exists rather than
from a field an author has to remember to fill in twice. Deriving beats storing: a room moved
between zones gets the right category with no second edit and no chance of the two disagreeing.

Honest when it cannot answer. A seed that ships no `zones.yaml` (first-forge does not) gets NO
category rather than an invented one. A blank is truthful; `[Unknown]` under every room title is
noise pretending to be information.

Inputs:  a room label, and the zone pack the world booted with.
Outputs: the display category, or "" when the world does not say.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = ["category_of", "display_category", "index_by_room"]


def display_category(raw: str) -> str:
    """A seed's slug as a player reads it: `temperate-meadow` becomes `Temperate Meadow`.

    Only the RENDERING is prettified. The seed's slug stays canonical, because labels are
    lowercase_snake or kebab identity strings and display capitalisation happens at render time.
    """
    words = raw.replace("_", " ").replace("-", " ").split()
    return " ".join(word.capitalize() for word in words)


def index_by_room(zones: Mapping[str, Any]) -> dict[str, str]:
    """Map every room label to its zone's category, once, instead of scanning zones per look.

    A room listed in two zones is a content defect this card does NOT adjudicate: the first
    listing wins and the world stays renderable. The zone loader is the right place to refuse
    that, and inventing a second opinion here would just hide it.
    """
    index: dict[str, str] = {}
    for zone in zones.values():
        biome = _field(zone, "biome") or _field(zone, "region")
        if not biome:
            continue
        for room in _rooms(zone):
            index.setdefault(room, biome)
    return index


def category_of(room_label: str, index: Mapping[str, str]) -> str:
    """The bracketed category for one room, ready to render, or "" when unknown."""
    raw = index.get(room_label, "")
    return display_category(raw) if raw else ""


def _field(zone: Any, name: str) -> str:
    """Read a field from a Zone dataclass or a plain mapping, whichever the loader returns."""
    value = zone.get(name, "") if isinstance(zone, Mapping) else getattr(zone, name, "")
    return str(value).strip() if value else ""


def _rooms(zone: Any) -> tuple[str, ...]:
    rooms = zone.get("rooms") if isinstance(zone, Mapping) else getattr(zone, "rooms", ())
    if not rooms:
        return ()
    return tuple(str(room) for room in rooms)
