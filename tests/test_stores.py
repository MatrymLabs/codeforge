"""Test twin for parts/world/stores.py -- a general store (materials market) per settlement.

Acceptance: raise_stores emits one store room (linked back OUT to the hub) plus a provisioner with a
two-way materials shop (buys raw stock, sells it on at a spread) for every settlement;
wire_store_doors opens each hub's `market` exit into its store. Refusal / tolerance: the buy list is
restricted to materials the loaded seed actually has (so the boot cross-check holds), and a hub
absent from the world is skipped rather than crashing the boot.
"""

from __future__ import annotations

from parts.world.seed import Room
from parts.world.stores import raise_stores, wire_store_doors

_CONFIGS = [
    {"room": "veridia_town", "name": "Veridia", "zone": "veridia", "level": 5},
    {"room": "duskwood_town", "name": "Duskwood", "zone": "duskwood", "level": 20},
]
# a realistic material set the seed provides
_KNOWN = {"ember_shard", "hollow_ingot", "raw_ore", "meadowfoil", "fernshade", "a_sword"}


# --- acceptance -------------------------------------------------------------------------------
def test_each_settlement_grows_one_store_and_a_provisioner():
    rooms, npcs = raise_stores(_CONFIGS, _KNOWN)
    assert set(rooms) == {"veridia_town_store", "duskwood_town_store"}
    store = rooms["veridia_town_store"]
    assert store["name"] == "the Veridia General Store"
    assert store["exits"] == {"out": "veridia_town"}
    keeper = npcs["veridia_town_store_keeper"]
    assert keeper["location"] == "veridia_town_store"
    assert keeper["hp"] == 0  # a trader is never a fight
    assert "provisioner" in keeper["keywords"]


def test_the_shop_is_a_two_way_materials_market():
    _, npcs = raise_stores(_CONFIGS, _KNOWN)
    shop = npcs["veridia_town_store_keeper"]["shop"]
    # buys the real materials it was told exist...
    assert shop["buys"]["ember_shard"] == 2 and shop["buys"]["meadowfoil"] == 3
    # ...and sells them on at twice the buy price (the spread)
    assert shop["sells"]["ember_shard"] == 4 and shop["sells"]["meadowfoil"] == 6


def test_only_materials_present_in_the_seed_are_priced():
    # a world that ships no herbs at all: the store simply does not price them
    _, npcs = raise_stores(_CONFIGS, {"ember_shard"})
    shop = npcs["veridia_town_store_keeper"]["shop"]
    assert set(shop["buys"]) == {"ember_shard"}
    assert "meadowfoil" not in shop["buys"]  # absent material never named (cross-check stays green)


def test_wire_store_doors_opens_the_hub_market_exit():
    world: dict[str, Room] = {
        "veridia_town": Room(name="Veridia", desc="a plaza", exits={"in": "veridia_town_inn"}),
    }
    wire_store_doors(world, _CONFIGS[:1])
    assert world["veridia_town"]["exits"]["market"] == "veridia_town_store"
    assert world["veridia_town"]["exits"]["in"] == "veridia_town_inn"  # the inn exit is untouched


# --- refusal / tolerance -----------------------------------------------------------------------
def test_a_hub_absent_from_the_world_is_skipped_not_crashed():
    world: dict[str, Room] = {}
    wire_store_doors(world, _CONFIGS)  # must not raise
    assert world == {}


def test_generation_is_deterministic():
    assert raise_stores(_CONFIGS, _KNOWN) == raise_stores(_CONFIGS, _KNOWN)
