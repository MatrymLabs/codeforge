"""Test twin for parts/world/inns.py -- an inn interior and its keeper per settlement.

Acceptance: raise_inns emits one inn room (linked back OUT to the hub) plus a peaceful keeper for
each settlement; wire_inn_doors opens each town hub's `in` exit into its inn. Refusal / tolerance: a
hub absent from the world is skipped rather than crashing the boot (mirrors the delve wiring).
"""

from __future__ import annotations

from parts.world.inns import raise_inns, wire_inn_doors
from parts.world.seed import Room

_CONFIGS = [
    {"room": "veridia_town", "name": "Veridia", "zone": "veridia", "level": 5},
    {"room": "duskwood_town", "name": "Duskwood", "zone": "duskwood", "level": 20},
]


# --- acceptance -------------------------------------------------------------------------------
def test_each_settlement_grows_one_inn_and_a_keeper():
    rooms, npcs = raise_inns(_CONFIGS)
    assert set(rooms) == {"veridia_town_inn", "duskwood_town_inn"}
    inn = rooms["veridia_town_inn"]
    assert inn["name"] == "the Veridia Inn"
    assert inn["exits"] == {"out": "veridia_town"}  # the way back to the plaza
    assert "Veridia" in inn["desc"]
    keeper = npcs["veridia_town_inn_keeper"]
    assert keeper["location"] == "veridia_town_inn"
    assert keeper["hp"] == 0  # a host is never a fight
    assert "keeper" in keeper["keywords"]


def test_the_keeper_talks_about_rest_and_the_roads():
    _, npcs = raise_inns(_CONFIGS)
    topics = npcs["veridia_town_inn_keeper"]["topics"]
    assert "rest" in topics and "roads" in topics
    assert "Forgeward Road" in topics["roads"][0]


def test_wire_inn_doors_opens_the_hub_into_the_inn():
    world: dict[str, Room] = {
        "veridia_town": Room(name="Veridia", desc="a plaza", exits={"north": "meadow"}),
        "duskwood_town": Room(name="Duskwood", desc="a plaza", exits={}),
    }
    wire_inn_doors(world, _CONFIGS)
    assert world["veridia_town"]["exits"]["in"] == "veridia_town_inn"
    assert world["veridia_town"]["exits"]["north"] == "meadow"  # existing exits untouched
    assert world["duskwood_town"]["exits"]["in"] == "duskwood_town_inn"


def test_the_inn_and_hub_link_both_ways():
    rooms, _ = raise_inns(_CONFIGS)
    world: dict[str, Room] = {"veridia_town": Room(name="V", desc="", exits={})}
    world.update(rooms)
    wire_inn_doors(world, _CONFIGS[:1])
    # hub --in--> inn --out--> hub, a closed round trip
    assert world["veridia_town"]["exits"]["in"] == "veridia_town_inn"
    assert world["veridia_town_inn"]["exits"]["out"] == "veridia_town"


# --- refusal / tolerance -----------------------------------------------------------------------
def test_a_hub_absent_from_the_world_is_skipped_not_crashed():
    world: dict[str, Room] = {}  # no hubs present at all
    wire_inn_doors(world, _CONFIGS)  # must not raise
    assert world == {}  # nothing wired, nothing broken


def test_generation_is_deterministic():
    assert raise_inns(_CONFIGS) == raise_inns(_CONFIGS)
