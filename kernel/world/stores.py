"""CARD: stores -- a general store off every town plaza: the market for raw materials.

The plaza merchant sells draughts (the coin SINK); this is its counterpart, a trading post that
puts a price on the wilds' raw materials. Gatherers had nowhere to turn ore, shards, and herbs into
coin, and crafters had no way to buy a material their own biome does not yield; the store is both.
It is the second interior a town gains (after the inn), reached `market` off the hub, `out` back.

Pure additive generation in the inn's mould: `raise_stores` returns (rooms, npcs) to merge and
`wire_store_doors` opens each hub's `market` exit into its store, in place. The provisioner keeps a
two-way `shop` of materials (buy low, sell higher), so `shop`/`buy`/`sell` work there like any
merchant. The buy list is filtered to materials that actually exist in the loaded seed, so a world
missing a herb simply does not price it; the boot cross-check (real prototypes only) always passes.
"""

from __future__ import annotations

from typing import Any

from kernel.world.seed import Npc, Room

# Base coin a store PAYS for one unit of raw material (it SELLS at twice this, the market's spread).
_MATERIAL_BUY: dict[str, int] = {
    "ember_shard": 2,
    "hollow_ingot": 4,
    "raw_ore": 3,
}
_HERB_BUY = 3  # every biome herb fetches the same modest price


def _material_prices(known_items: set[str]) -> tuple[dict[str, int], dict[str, int]]:
    """The store's (buys, sells) tables, restricted to materials that exist in the loaded seed.
    Herb labels come canonically from the wildlands biome map, never guessed."""
    from kernel.world.wildlands import _BIOME_HERB

    wanted = dict(_MATERIAL_BUY)
    for herb in _BIOME_HERB.values():
        wanted[herb] = _HERB_BUY
    buys = {mat: price for mat, price in wanted.items() if mat in known_items}
    sells = {mat: price * 2 for mat, price in buys.items()}  # the spread: buy low, sell higher
    return buys, sells


def _provisioner(store_label: str, town: str, buys: dict[str, int], sells: dict[str, int]) -> Npc:
    """A peaceful trader who buys the wilds' raw materials and sells them on to crafters."""
    return Npc(
        name=f"a provisioner of {town}",
        keywords=["provisioner", "trader", "store"],
        location=store_label,
        dialogue=['"Ore, shard, or herb, I pay fair coin. Type SHOP to see the going rate."'],
        next_line=0,
        hp=0,  # a trader is never a fight
        hp_now=0,
        xp=0,
        atk=0,
        shop={"sells": sells, "buys": buys},
        topics={
            "materials": ["The wilds are full of coin, if you know what to gather. I buy it all."],
            "store": [
                "A fair price for raw stock, and stock to sell to any crafter short a material."
            ],
        },
    )


def raise_stores(
    configs: list[dict[str, Any]], known_items: set[str]
) -> tuple[dict[str, Room], dict[str, Npc]]:
    """Build one general store per settlement, each with its provisioner and a two-way materials
    market. Returns (rooms, npcs) to merge; `wire_store_doors` opens each hub's `market` exit in."""
    buys, sells = _material_prices(known_items)
    rooms: dict[str, Room] = {}
    npcs: dict[str, Npc] = {}
    for cfg in configs:
        hub, town = cfg["room"], str(cfg["name"])
        store_label = f"{hub}_store"
        rooms[store_label] = Room(
            name=f"the {town} General Store",
            desc=(
                f"The {town} General Store. Bins and crates line the walls, sorted by the raw "
                "stock of the wilds: ore and shard, and bundled herbs from every biome the roads "
                "reach. A provisioner weighs it all by eye. A door leads back OUT to the plaza."
            ),
            exits={"out": hub},
        )
        npcs[f"{store_label}_keeper"] = _provisioner(store_label, town, buys, sells)
    return rooms, npcs


def wire_store_doors(world: dict[str, Room], configs: list[dict[str, Any]]) -> None:
    """Open each town hub `market` into its store, in place. A seed may omit a settlement's hub
    room; skip it rather than fail the boot (the same tolerance the inn and delve wiring keep)."""
    for cfg in configs:
        hub = cfg["room"]
        if hub in world:
            world[hub]["exits"].setdefault("market", f"{hub}_store")
