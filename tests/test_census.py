"""Test twin for tools/census.py -- the reproducible world/engine census the scorecard cites.

Acceptance: the census reads the LIVE seed and reports the real, non-zero content it declares.
Refusal: this pins the exact failure that slipped by silently -- after the section-2 restructure
moved the seed to content/seeds/ and retired parts/, census kept reading the old paths and reported
ALL ZEROS, and the scorecard's "Measured" counts drifted. A tool whose whole job is to measure must
fail loud when it is measuring nothing, so every section below asserts it counts a real world.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tools import census


def test_seed_path_points_at_the_live_world():
    # The seed moved to content/seeds/aethryn in the restructure; a stale path silently reads zero.
    assert census.SEED.is_dir(), f"census seed path is not a directory: {census.SEED}"
    assert (census.SEED / "zones.yaml").is_file()


def test_world_scale_counts_a_real_world():
    scale = census.world_scale()
    assert scale["authored_rooms"] > 0
    assert scale["wildlands_regions"] > 0
    assert scale["total_rooms_default_scale"] > scale["authored_rooms"]  # generators add rooms


def test_seed_counts_match_the_declared_content():
    # Structural counts the world declares; zero here means census reads the wrong path.
    zones = census._count("zones.yaml")
    dungeons = census._count("dungeons.yaml")
    quests = census._count_dir("quests")
    assert zones >= 14
    assert dungeons >= 14
    assert quests >= 14  # authored quests live in the quests/ DIR, not the legacy quest.yaml


def test_population_and_items_are_non_zero():
    assert census.population()["authored_npcs"] > 0
    assert census.items()["total_items"] > 0


def test_engine_metrics_read_the_restructured_layout():
    # parts/ was retired into kernel/ + adapters/; a stale parts/ path reports zero modules.
    eng = census.engine()
    assert eng["engine_modules"] > 0
    assert eng["world_modules"] > 0
    assert eng["engine_python_loc"] > 0


def test_command_reports_assembled_aethryn_runtime_not_only_source_counts():
    """The scorecard must measure what boots, including generated world content."""
    repo = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env.pop("FORGE_SEED", None)
    env["PYTHONPATH"] = str(repo)
    result = subprocess.run(
        [sys.executable, "tools/census.py"],
        cwd=repo,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "[runtime]" in result.stdout
    assert "seed: aethryn" in result.stdout
    assert "rooms: 28745" in result.stdout
    assert "npcs: 27961" in result.stdout
    assert "items: 3432" in result.stdout
    assert "quests: 3394" in result.stdout
    assert "runtime_zones: 56" in result.stdout
    assert "field_zones: 14" in result.stdout
    assert "underground_zones: 28" in result.stdout
