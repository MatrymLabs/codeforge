"""Test twin: a seed is a game. Codeforge boots first-forge or spiral-ascent."""

import importlib

import pytest

import parts.world.seed
from parts.cli import _pop_seed, main
from parts.world.seed import (
    SEEDS_ROOT,
    SeedError,
    available_seeds,
    load_abilities,
    load_doors,
    load_items,
    load_jobs,
    load_npcs,
    load_quest,
    load_rooms,
)

FIRST_FORGE = SEEDS_ROOT / "first-forge"

SPIRAL = SEEDS_ROOT / "spiral-ascent"
AETHRYN = SEEDS_ROOT / "aethryn"


def test_both_games_are_installed():
    seeds = available_seeds()
    assert "first-forge" in seeds and "spiral-ascent" in seeds


def test_flagship_aethryn_is_installed():
    assert "aethryn" in available_seeds()


def test_aethryn_passes_every_loader_gate_and_spawns_on_the_shore():
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    # The world bible's Kindlands Coast: the first room is the spawn, no hardcoded start.
    assert next(iter(rooms)) == "the_waking_shore"
    assert rooms["cinderhearth_square"]["exits"]["down"] == "cold_cellar"
    load_items(AETHRYN / "items.yaml")  # gates: valid labels, present location
    load_npcs(AETHRYN / "npcs.yaml")
    jobs = load_jobs(AETHRYN / "jobs.yaml")
    assert "emberwright" in jobs and jobs["pathfinder"]["stats"]["speed"] == 14


def test_aethryn_every_exit_and_placement_resolves():
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    for label, room in rooms.items():
        for direction, dest in room["exits"].items():
            assert dest in rooms, f"{label} exit {direction} -> {dest} is a dead link"
    for label, item in load_items(AETHRYN / "items.yaml").items():
        if item["location"] in ("player", "nowhere"):
            continue  # a carried item or a drop-only prototype (spawned by loot), not room-placed
        assert item["location"].split(":")[-1] in rooms, f"item {label} floats nowhere"
    for label, npc in load_npcs(AETHRYN / "npcs.yaml").items():
        assert npc["location"].split(":")[-1] in rooms, f"npc {label} floats nowhere"


def test_aethryn_no_room_is_meaninglessly_empty():
    """Every room holds content -- a foe, an NPC, or a deliberate exception (the spawn, a rest-stop,
    a transit hub, or a puzzle room whose content IS the puzzle). Guards against a wilderness or
    dungeon room shipping empty of anything to find, now that the empty rooms are populated."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    occupied = {npc["location"].split(":")[-1] for npc in npcs.values()}
    # rooms allowed to hold no foe or NPC, each for a stated reason
    allowed_empty = {
        "the_waking_shore",  # the spawn: a fresh Forger is not ambushed at birth
        "wayfarers_rest",  # a rest-stop on the Ember-road: a safe haven by design
        "old_reach_bridge",  # a mend-the-span puzzle room; its content is the repair
        "cold_cellar",  # the jumbled-Forge puzzle room; its content is ordering the steps
        "the_deepwater_berth",  # a far-ferry transit hub (its captains cry the crossings)
    }
    empty = {r for r in rooms if r not in occupied} - allowed_empty
    assert not empty, f"wilderness/dungeon rooms shipped empty of content: {sorted(empty)}"
    # the ruin's flavour names a salvage-wraith; it must actually exist there (no broken promise)
    assert npcs["salvage_wraith"]["location"] == "the_scoured_ruin"


def test_aethryn_wren_keeps_a_coast_shop_so_act_one_has_an_economy():
    """The starting coast now has a functional till: Wren sells heals and a starter blade, so a
    fresh Forger can spend the coins the wolves drop instead of reaching mid-game for a shop."""
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    wren = npcs["wren"]
    assert "shop" in wren, "the coast town smith keeps no shop -- Act 1 has no economy"
    sells = wren["shop"]["sells"]
    assert sells.get("healing_draught") and sells.get("mana_draught")  # heals on the coast
    assert "cinder_hammer" in sells  # a starter weapon you can buy, not only delve for
    assert wren["shop"]["buys"].get("ember_shard")  # and coast salvage has a buyer


def test_aethryn_capital_npcs_hold_real_conversations():
    """The capital feels lived-in: its lore, order, and gate keepers answer `ask about <topic>`, so
    a curious player learns the world and the Orders instead of reading cycling flavour barks."""
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    ilya = npcs["grandforge_loremaster"]["topics"]
    assert {"unforging", "seed", "spiral"} <= set(ilya)  # the lore keeper explains the world
    recruiter = npcs["order_recruiter"]["topics"]
    assert {"making", "warcraft", "knowing", "gathering"} <= set(recruiter)  # teaches the 4 Orders
    keeper = npcs["warden_keeper"]["topics"]
    assert "spiral" in keeper  # the gate keeper describes the climb ahead
    # every topic is a non-empty list of reply lines (the loader gate, re-asserted for content)
    for who in (ilya, recruiter, keeper):
        assert all(lines and all(isinstance(x, str) for x in lines) for lines in who.values())


def test_aethryn_elemental_abilities_carry_their_element():
    """The caster Jobs have elemental identity: their thematically-elemental strikes are TYPED, so
    their whole kit interacts with foe resistances and the themed Spiral (a stormcaller's lightning
    is resisted by a storm Coil; bring a geomancer's stone). Only the elemental moves are typed, so
    the roster reads as distinct rather than a wall of untyped strikes."""
    ab = load_abilities(AETHRYN / "abilities.yaml")
    expected = {
        "firestorm": "FIR",
        "frostbite": "ICE",
        "chain_lightning": "LGT",
        "gale": "WND",
        "stonefall": "ERT",
        "smite": "HLY",
        "holy_strike": "HLY",
        "killing_dark": "DRK",
        "toxin": "PSN",
        "hex": "CRS",
        "turret_fire": "FIR",
        "word_of_ruin": "DRK",
    }
    for label, element in expected.items():
        assert ab[label].get("element") == element, f"{label} should strike with {element}"


def test_aethryn_side_quests_vary_beyond_kill_bounties():
    """Side content has variety, not just the hunt-contracts on the bounty board: a GATHER quest
    (advance by picking up wild ember) and a DISCOVERY quest (advance by reaching the deepest
    floor), each a different verb from felling a foe."""
    from parts.world.seed import load_quest

    harvest = load_quest(AETHRYN / "quests" / "ember_harvest.yaml")
    assert harvest is not None and harvest["steps"][0]["on_take"] == "ember_shard"  # gather
    deep = load_quest(AETHRYN / "quests" / "sound_the_deep.yaml")
    assert deep is not None and deep["steps"][0]["on_enter"] == "the_cinderheart"  # discovery
    # neither side quest advances on a defeat -- they reward gathering and exploring
    for spec in (harvest, deep):
        assert not any(s.get("on_defeat") for s in spec["steps"])


def test_aethryn_recipes_forge_real_items_from_real_materials():
    """The maker's loop is real content: the flagship ships recipes, and every recipe forges a real
    item from real materials (a cross-check, so a recipe can never make or need a phantom item)."""
    from parts.world.seed import load_recipes

    recipes = load_recipes(AETHRYN / "recipes.yaml")
    assert recipes, "the flagship ships no crafting recipes -- the maker Jobs have nothing to forge"
    item_labels = set(load_items(AETHRYN / "items.yaml"))
    for label, recipe in recipes.items():
        assert recipe["makes"] in item_labels, f"recipe {label} makes unknown {recipe['makes']}"
        for material in recipe["inputs"]:
            assert material in item_labels, f"recipe {label} needs unknown material {material}"


def test_aethryn_cradle_offers_a_slot_complete_armor_set():
    """A world you can walk needs gear to wear: the Emberreach cradle ships the Emberhide set, a
    slot-complete starter armor kit (head + body + arm) dropped by the coast beasts, so a fresh
    Forger can outfit every armor slot before leaving the cradle (armor was the thin slot)."""
    items = load_items(AETHRYN / "items.yaml")
    emberhide = {"emberhide_hood": "head", "emberhide_jerkin": "body", "emberhide_wraps": "arm"}
    for label, slot in emberhide.items():
        assert label in items, f"the Emberhide set is missing {label}"
        assert items[label]["slot"] == slot, f"{label} should fill the {slot} slot"
        assert items[label]["mods"], f"{label} grants no stats"  # a real piece, not a flavour prop
    # every piece is obtainable in the cradle: dropped by an early coast beast, not stranded
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    assert "emberhide_hood" in npcs["reach_wolf"]["drops"]
    assert "emberhide_jerkin" in npcs["thornback_boar"]["drops"]
    assert "emberhide_wraps" in npcs["tide_crawler"]["drops"]
    # the cradle now covers all three ARMOR slots between its own drops (the point of this set)
    cradle_foes = ("reach_wolf", "thornback_boar", "tide_crawler")
    cradle_slots = {
        items[d]["slot"] for f in cradle_foes for d in npcs[f].get("drops", []) if items[d]["slot"]
    }
    assert {"head", "body", "arm"} <= cradle_slots


def test_aethryn_every_reach_offers_a_slot_complete_loadout():
    """The wide gear pass: EVERY Reach drops a slot-complete GEAR loadout (weapon + head + body +
    arm) from its own foes, so a Forger can re-outfit their whole kit at every stage of the 1-300
    journey. Armor was the thin slot (the world had 4 pieces total) and five Reaches had no weapon;
    this pins both holes closed everywhere, measured through the `completeness` shelf part."""
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    items = load_items(AETHRYN / "items.yaml")
    # each Reach, named by the foes whose drops should cover a full loadout between them
    reach_foes = {
        "Emberreach cradle": [
            "reach_wolf",
            "thornback_boar",
            "tide_crawler",
            "cinder_wight",
            "road_reaver",
            "ash_colossus",
        ],
        "Cinderdeep": ["cold_vein_lurker", "drowned_maker", "hollow_smith"],
        "Quenchmere": ["brine_wight", "sunken_revenant", "sunhold_warden"],
        "Verdance": ["canopy_stalker", "mire_returned", "boughwarden"],
        "Rimefall": ["glass_hound", "rime_king"],
        "Kollforge": ["forgeborn", "cinder_drake", "vent_lord"],
        "Sundered Sky": ["stormkin", "fall_wight", "court_warden"],
    }
    # measured through the Hardware Store's `completeness` part (dogfooding the harvest)
    from parts.shelf.completeness import coverage

    for reach, foes in reach_foes.items():
        slots = [
            items[d]["slot"]
            for f in foes
            for d in npcs[f].get("drops", [])
            if items.get(d, {}).get("slot")
        ]
        gear = coverage(slots, required=("weapon", "head", "body", "arm"))
        assert gear.complete, f"{reach} cannot outfit a full loadout: missing {gear.missing}"


def test_aethryn_cinderdeep_descends_to_a_real_bottom():
    """The coast's downward road no longer dead-ends: the maw opens down through the Drowned Way to
    the Cinderheart, where a frost-typed bottom-boss (bring fire) gives the deep a real climax."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert rooms["cinderdeep_maw"]["exits"].get("down") == "the_drowned_way"  # no longer a dead-end
    assert rooms["the_drowned_way"]["exits"]["down"] == "the_cinderheart"  # descends to the bottom
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    boss = npcs["drowned_forgemaster"]
    assert boss["level"] == 24 and boss["tier"] == "boss" and boss["lethal"] is True
    # an elemental puzzle: a maker of black ice that resists frost and is weak to fire
    assert boss["attack_element"] == "ICE"
    assert boss["resistances"] == {"ICE": "Resist", "FIR": "Weak"}
    assert boss["drops"] == ["drowned_seal"]  # the deep pays a real reward
    assert load_items(AETHRYN / "items.yaml")["drowned_seal"]["slot"] == "accessory_2"


def test_aethryn_sundered_sky_is_the_last_surface_reach_and_the_spiral_gate():
    """The sixth Reach (Build Order Phase 5): the berth's sky-lanes rise to the Sundered Sky -- the
    floating lands the Unforging tore loose, the last surface Reach, whose capital Highgate wires
    NORTH (by anchor-line) onto the Forgeward Road, a second way onto the flat endgame frontier."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert rooms["the_deepwater_berth"]["exits"].get("up") == "the_sky_lanes"
    assert (
        rooms["highgate"]["exits"].get("north") == "coilfoot_ascent"
    )  # the surface joins the Road
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    assert npcs["stormkin"]["level"] == 60 and npcs["fall_wight"]["level"] == 64
    assert "spiral" in npcs["sky_warden"]["topics"] and "shop" in npcs["anchor_keeper"]
    court = npcs["court_warden"]
    assert court["level"] == 72 and court["tier"] == "boss" and court["lethal"] is True
    assert court["resistances"] == {"DRK": "Resist", "HLY": "Weak"}  # bring radiance to the shadow
    arc = load_quest(AETHRYN / "quests" / "the_sundered_sky.yaml")
    assert arc is not None and arc["steps"][-1]["on_defeat"] == "court_warden"


def test_aethryn_kollforge_is_the_molten_reach_before_the_spiral():
    """The fifth Reach (Build Order Phase 5): the berth ferries west to the Kollforge -- the molten
    surface land closest to the Forge, the Kollkin fire-Forgers of Emberkoll, and the Vent-Lord, the
    last guardian before the Spiral endgame (a level-62 boss)."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert rooms["the_deepwater_berth"]["exits"].get("west") == "the_molten_passage"
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    assert npcs["cinder_drake"]["level"] == 50 and npcs["forgeborn"]["level"] == 54
    assert "kollforge" in npcs["ventforge_master"]["topics"] and "shop" in npcs["kollkin_trader"]
    lord = npcs["vent_lord"]
    assert lord["level"] == 62 and lord["tier"] == "boss" and lord["lethal"] is True
    assert lord["resistances"] == {"FIR": "Resist", "WTR": "Weak"}  # bring flood to the fire
    arc = load_quest(AETHRYN / "quests" / "the_kollforge.yaml")
    assert arc is not None and arc["steps"][-1]["on_defeat"] == "vent_lord"


def test_aethryn_rimefall_is_the_frozen_high_level_reach():
    """The fourth Reach (Build Order Phase 4): a deepwater berth ferries north to the Rimefall -- a
    continent flash-frozen in the Unforging, its golden-age cities whole under the ice, kept by the
    Silent Anvil, climaxing in the flash-frozen Rime-King (a level-52 boss)."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert (
        rooms["tidewharf_plaza"]["exits"].get("north") == "the_deepwater_berth"
    )  # the far-ferry hub
    assert rooms["the_deepwater_berth"]["exits"].get("north") == "the_riming_passage"
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    assert npcs["glass_hound"]["level"] == 40 and npcs["glass_hound"]["tier"] == "elite"
    assert "silent_anvil" in npcs["stillhearth_keeper"]["topics"]  # the world's conscience speaks
    king = npcs["rime_king"]
    assert king["level"] == 52 and king["tier"] == "boss" and king["lethal"] is True
    assert king["resistances"] == {"ICE": "Resist", "FIR": "Weak"}  # bring fire to thaw the reign
    assert "stillheart" in king["drops"]  # a Reach-Relic of the golden age (+ the Rimeplate set)
    arc = load_quest(AETHRYN / "quests" / "the_rimefall.yaml")
    assert arc is not None and arc["steps"][-1]["on_defeat"] == "rime_king"


def test_aethryn_verdance_is_a_living_wild_reach_off_the_crossroads():
    """The third Reach (Build Order Phase 3): Tidewharf ferries west to the Verdance -- a living
    jungle continent with the Deeprooted capital Highbough and the Heart-Grove (a boss that is the
    apex of a real food chain: canopy-stalker, mire-returned, then the Boughwarden)."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert (
        rooms["tidewharf_docks"]["exits"].get("west") == "the_verdant_passage"
    )  # a Reach off the hub
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    # a believable ecosystem: apex predator, scavenger, and the living heart, level-banded
    assert npcs["canopy_stalker"]["level"] == 22 and npcs["mire_returned"]["level"] == 26
    assert "verdance" in npcs["grove_elder"]["topics"] and "shop" in npcs["canopy_trader"]
    warden = npcs["boughwarden"]
    assert warden["level"] == 32 and warden["tier"] == "boss" and warden["lethal"] is True
    assert warden["resistances"] == {
        "ERT": "Resist",
        "WND": "Weak",
    }  # bring wind to the living wild
    arc = load_quest(AETHRYN / "quests" / "the_verdance.yaml")
    assert arc is not None and arc["steps"][-1]["on_defeat"] == "boughwarden"


def test_aethryn_quenchmere_is_a_second_continent_reached_by_sea():
    """The first sea-crossing (Build Order Phase 2): Quench Harbor's ferry runs west to the
    Quenchmere -- a second Reach with the free-port Tidewharf (an Accord-Speaker, a Merewright shop,
    a Salvage agent) and the drowned Sunhold dungeon below it."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    # the world grows across the sea: the harbor opens onto the lanes, which reach the free-port
    assert rooms["quench_harbor"]["exits"].get("west") == "the_quench_lanes"
    assert rooms["the_quench_lanes"]["exits"]["west"] == "tidewharf_docks"
    assert (
        rooms["tidewharf_docks"]["exits"]["south"] == "drowned_sunhold_descent"
    )  # down to the deep
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    assert npcs["brine_wight"]["level"] == 18 and npcs["brine_wight"]["tier"] == "elite"
    # the free-port is a real capital: government, trade, and salvage all have a voice
    assert "quenchmere" in npcs["accord_speaker"]["topics"] and "shop" in npcs["merewright_captain"]
    warden = npcs["sunhold_warden"]
    assert warden["level"] == 30 and warden["tier"] == "boss" and warden["lethal"] is True
    assert warden["resistances"] == {
        "WTR": "Resist",
        "LGT": "Weak",
    }  # bring lightning to the drowned
    arc = load_quest(AETHRYN / "quests" / "the_quenchmere.yaml")
    assert arc is not None and arc["steps"][-1]["on_defeat"] == "sunhold_warden"


def test_aethryn_cooling_sea_is_a_dialogue_rich_port_region():
    """A coastal port region west of the waking shore (levels 6-14): the shore opens west along the
    Cooling-Sea to Quench Harbor -- a lived-in fishing town (a harbormaster, a fisher, a dock shop),
    with the Drowned Pilot at a wreck reef, tied together by a coastal questline."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert (
        rooms["the_waking_shore"]["exits"].get("west") == "the_saltstrand"
    )  # a road off the spawn
    assert rooms["the_saltstrand"]["exits"]["west"] == "quench_harbor"
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    # the harbor is a real town: several NPCs, two of them conversational, one keeping a shop
    assert (
        "cooling_sea" in npcs["harbormaster"]["topics"] and "sea" in npcs["quench_fisher"]["topics"]
    )
    assert "shop" in npcs["dock_trader"]
    pilot = npcs["drowned_pilot"]
    assert pilot["level"] == 14 and pilot["tier"] == "boss" and pilot["lethal"] is True
    assert pilot["resistances"] == {"WTR": "Resist", "LGT": "Weak"}  # bring lightning to the water
    arc = load_quest(AETHRYN / "quests" / "the_cooling_sea.yaml")
    assert arc is not None and arc["steps"][-1]["on_defeat"] == "drowned_pilot"


def test_aethryn_ashwastes_is_a_real_mid_game_region_with_an_arc():
    """A whole new mid-game region east of the capital (levels 15-25): the Market Quarter opens onto
    a salt-road into the Ashwastes -- a desert with the Ashborn survivors (a shop + a lore scout), a
    ruin, and the Ash-Colossus at the crater, tied together by its own questline."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert (
        rooms["market_quarter"]["exits"].get("east") == "ashwastes_road"
    )  # a road out of the city
    # the region chains road -> dunes -> (camp / ruin -> crater)
    assert rooms["the_cinder_dunes"]["exits"]["east"] == "the_scoured_ruin"
    assert rooms["the_scoured_ruin"]["exits"]["east"] == "the_glass_crater"
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    assert npcs["ash_jackal"]["level"] == 15  # bands above the reachwood and the cellar
    colossus = npcs["ash_colossus"]
    assert colossus["level"] == 25 and colossus["tier"] == "boss" and colossus["lethal"] is True
    assert colossus["resistances"] == {"ERT": "Resist", "WND": "Weak"}  # an elemental puzzle
    assert "shop" in npcs["ashborn_trader"]  # a third till, mid-game
    assert "ashwastes" in npcs["ashborn_scout"]["topics"]  # lore makes it lived-in
    # a real regional questline: cross the wastes -> meet the Ashborn -> still the Colossus
    arc = load_quest(AETHRYN / "quests" / "the_ashwastes.yaml")
    assert arc is not None and arc["terminal"] == ["stilled"]
    assert arc["steps"][-1]["on_defeat"] == "ash_colossus"


def test_aethryn_reachwood_is_a_real_lateral_region():
    """The coast has horizontal exploration, not just the vertical spine: the Reachwood Edge opens
    east into a forest region (a hollow, a warden's glade, a bramble warren) with level-banded foes,
    a lore-keeping warden, and a mini-boss - an alternative early road to diving the cellar."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert (
        rooms["reachwood_edge"]["exits"].get("east") == "reachwood_hollow"
    )  # no longer a dead-end
    assert set(rooms["reachwood_hollow"]["exits"].values()) >= {
        "wardens_glade",
        "the_bramblewarren",
    }
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    assert npcs["thornback_boar"]["level"] == 5  # a step past the coast wolves
    wight = npcs["bramble_wight"]
    assert wight["level"] == 10 and wight["tier"] == "elite" and wight["attack_element"] == "ERT"
    assert wight["drops"] == ["warden_charm"]  # a real reward off the main spine
    assert "reachwood" in npcs["the_greenwarden"]["topics"]  # a lore-keeper makes it feel lived-in


def test_aethryn_cinder_wight_boss_is_attackable_and_strikes_back():
    wight = load_npcs(AETHRYN / "npcs.yaml")["cinder_wight"]
    assert wight["hp"] == 50
    assert wight["atk"] == 7  # the Cold Cellar boss hits back
    assert wight["level"] == 8 and wight["tier"] == "boss"  # a boss-tier, curve-scaled reward


def test_aethryn_ember_road_climbs_from_the_coast_to_emberreach():
    """The pour past the Kindlands: the Far Reach now opens north onto the Ember-road, which
    climbs through the road and the waystation to the gates of the capital."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert rooms["the_far_reach"]["exits"]["north"] == "emberroad_climb"
    assert rooms["emberroad_climb"]["exits"]["north"] == "wayfarers_rest"
    assert rooms["wayfarers_rest"]["exits"]["north"] == "emberreach_gates"
    assert rooms["emberreach_gates"]["exits"]["north"] == "the_grand_forge"
    # the capital is a hub: the Grand Forge reaches the Orders' Row, the Market, and the Warden Gate
    forge_exits = rooms["the_grand_forge"]["exits"]
    assert {"orders_row", "market_quarter", "warden_gate"} <= set(forge_exits.values())


def test_aethryn_road_foes_are_level_banded_above_the_coast():
    """The Ember-road foes carry levels/tiers well above the coast, so fighting up pays; the city
    stays safe (its service NPCs are peaceful, hp 0)."""
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    stray, reaver = npcs["cinder_stray"], npcs["road_reaver"]
    assert stray["level"] == 10 and stray["tier"] == "normal"
    assert reaver["level"] == 13 and reaver["tier"] == "elite"  # a road threat pays elite (x3)
    assert stray["hp"] > 0 and reaver["hp"] > 0  # combatable
    for keeper in ("emberreach_warden", "grandforge_loremaster", "market_trader", "warden_keeper"):
        assert npcs[keeper]["hp"] == 0, f"{keeper} should be a peaceful city NPC"


def test_aethryn_road_reward_pays_for_the_climb():
    """A coast-fresh Forger fighting the level-13 elite reaver earns far more than a coast wolf: the
    scaled economy rewards closing the gap (fighting up), not farming grays."""
    from parts.world.combat import _reward_amounts
    from parts.world.session import Session

    npcs = load_npcs(AETHRYN / "npcs.yaml")
    session = Session(player_id="climber", location="strayfire_hollow")
    session.level = 6
    reaver_xp = _reward_amounts(session, npcs["road_reaver"])[0]
    wolf_xp = _reward_amounts(session, npcs["reach_wolf"])[0]
    assert reaver_xp > wolf_xp * 5  # the road's elite dwarfs a coast kill


def test_aethryn_wardens_test_opens_the_ascent_to_the_first_coil():
    """Past Emberreach the Warden Gate opens north onto the Wardenmarch, then east onto the
    Forgeward Road's first march - the long flat frontier begins."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert rooms["warden_gate"]["exits"]["north"] == "the_wardenmarch"
    assert rooms["the_wardenmarch"]["exits"]["east"] == "coilfoot_ascent"
    assert rooms["coilfoot_ascent"]["exits"]["east"] == "coil_first_landing"


def test_aethryn_ascent_bosses_are_lethal_and_boss_tier():
    """The Warden Sentinel (the test) and the first road-warden are lethal boss-tier foes well above
    Emberreach - real frontier stakes."""
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    sentinel, wraith = npcs["warden_sentinel"], npcs["gate_forgewraith"]
    assert sentinel["level"] == 17 and sentinel["tier"] == "boss" and sentinel.get("lethal") is True
    assert wraith["level"] == 22 and wraith["tier"] == "boss" and wraith.get("lethal") is True
    assert wraith["level"] > sentinel["level"]  # the first march climbs above the gate test


def test_aethryn_ships_the_descent_the_downward_counterpart_quest():
    """Both roads carry a story: The Descent frames the Cinderdeep as The Ascent frames the Spiral.
    It self-completes from real deeds and ends on stilling the Hollow Smith at the maw."""
    descent = load_quest(AETHRYN / "quests" / "the_descent.yaml")
    assert descent is not None
    assert descent["id"] == "the_descent" and descent["name"] == "The Descent"
    assert descent["terminal"] == ["descended"]
    for step in descent["steps"]:  # every beat fires from a real world deed, never a soft-lock
        assert step.get("on_defeat") or step.get("on_enter") or step.get("on_take")
    last = next(s for s in descent["steps"] if s["to"] == "descended")
    assert last.get("on_defeat") == "hollow_smith" and last.get("effect") == "award_xp"


def test_aethryn_second_coil_climbs_above_the_first():
    """The Road keeps running east: the first waystation opens east into the second march, which
    runs through a roadbridge to its own road-warden, the Ashlord (higher than the first)."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert rooms["coil_first_landing"]["exits"]["east"] == "coil_second_ascent"
    assert rooms["coil_second_ascent"]["exits"]["east"] == "coil_bridgespan"
    assert rooms["coil_bridgespan"]["exits"]["east"] == "coil_second_landing"
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    ashlord, wraith = npcs["gate_ashlord"], npcs["gate_forgewraith"]
    assert ashlord["level"] == 28 and ashlord["tier"] == "boss" and ashlord.get("lethal") is True
    assert ashlord["level"] > wraith["level"]  # each march's road-warden climbs above the last


def test_aethryn_third_coil_climbs_the_spiral_higher():
    """The Road runs on past the Ashlord: the second waystation opens east into the storm-wracked
    third march, whose road-warden (the Stormlord) out-levels every wall before it and drops a
    weapon a tier above the road's blade."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert rooms["coil_second_landing"]["exits"]["east"] == "coil_third_ascent"
    assert rooms["coil_third_ascent"]["exits"]["east"] == "coil_stormreach"
    assert rooms["coil_stormreach"]["exits"]["east"] == "coil_third_landing"
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    stormlord, ashlord = npcs["gate_stormlord"], npcs["gate_ashlord"]
    assert stormlord["level"] == 38 and stormlord["tier"] == "boss"
    assert stormlord["level"] > ashlord["level"]  # each march climbs above the last
    assert "stormlord_edge" in stormlord["drops"]
    edge = load_items(AETHRYN / "items.yaml")["stormlord_edge"]
    assert edge["slot"] == "weapon" and edge["mods"]["ATK"] > 9  # above the reaver blade


def test_aethryn_cinderdeep_is_the_downward_road_from_the_cellar():
    """The coast's OTHER road: down from the cellar hearth into the Cinderdeep, a mid-band depths
    line parallel to the early Ember-road, floored by the Hollow Smith."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert rooms["cellar_hearth"]["exits"]["down"] == "cinderdeep_descent"
    assert rooms["cinderdeep_descent"]["exits"]["down"] == "sunken_forgeworks"
    assert rooms["sunken_forgeworks"]["exits"]["down"] == "cinderdeep_maw"
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    smith = npcs["hollow_smith"]
    assert smith["level"] == 15 and smith["tier"] == "boss" and smith.get("lethal") is True
    # the deep is a mid-band alternative: its foes sit near the early road, not the Spiral's Coils
    assert npcs["deep_crawler"]["level"] == 10 and npcs["cold_vein_lurker"]["tier"] == "elite"


def test_aethryn_boss_drops_are_real_gear_across_every_slot():
    """Felling a boss now yields equippable gear, not just keepsakes: the ladder fills all six
    equipment slots (weapon, body, head, arm, two accessories) with flat stat mods."""
    from parts.world.equipment import SLOTS
    from parts.world.stat_rules import DERIVED_STATS

    items = load_items(AETHRYN / "items.yaml")
    ladder = {
        "cinder_hammer": "weapon",
        "reaver_blade": "weapon",
        "cindershell_plate": "body",
        "wraithlamp_circlet": "head",
        "ashlord_gauntlet": "arm",
        "warden_sigil": "accessory_1",
        "coil_keystone": "accessory_2",
    }
    covered = set()
    for label, slot in ladder.items():
        gear = items[label]
        assert gear["slot"] == slot, f"{label} should equip in {slot}"
        assert gear["mods"], f"{label} must grant stat mods to be worth equipping"
        assert all(target in DERIVED_STATS for target in gear["mods"]), f"{label} mods a real stat"
        covered.add(slot)
    assert covered == set(SLOTS)  # every equipment slot has a drop on the ladder


def test_aethryn_gate_bosses_drop_their_gear():
    """The Coil Gate-bosses drop their signature gear, not only a charm."""
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    assert "wraithlamp_circlet" in npcs["gate_forgewraith"]["drops"]
    assert "ashlord_gauntlet" in npcs["gate_ashlord"]["drops"]
    assert "cindershell_plate" in npcs["hollow_smith"]["drops"]


def test_aethryn_ships_the_relighting_quest_as_data():
    """The flagship's story arc is a seed-shipped workflow, not hardcoded in Python."""
    quest = load_quest(AETHRYN / "quest.yaml")
    assert quest is not None
    assert quest["id"] == "the_relighting" and quest["name"] == "The Relighting"
    assert quest["reward_xp"] == 120
    assert quest["start"] == "offered" and quest["terminal"] == ["done"]
    assert quest["steps"][-1]["effect"] == "award_xp"  # finishing the arc awards XP
    assert quest["steps"][-1]["on_defeat"] == "cinder_wight"  # felling the boss completes it
    triggers = {(k, s[k]) for s in quest["steps"] for k in ("on_take", "on_enter") if k in s}
    assert ("on_enter", "old_reach_bridge") in triggers  # walking onto the bridge reforges it
    assert ("on_enter", "cold_cellar") in triggers  # entering the cellar delves it
    # It is a valid workflow graph (start -> ... -> a terminal state), not just a list.
    from parts.shelf.workflow import Step, build_workflow

    steps = [Step(s["state"], s["event"], s["to"], effect=s.get("effect")) for s in quest["steps"]]
    workflow = build_workflow(
        quest["id"], start=quest["start"], steps=steps, terminal=quest["terminal"]
    )
    assert "done" in workflow.terminal


def test_a_seed_without_a_quest_file_returns_none():
    """A seed that ships no quest.yaml (spiral-ascent) has no arc; the game uses its default."""
    assert load_quest(SPIRAL / "quest.yaml") is None


def test_aethryn_ships_the_broken_bridge_as_a_seed_door():
    """The Old Reach Bridge is a locked, keyless barrier -- reforged by the quest, not a key."""
    doors = load_doors(AETHRYN / "doors.yaml")
    bridge = doors["reach_bridge"]
    assert bridge["blocks"] == ("old_reach_bridge", "north")
    assert bridge["locked"] is True
    assert bridge["key_id"] == ""  # opened by the reforge quest effect, never a key


def test_first_forge_door_is_now_seed_data_not_hardcoded():
    """The former hardcoded oak_door lives in the seed's doors.yaml (world is data)."""
    doors = load_doors(FIRST_FORGE / "doors.yaml")
    assert doors["oak_door"]["blocks"] == ("library", "north")
    assert doors["oak_door"]["key_id"] == "copper_key"


def test_a_seed_without_doors_returns_empty():
    assert load_doors(SPIRAL / "doors.yaml") == {}


def test_load_doors_refuses_a_door_without_a_valid_blocks_pair(tmp_path):
    """A barrier that doesn't say which exit it guards must fail loud, not gate nothing silently."""
    bad = tmp_path / "doors.yaml"
    bad.write_text("gate:\n  name: a gate\n  locked: true\n", encoding="utf-8")  # no blocks
    with pytest.raises(SeedError, match="'blocks' must be"):
        load_doors(bad)


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ("- a\n- b\n", "must be a mapping"),  # a list, not a mapping
        ("id: x\nsteps:\n  - {state: a, event: go, to: b}\n", "quest needs 'start'"),  # no start
        ("id: x\nstart: a\nsteps: []\n", "non-empty list"),  # no steps
        (
            "id: x\nstart: a\nsteps:\n  - {state: a, event: go}\n",
            "each quest step needs",
        ),  # bad step
        (
            "id: x\nstart: a\nsteps:\n  - {state: a, event: g, to: b}\nreward_xp: -5\n",
            "non-negative",
        ),
        (
            "id: x\nstart: a\nsteps:\n  - {state: a, event: g, to: b}\nterminal: nope\n",
            "must be a list",
        ),
    ],
)
def test_load_quest_refuses_a_malformed_arc(tmp_path, body, match):
    """A broken arc must not boot silently: every malformed shape fails loud with a named reason."""
    bad = tmp_path / "quest.yaml"
    bad.write_text(body, encoding="utf-8")
    with pytest.raises(SeedError, match=match):
        load_quest(bad)


def test_load_quest_fills_sensible_defaults(tmp_path):
    """A minimal valid arc names itself from its id and defaults reward/terminal/labels."""
    minimal = tmp_path / "quest.yaml"
    minimal.write_text(
        "id: hidden_vault\nstart: a\nsteps:\n  - {state: a, event: open, to: b}\n", encoding="utf-8"
    )
    quest = load_quest(minimal)
    assert quest is not None
    assert quest["name"] == "Hidden Vault"  # derived from the id
    assert quest["reward_xp"] == 50 and quest["terminal"] == [] and quest["labels"] == {}


def test_spiral_seed_passes_every_loader_gate():
    rooms = load_rooms(SPIRAL / "rooms.yaml")
    assert "spiral_landing" in rooms and "gate_chamber" in rooms
    assert rooms["first_coil"]["exits"]["up"] == "gate_chamber"
    load_items(SPIRAL / "items.yaml")  # gates: valid labels, present location
    load_npcs(SPIRAL / "npcs.yaml")
    jobs = load_jobs(SPIRAL / "jobs.yaml")
    assert "vanguard" in jobs and jobs["pathfinder"]["stats"]["speed"] == 14


def test_spiral_boss_is_attackable_and_strikes_back():
    coilwarden = load_npcs(SPIRAL / "npcs.yaml")["coilwarden"]
    assert coilwarden["hp"] == 60 and coilwarden["xp"] == 200
    assert coilwarden["atk"] == 8  # a real fight: the Gate boss hits back


def test_pop_seed_extracts_and_mutates():
    args = ["play", "--seed", "spiral-ascent"]
    assert _pop_seed(args) == "spiral-ascent"
    assert args == ["play"]


def test_pop_seed_is_none_when_absent():
    args = ["play"]
    assert _pop_seed(args) is None and args == ["play"]


def test_cli_seeds_lists_both_games(capsys: pytest.CaptureFixture[str]):
    assert main(["seeds"]) == 0
    out = capsys.readouterr().out
    assert "first-forge" in out and "spiral-ascent" in out


def test_cli_unknown_seed_is_rejected(capsys: pytest.CaptureFixture[str]):
    assert main(["play", "--seed", "no-such-game"]) == 2
    assert "Unknown seed" in capsys.readouterr().err


def test_seeds_root_honors_env_override(tmp_path, monkeypatch):
    """Installed/containerized deploys keep seeds apart from the package;
    CODEFORGE_SEEDS_ROOT points the loader at them (this is how the Docker
    image finds /app/seeds)."""
    (tmp_path / "solo-game").mkdir()
    (tmp_path / "solo-game" / "rooms.yaml").write_text("start:\n")
    monkeypatch.setenv("CODEFORGE_SEEDS_ROOT", str(tmp_path))
    try:
        importlib.reload(parts.world.seed)
        assert tmp_path == parts.world.seed.SEEDS_ROOT
        assert parts.world.seed.available_seeds() == ["solo-game"]
    finally:
        monkeypatch.delenv("CODEFORGE_SEEDS_ROOT", raising=False)
        importlib.reload(parts.world.seed)  # restore the default root for other tests


def test_aethryn_ships_a_second_quest_the_ascent():
    """The flagship now ships TWO arcs: the Relighting (quest.yaml) and the Ascent (quests/)."""

    ascent = load_quest(AETHRYN / "quests" / "the_ascent.yaml")
    assert ascent is not None
    assert ascent["id"] == "the_ascent" and ascent["name"] == "The Ascent"
    assert ascent["terminal"] == ["ascended"]
    # every beat past the start fires from a real world deed (a natural trigger), never a soft-lock
    for step in ascent["steps"]:
        assert step.get("on_defeat") or step.get("on_enter") or step.get("on_take")
    # the arc spans BOTH built Coils and ends on felling the Second Coil's Ashlord with a reward
    assert {"gate_forgewraith", "gate_ashlord"} <= {s.get("on_defeat") for s in ascent["steps"]}
    last = next(s for s in ascent["steps"] if s["to"] == "ascended")
    assert last.get("on_defeat") == "gate_ashlord" and last.get("effect") == "award_xp"


def test_aethryn_ships_the_summit_capstone_quest():
    """The endgame arc names the procedural far end by its stable labels and ends on felling the
    Sovereign at the far end of the 1-300 Forgeward Road."""
    from parts.world.spiral import SUMMIT_BOSS, SUMMIT_ROOM

    summit = load_quest(AETHRYN / "quests" / "the_summit.yaml")
    assert summit is not None and summit["name"] == "The Forge's Edge"
    assert summit["terminal"] == ["crowned"]
    triggers = {(s.get("on_enter") or s.get("on_defeat")) for s in summit["steps"]}
    assert SUMMIT_ROOM in triggers and SUMMIT_BOSS in triggers  # names the stable far-end labels
    last = next(s for s in summit["steps"] if s["to"] == "crowned")
    assert last.get("on_defeat") == SUMMIT_BOSS and last.get("effect") == "award_xp"
    # the finale pays off the world's framing mystery, not just "you win": the Forge's Edge reveals
    # the First Seed, and the crowned epilogue reforges it (the Unforging answered) - a real ending.
    assert "First Seed" in summit["labels"]["at_the_summit"]
    crowned = summit["labels"]["crowned"]
    assert "SEED REMEMBERS" in crowned and "reforged" in crowned  # the sundering resolved
    assert "Waking Shore" in crowned  # and the cradle-to-crown journey is honoured


def test_aethryn_ships_the_martial_and_precision_job_families():
    """Batch 1 of the 30 switchable callings: the Martial (Duelist/Sentinel/Berserker) and
    Precision (Ranger/Scout/Shadowblade/Saboteur) families, each a distinct stat spread."""
    jobs = load_jobs(AETHRYN / "jobs.yaml")
    for job in ("duelist", "sentinel", "berserker", "ranger", "scout", "shadowblade", "saboteur"):
        assert job in jobs, f"{job} calling missing"
    # family stat identity: the Berserker leans strength, the Scout leans speed
    assert jobs["berserker"]["stats"]["strength"] > jobs["scout"]["stats"]["strength"]
    assert jobs["scout"]["stats"]["speed"] > jobs["berserker"]["stats"]["speed"]
    # each new calling carries a moveset (switchable in/out via the subjob kit)
    from parts.world.seed import load_abilities

    abilities = load_abilities(AETHRYN / "abilities.yaml")
    for job in ("duelist", "berserker", "ranger", "saboteur"):
        assert any(job in a["jobs"] for a in abilities.values()), f"{job} has no abilities"


def test_aethryn_ships_the_arcane_and_divine_job_families():
    """Batch 2 of the 30 callings: the Arcane (Arcanist/Elementalist/Chronomancer/Summoner) and
    Divine (Cleric/Oracle/Templar/Warden) families, magic/wisdom-led."""
    jobs = load_jobs(AETHRYN / "jobs.yaml")
    arcane = ("arcanist", "elementalist", "chronomancer", "summoner")
    divine = ("cleric", "oracle", "templar", "warden")
    for job in arcane + divine:
        assert job in jobs, f"{job} calling missing"
    assert len(jobs) >= 18  # 3 original + Martial/Precision (7) + Arcane/Divine (8)
    # casters lean magic/wisdom; the Arcanist out-magics the Martial Berserker
    assert jobs["arcanist"]["stats"]["magic"] > jobs["berserker"]["stats"]["magic"]
    assert jobs["cleric"]["stats"]["wisdom"] > jobs["berserker"]["stats"]["wisdom"]


def test_aethryn_ships_the_full_thirty_switchable_callings():
    """The AAA-pivot target: 30 distinct callings a player can modulate and swap in/out. Every one
    has a two-move kit, so a subjob genuinely changes your loadout."""
    from parts.world.seed import load_abilities

    jobs = load_jobs(AETHRYN / "jobs.yaml")
    assert len(jobs) == 30, f"expected 30 callings, got {len(jobs)}"
    abilities = load_abilities(AETHRYN / "abilities.yaml")
    armed = {job for a in abilities.values() for job in a["jobs"]}
    assert armed == set(jobs)  # every calling is armed - none is a dead switch
    # each calling carries at least two moves (a signature + a utility)
    from collections import Counter

    per_job = Counter(job for a in abilities.values() for job in a["jobs"])
    assert all(count >= 2 for count in per_job.values()), "a calling has fewer than 2 abilities"
