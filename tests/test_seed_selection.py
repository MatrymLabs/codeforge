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
    load_zones,
)

FIRST_FORGE = SEEDS_ROOT / "first-forge"

SPIRAL = SEEDS_ROOT / "spiral-ascent"
AETHRYN = SEEDS_ROOT / "aethryn"


def test_both_games_are_installed():
    seeds = available_seeds()
    assert "first-forge" in seeds and "spiral-ascent" in seeds


def test_flagship_aethryn_is_installed():
    assert "aethryn" in available_seeds()


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


def test_aethryn_the_makers_loop_reaches_the_new_content():
    """The maker Jobs can forge the new content, not just the four starter goods: the consumable
    ladder and the Emberhide set are craftable, the grand tiers and the elixir are gated behind
    boss-salvage (hollow_ingot) so crafting progresses with the journey, not ahead of it."""
    from parts.world.seed import load_recipes

    recipes = load_recipes(AETHRYN / "recipes.yaml")
    by_make = {r["makes"]: r for r in recipes.values()}
    # the ladder + starter set are craftable
    for target in (
        "greater_healing_draught",
        "grand_healing_draught",
        "forgefire_elixir",
        "emberhide_hood",
        "emberhide_jerkin",
        "emberhide_wraps",
    ):
        assert target in by_make, f"no recipe forges {target}"
    # the grand tiers + elixir need boss-salvage, not just gathered ember (a progression gate)
    for gated in ("grand_healing_draught", "grand_mana_draught", "forgefire_elixir"):
        assert "hollow_ingot" in by_make[gated]["inputs"], f"{gated} should cost boss-salvage"
    # the greater tiers are cheaper (ember only) -- an accessible mid-game craft
    assert "hollow_ingot" not in by_make["greater_healing_draught"]["inputs"]


def test_aethryn_regional_sets_grant_bonuses_from_real_pieces():
    """Collecting a whole regional set pays off: aethryn ships a gear SET per Reach, each granting a
    flat bonus when all its pieces are worn. Every piece is a real item and every bonus stat is a
    real equip stat (a cross-check, so a set can never bonus off a phantom), and the bonus fires
    only on a COMPLETE set (measured through the gearsets bonus fold)."""
    from parts.world.gearsets import active_set_bonuses
    from parts.world.seed import load_sets

    sets = load_sets(AETHRYN / "sets.yaml")
    assert sets, "the flagship ships no gear sets -- the wide gear pass has no payoff"
    items = set(load_items(AETHRYN / "items.yaml"))
    valid_stats = {"ATK", "DEF", "ACC", "EVA", "MAG DEF"}
    for label, gear_set in sets.items():
        assert len(gear_set["pieces"]) >= 2
        for piece in gear_set["pieces"]:
            assert piece in items, f"set {label} names a phantom piece {piece}"
        for stat in gear_set["bonus"]:
            assert stat in valid_stats, f"set {label} bonuses an unknown stat {stat}"
    # a full set grants its bonus; one piece short grants nothing (all-or-nothing)
    storm = sets["stormward"]
    assert active_set_bonuses(set(storm["pieces"]), sets) == storm["bonus"]
    assert active_set_bonuses(set(storm["pieces"][:-1]), sets) == {}


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


def test_a_seed_without_a_quest_file_returns_none():
    """A seed that ships no quest.yaml (spiral-ascent) has no arc; the game uses its default."""
    assert load_quest(SPIRAL / "quest.yaml") is None


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


# --- The canonical map world (Pictures/Map.png): 14 zones, spawn in Veridia -------------------
_MAP_ZONES = {
    "veridia": (1, 30),
    "duskwood_vale": (20, 50),
    "caeloria": (30, 60),
    "eldryn_forest": (50, 80),
    "frostspire_peaks": (60, 90),
    "zhaar_desert": (80, 130),
    "xilnath_jungle": (90, 150),
    "thalorin": (100, 140),
    "ashen_wastes": (120, 170),
    "korvash_highlands": (150, 200),
    "shattered_isles": (180, 230),
    "skyward_spires": (200, 250),
    "the_deepreach": (100, 250),
    "the_voidscar": (250, 300),
}


def test_aethryn_spawns_in_veridia_the_starter_zone():
    """The map's starter region is the spawn: the first room in rooms.yaml is Veridia."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert next(iter(rooms)) == "veridia"
    assert rooms["veridia"]["name"] == "Veridia"


def test_aethryn_all_fourteen_map_zones_exist_as_rooms():
    """Every named zone on the canonical map is an implemented hub room."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    missing = [z for z in _MAP_ZONES if z not in rooms]
    assert not missing, f"map zones not implemented as rooms: {missing}"


def test_aethryn_zones_carry_the_maps_level_bands():
    """Each zone's metadata area carries exactly the level band the map prints for it."""
    rooms = set(load_rooms(AETHRYN / "rooms.yaml"))
    zones = load_zones(AETHRYN / "zones.yaml", rooms)
    for zid, (lo, hi) in _MAP_ZONES.items():
        z = zones[f"{zid}_zone"]
        assert (z["level_min"], z["level_max"]) == (lo, hi), f"{zid} band wrong"


def test_aethryn_map_world_is_fully_connected_from_veridia():
    """A player can begin in Veridia and physically reach every hand-authored place on the map."""
    from collections import deque

    rooms = load_rooms(AETHRYN / "rooms.yaml")
    seen, q = {"veridia"}, deque(["veridia"])
    while q:
        for dest in rooms[q.popleft()]["exits"].values():
            if dest in rooms and dest not in seen:
                seen.add(dest)
                q.append(dest)
    assert set(rooms) <= seen, f"unreachable map rooms: {sorted(set(rooms) - seen)[:8]}"


def test_aethryn_no_map_room_ships_empty():
    """Every hand-authored map room has a resident or a guardian -- no empty places."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    occupied = {n["location"] for n in npcs.values()}
    empty = set(rooms) - occupied
    assert not empty, f"map rooms with no NPC: {sorted(empty)[:8]}"


def test_aethryn_key_settlements_and_dungeons_are_implemented():
    """A sampling of the map's named settlements and dungeons exist as explorable rooms."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    for place in (
        "greenhold",
        "caeloria_city",
        "sunscar_city",
        "moltenhold",
        "aurelian_city",
        "deepforge_city",
        "the_black_hollow",
        "the_obsidian_pit",
        "netharions_throne",
        "the_crystal_labyrinth",
        "the_great_tree",
        "the_maelstrom_rise",
    ):
        assert place in rooms, f"map place not implemented: {place}"


def test_aethryn_dungeons_are_guarded_by_a_boss():
    """Each dungeon room on the map holds a boss-tier guardian foe."""
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    for dungeon in ("the_black_hollow", "the_obsidian_pit", "netharions_throne"):
        guards = [n for n in npcs.values() if n["location"] == dungeon]
        assert guards and any(n.get("tier") == "boss" for n in guards), f"{dungeon} has no boss"


def test_aethryn_map_zones_span_levels_1_to_300():
    """The map's zones cover the whole 1-300 progression with no band left uncovered."""
    covered = set()
    for lo, hi in _MAP_ZONES.values():
        covered.update(range(lo, hi + 1))
    assert covered.issuperset(range(1, 301)), "a level band is uncovered by the map's zones"
