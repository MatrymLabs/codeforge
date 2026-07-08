"""Test twin: a seed is a game. Codeforge boots first-forge or sword-art-online."""

import importlib

import pytest

import parts.seed
from parts.cli import _pop_seed, main
from parts.seed import SEEDS_ROOT, available_seeds, load_items, load_jobs, load_npcs, load_rooms

SAO = SEEDS_ROOT / "sword-art-online"


def test_both_games_are_installed():
    seeds = available_seeds()
    assert "first-forge" in seeds and "sword-art-online" in seeds


def test_sao_seed_passes_every_loader_gate():
    rooms = load_rooms(SAO / "rooms.yaml")
    assert "town_of_beginnings" in rooms and "boss_chamber" in rooms
    assert rooms["floor_labyrinth"]["exits"]["up"] == "boss_chamber"
    load_items(SAO / "items.yaml")  # gates: valid labels, present location
    load_npcs(SAO / "npcs.yaml")
    jobs = load_jobs(SAO / "jobs.yaml")
    assert "swordsman" in jobs and jobs["beater"]["stats"]["agility"] == 14


def test_sao_boss_is_attackable():
    illfang = load_npcs(SAO / "npcs.yaml")["illfang"]
    assert illfang["hp"] == 60 and illfang["xp"] == 200


def test_pop_seed_extracts_and_mutates():
    args = ["play", "--seed", "sword-art-online"]
    assert _pop_seed(args) == "sword-art-online"
    assert args == ["play"]


def test_pop_seed_is_none_when_absent():
    args = ["play"]
    assert _pop_seed(args) is None and args == ["play"]


def test_cli_seeds_lists_both_games(capsys: pytest.CaptureFixture[str]):
    assert main(["seeds"]) == 0
    out = capsys.readouterr().out
    assert "first-forge" in out and "sword-art-online" in out


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
