"""Test twin for kernel/world/inns.py -- an inn interior and its keeper per settlement.

Acceptance: raise_inns emits one inn room (linked back OUT to the hub) plus a peaceful keeper for
each settlement; wire_inn_doors opens each town hub's `in` exit into its inn. Refusal / tolerance: a
hub absent from the world is skipped rather than crashing the boot (mirrors the delve wiring).
"""

from __future__ import annotations

from kernel.world.inns import is_inn_room, raise_inns, rest, wire_inn_doors
from kernel.world.resources import Resource
from kernel.world.seed import Room
from kernel.world.session import Session

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


# --- rest at the hearth ------------------------------------------------------------------------
def _weary_hero(location: str) -> Session:
    """A hero with depleted HP and MP, standing wherever we place them."""
    s = Session(player_id="alia", location=location)
    s.resources = {
        "hp": Resource(name="hp", current=3, maximum=50),
        "mp": Resource(name="mp", current=0, maximum=20),
    }
    return s


def test_is_inn_room_reads_the_suffix_convention():
    assert is_inn_room("greenhold_inn") is True
    assert is_inn_room("greenhold") is False


def test_resting_at_an_inn_restores_every_resource_to_full():
    hero = _weary_hero("greenhold_inn")
    out = rest(hero)
    assert "return in full" in out
    assert hero.resources["hp"].current == 50 and hero.resources["hp"].is_full
    assert hero.resources["mp"].current == 20 and hero.resources["mp"].is_full


def test_resting_anywhere_but_an_inn_is_refused_and_heals_nothing():
    hero = _weary_hero("greenhold")  # the plaza, not the inn
    out = rest(hero)
    assert "no hearth here" in out.lower()
    assert hero.resources["hp"].current == 3  # untouched
    assert hero.resources["mp"].current == 0


def test_the_rest_verb_is_reachable_through_the_tick():
    import forge

    hero = _weary_hero("greenhold_inn")
    out = forge.handle_command(hero, "rest")
    assert "return in full" in out
    assert hero.resources["hp"].is_full


def test_a_party_rests_together_at_the_hearth():
    from kernel.world import events, party
    from kernel.world.session import SESSIONS

    try:
        alia = _weary_hero("greenhold_inn")
        bram = Session(player_id="bram", location="greenhold_inn")
        bram.resources = {"hp": Resource(name="hp", current=1, maximum=40)}
        SESSIONS["alia"], SESSIONS["bram"] = alia, bram
        party.invite("alia", "bram")
        party.join("bram", "alia")
        out = rest(alia)  # the leader rests; the whole party at the hearth is mended
        assert "party settles" in out.lower()
        assert alia.resources["hp"].is_full and bram.resources["hp"].is_full
    finally:
        party._reset()
        for name in ("alia", "bram"):
            events.unbind_echo(name)
            SESSIONS.pop(name, None)
