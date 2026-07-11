"""Test twin for parts/character_view.py -- building a sheet from a live job definition.

Proves the vertical slice: the seeded Engineer becomes a correct CharacterSheet -- player
level separate from job level, the six attributes and the loadout from the job data, HP/MP
from the calling rule, derived stats from the calculator -- and renders without error. An
unknown job is a loud KeyError, not a blank sheet.
"""

from __future__ import annotations

import pytest

from parts.character_view import build_job_sheet
from parts.score_sheet import render_score_sheet


def test_the_engineer_builds_a_correct_sheet() -> None:
    sheet = build_job_sheet("engineer", "Matrym", player_level=1, job_level=1)
    assert sheet.primary_job == "Engineer"
    assert sheet.player_level == 1 and sheet.primary_job_level == 1  # separate axes
    assert sheet.attributes["STR"] == 10 and sheet.attributes["WIS"] == 13
    assert set(sheet.attributes) == {"STR", "SPD", "MAG", "STA", "WIS", "LUCK"}
    assert set(sheet.derived) == {"ATK", "DEF", "EVA", "MAG DEF", "ACC"}
    assert sheet.counter == "Emergency Repair" and sheet.signature == "Forge Overdrive"
    assert sheet.secondary_job is None  # renders as Unassigned


def test_player_level_and_job_level_are_independent() -> None:
    sheet = build_job_sheet("engineer", "Matrym", player_level=12, job_level=9)
    assert sheet.player_level == 12
    assert (
        sheet.primary_job_level == 9
    )  # a high player level with a lower job level, and vice versa


def test_resources_come_from_the_calling_rule() -> None:
    sheet = build_job_sheet("engineer", "Matrym")
    # HP = BASE_HP(20) + stamina(11); MP = BASE_MP(5) + magic(8)
    assert sheet.hp == (31, 31)
    assert sheet.mp == (13, 13)


def test_the_engineer_sheet_renders_without_error() -> None:
    out = render_score_sheet(build_job_sheet("engineer", "Matrym"))
    assert "Job: Engineer (Lv 1)" in out
    assert "Forge Overdrive" in out
    assert all(len(line) <= 70 for line in out.splitlines())


def test_an_unknown_job_is_a_loud_error() -> None:
    with pytest.raises(KeyError, match="no job named"):
        build_job_sheet("necromancer", "Matrym")
