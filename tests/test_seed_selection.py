"""Test twin: a seed is a game. Codeforge boots first-forge or spiral-ascent."""

import importlib

import pytest

import parts.world.seed
from parts.cli import _pop_seed, main
from parts.world.seed import (
    SEEDS_ROOT,
    SeedError,
    available_seeds,
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
    """Past Emberreach the Warden Gate opens north onto the Wardenmarch, then the Great Spiral's
    first Coil - the megadungeon ascent begins."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert rooms["warden_gate"]["exits"]["north"] == "the_wardenmarch"
    assert rooms["the_wardenmarch"]["exits"]["north"] == "coilfoot_ascent"
    assert rooms["coilfoot_ascent"]["exits"]["up"] == "coil_first_landing"


def test_aethryn_ascent_bosses_are_lethal_and_boss_tier():
    """The Warden Sentinel (the test) and the Coil Forgewraith (the first Gate-boss) are lethal
    boss-tier foes well above Emberreach - real ascent stakes."""
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    sentinel, wraith = npcs["warden_sentinel"], npcs["gate_forgewraith"]
    assert sentinel["level"] == 17 and sentinel["tier"] == "boss" and sentinel.get("lethal") is True
    assert wraith["level"] == 22 and wraith["tier"] == "boss" and wraith.get("lethal") is True
    assert wraith["level"] > sentinel["level"]  # the Coil climbs above the gate test


def test_aethryn_second_coil_climbs_above_the_first():
    """The Spiral keeps ascending: the First Coil Landing opens up into the Second Coil, which
    climbs through a bridgespan to its own Gate-boss, the Ashlord (higher than the first)."""
    rooms = load_rooms(AETHRYN / "rooms.yaml")
    assert rooms["coil_first_landing"]["exits"]["up"] == "coil_second_ascent"
    assert rooms["coil_second_ascent"]["exits"]["up"] == "coil_bridgespan"
    assert rooms["coil_bridgespan"]["exits"]["up"] == "coil_second_landing"
    npcs = load_npcs(AETHRYN / "npcs.yaml")
    ashlord, wraith = npcs["gate_ashlord"], npcs["gate_forgewraith"]
    assert ashlord["level"] == 28 and ashlord["tier"] == "boss" and ashlord.get("lethal") is True
    assert ashlord["level"] > wraith["level"]  # each Coil's Gate-boss climbs above the last


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
