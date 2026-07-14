"""Test twin: a seed is a game. Codeforge boots first-forge or spiral-ascent."""

import importlib

import pytest

import parts.seed
from parts.cli import _pop_seed, main
from parts.seed import SEEDS_ROOT, available_seeds, load_items, load_jobs, load_npcs, load_rooms

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
        assert item["location"].split(":")[-1] in rooms, f"item {label} floats nowhere"
    for label, npc in load_npcs(AETHRYN / "npcs.yaml").items():
        assert npc["location"].split(":")[-1] in rooms, f"npc {label} floats nowhere"


def test_aethryn_cinder_wight_boss_is_attackable_and_strikes_back():
    wight = load_npcs(AETHRYN / "npcs.yaml")["cinder_wight"]
    assert wight["hp"] == 50 and wight["xp"] == 180
    assert wight["atk"] == 7  # the Cold Cellar boss hits back


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
        importlib.reload(parts.seed)
        assert tmp_path == parts.seed.SEEDS_ROOT
        assert parts.seed.available_seeds() == ["solo-game"]
    finally:
        monkeypatch.delenv("CODEFORGE_SEEDS_ROOT", raising=False)
        importlib.reload(parts.seed)  # restore the default root for other tests
