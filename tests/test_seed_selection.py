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
    assert wight["hp"] == 50 and wight["xp"] == 180
    assert wight["atk"] == 7  # the Cold Cellar boss hits back


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
    assert ("on_take", "first_ember") in triggers  # picking up the ember relights it
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
