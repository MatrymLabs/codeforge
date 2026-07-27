"""CARD: travel -- the Waystone network: pay to cross the world (the economy's great coin sink).

A million-room world is a long walk. The WAYSTONES are the fourteen zone hubs, each a standing
ember-stone keyed to the world's first kindling; a traveller at one may pay to be carried to any
other. This is the economy's largest sink by design: coins earned in the field drain back out every
time you skip the road, so wealth keeps moving, not piling up. The fee scales with the
DESTINATION's level band -- a hop to the starter valley costs a handful of cinders, a leap to the
endgame a small fortune -- so the network never trivialises the early game while still rewarding a
rich veteran with convenience.

Danger, not cost, gates the far zones: you may travel anywhere your purse allows, but a level-1 hero
who leaps to a level-300 waystone simply dies to what waits there. `travel` (at a waystone) lists
the network and its fares; `travel <where>` pays the fee and carries you. Data-driven: the hubs are
a manifest (seeds/<world>/waystones.yaml); a seed with no waystones has no network.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from parts.world.coinage import purse
from parts.world.seed import SeedError
from parts.world.session import Session

_BASE_FARE = 20  # cinders, before the destination's level premium
_FARE_PER_LEVEL = 2  # cinders added per level of the destination's band


def load_waystones(path: Path) -> dict[str, dict[str, Any]] | None:
    """Read a seed's optional waystones.yaml (hub room-id -> {name, level}). None if the seed ships
    no network. Fails loud on a malformed hub (missing field, bad level)."""
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise SeedError("waystones.yaml must be a mapping of hub room-id to config.")
    stones: dict[str, dict[str, Any]] = {}
    for room, cfg in raw.items():
        if not isinstance(cfg, dict) or "name" not in cfg or "level" not in cfg:
            raise SeedError(f"waystone {room!r} needs a 'name' and a 'level'.")
        level = cfg["level"]
        if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 300:
            raise SeedError(f"waystone {room!r}: 'level' must be an int 1..300, got {level!r}.")
        stones[room] = {"name": str(cfg["name"]), "level": level}
    return stones


def fare(level: int) -> int:
    """The coin fee to travel to a hub in a given level band."""
    return _BASE_FARE + _FARE_PER_LEVEL * level


def _match(word: str, stones: dict[str, dict[str, Any]]) -> str | None:
    """The hub id a player's word names -- by id or a case-insensitive name prefix, or None."""
    word = word.strip().lower()
    if word in stones:
        return word
    for room, cfg in stones.items():
        if str(cfg["name"]).lower() == word or str(cfg["name"]).lower().startswith(word):
            return room
    return None


def travel(session: Session, arg: str, stones: dict[str, dict[str, Any]]) -> str:
    """`travel [where]` at a waystone: bare lists the network and fares; a destination pays the fee
    and carries you there. Fails cleanly off a waystone, on an unknown hub, or an empty purse."""
    here = session.location
    if here not in stones:
        return "There is no waystone here. Travel begins at a zone's waystone (its hub)."
    word = arg.strip().lower()
    if not word:
        return _network(session, stones)
    dest = _match(word, stones)
    if dest is None or dest == here:
        if dest == here:
            return f"You are already at the {stones[here]['name']} waystone."
        return f"The network knows no waystone called '{arg.strip()}'. Type TRAVEL to see them."
    cost = fare(stones[dest]["level"])
    if session.coins < cost:
        return f"The waystone demands {purse(cost)}; your purse holds only {purse(session.coins)}."

    session.coins -= cost
    session.location = dest
    if session.named:
        from parts.world.characters import save_character

        save_character(session)
    name = stones[dest]["name"]
    return f"The ember-stone flares. You are carried to the {name} waystone. ({purse(cost)} spent.)"


def _network(session: Session, stones: dict[str, dict[str, Any]]) -> str:
    """The bare `travel` view: every OTHER waystone and its fare, cheapest first."""
    here = session.location
    others = sorted(
        ((room, cfg) for room, cfg in stones.items() if room != here),
        key=lambda item: item[1]["level"],
    )
    lines = [f"The {stones[here]['name']} waystone hums. Purse: {purse(session.coins)}.", "To:"]
    for _room, cfg in others:
        lines.append(f"  {cfg['name']:<18} (levels {cfg['level']}+)  {purse(fare(cfg['level']))}")
    lines.append("Travel with: travel <where>")
    return "\n".join(lines)
