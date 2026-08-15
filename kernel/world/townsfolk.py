"""CARD: townsfolk -- populate the map's settlements with residents and a merchant (economy sink).

The world-generation lever (rooms via wildlands, creatures via bestiary, gear via armory) pointed at
TOWN LIFE. The map's settlements shipped as one quiet room with a single resident; an MMO town is a
living plaza with people to talk to and, above all, a MERCHANT to spend coin at -- the sink the
economy was missing (kills paid coins with nothing to buy). This reads a compact settlement manifest
(seeds/<world>/settlements.yaml, one row per town/landmark: name, zone, level) and grows each into a
small crowd of townsfolk plus one merchant stocked to the settlement's level band.

Townsfolk are peaceful (hp 0, never a fight), each a trade with a word to say (`ask <folk> about
<trade>`); the merchant declares a `shop` of level-appropriate draughts (`shop`/`buy`/`sell`). The
wares are the seed's own consumables, cross-checked at boot like any shop. Deterministic and pure
(composed by index), so the same town always grows the same folk -- reproducible like the other
generators, and merged through the same loader gates as authored NPCs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from kernel.world.seed import BlueprintError, Npc

# The trades a town's residents keep, and the one thing each will talk about (a topic keyword -> a
# line). Composed by index, so a town's crowd is varied but reproducible.
_TRADES: dict[str, str] = {
    "baker": "The ovens are warm before dawn; there is always bread for the road.",
    "smith": "Iron and ember. Bring me ore and I will bring you an edge.",
    "herbalist": "Every hedge hides a cure and three poisons. Learn which is which.",
    "tanner": "Beast-hide from the wilds makes the stoutest jerkin, if you can fell it.",
    "fisher": "The river gives and the river takes. Mostly it takes my nets.",
    "miller": "The wheel turns, the grain falls. Slow work, honest work.",
    "minstrel": "I sing of the roads beyond, where the named beasts hold the passes.",
    "potter": "Clay from the bank, fire from the forge. It is all the same craft, really.",
    "weaver": "A good cloak turns the wind, and the wind out there has teeth.",
    "cooper": "Barrels and casks. Dull, until you need to keep something dry.",
}
_ROLES: tuple[str, ...] = tuple(_TRADES)

# a plaza's worth of residents (the town's named resident from the seed is extra)
_FOLK_PER_TOWN = 4

# Draughts a merchant stocks, by the settlement's level band (floor -> {consumable: coin price}).
# Every ware is a real seed consumable, so the shop passes the boot cross-check like any shop.
_WARE_BANDS: tuple[tuple[int, dict[str, int]], ...] = (
    (0, {"healing_draught": 12, "mana_draught": 10}),
    (30, {"greater_healing_draught": 40, "greater_mana_draught": 32}),
    (90, {"grand_healing_draught": 110, "grand_mana_draught": 90, "forgefire_elixir": 160}),
)


def load_settlements(path: Path) -> list[dict[str, Any]] | None:
    """Read a seed's optional settlements.yaml (room-id -> {name, zone, level}). Returns
    None when the seed ships none. Fails loud on a malformed row (missing field, bad level)."""
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise BlueprintError("settlements.yaml must be a mapping of room-id to settlement config.")
    configs: list[dict[str, Any]] = []
    for room, cfg in raw.items():
        if not isinstance(cfg, dict):
            raise BlueprintError(f"settlement {room!r} must be a mapping of config keys.")
        merged = {**cfg, "room": room}
        for key in ("name", "zone", "level"):
            if key not in merged:
                raise BlueprintError(f"settlement {room!r} is missing required key {key!r}.")
        level = merged["level"]
        if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 300:
            raise BlueprintError(
                f"settlement {room!r}: 'level' must be an int 1..300, got {level!r}."
            )
        configs.append(merged)
    return configs


def _wares_for(level: int) -> dict[str, int]:
    """The draught stock for a settlement's level band (the deepest band it qualifies for)."""
    stock: dict[str, int] = {}
    for floor, table in _WARE_BANDS:
        if level >= floor:
            stock = table
    return stock


def make_folk(idx: int, room: str, town: str) -> tuple[str, Npc]:
    """One peaceful resident of a settlement: a trade, a greeting, and a word about its craft."""
    role = _ROLES[idx % len(_ROLES)]
    article = "an" if role[0] in "aeiou" else "a"
    folk = Npc(
        name=f"{article} {role} of {town}",
        keywords=[role, "folk", "townsfolk"],
        location=room,
        dialogue=[f'The {role} nods. "Fair day to you in {town}."'],
        next_line=0,
        hp=0,  # a townsperson is never a fight
        hp_now=0,
        xp=0,
        atk=0,
        topics={
            "town": [f"{town} is a good place to rest before the road."],
            role: [_TRADES[role]],
        },
    )
    return f"{room}_dweller_{idx}", folk


def make_merchant(level: int, room: str, town: str) -> tuple[str, Npc]:
    """A settlement's merchant: a `shop` of level-banded draughts (the coin sink), buying its own
    wares back at half price so a traveller can offload spares. Peaceful, like all townsfolk."""
    wares = _wares_for(level)
    buys = {proto: max(1, price // 2) for proto, price in wares.items()}
    merchant = Npc(
        name=f"a merchant of {town}",
        keywords=["merchant", "trader", "shop"],
        location=room,
        dialogue=['"Coin for a draught, traveller? Type SHOP to see my wares."'],
        next_line=0,
        hp=0,
        hp_now=0,
        xp=0,
        atk=0,
        shop={"sells": dict(wares), "buys": buys},
        topics={"wares": ["Draughts to keep you on your feet. Type SHOP to see them."]},
    )
    return f"{room}_merchant", merchant


def populate_settlements(configs: list[dict[str, Any]]) -> dict[str, Npc]:
    """Grow every settlement into a crowd of townsfolk plus one merchant. Returns the NPCs to merge
    into the world (before the boot link-audit, so the merchant's shop wares are cross-checked)."""
    npcs: dict[str, Npc] = {}
    for cfg in configs:
        room, town, level = cfg["room"], str(cfg["name"]), int(cfg["level"])
        for idx in range(_FOLK_PER_TOWN):
            label, folk = make_folk(idx, room, town)
            npcs[label] = folk
        m_label, merchant = make_merchant(level, room, town)
        npcs[m_label] = merchant
    return npcs
