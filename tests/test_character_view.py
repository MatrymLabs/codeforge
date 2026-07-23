"""Test twin for parts/world/character_view.py -- building a sheet from a live job definition.

Proves the vertical slice: the seeded Engineer becomes a correct CharacterSheet -- player
level separate from job level, the six attributes and the loadout from the job data, HP/MP
from the calling rule, derived stats from the calculator -- and renders without error. An
unknown job is a loud KeyError, not a blank sheet.
"""

from __future__ import annotations

import pytest

from parts.world.character_view import build_job_sheet, sheet_from_session
from parts.world.job_progress import JobProgress
from parts.world.jobs import bind_calling
from parts.world.score_sheet import render_score_sheet
from parts.world.session import Session


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


def test_sheet_from_a_live_session_reads_real_progress() -> None:
    s = Session(player_id="matrym", level=12, xp=4820)
    bind_calling(s, "engineer")
    s.job_progress["engineer"] = JobProgress("engineer", job_level=9, jp=1150, tp=340)
    sheet = sheet_from_session(s)
    assert sheet is not None
    assert sheet.player_level == 12 and sheet.primary_job_level == 9  # separate axes, live
    assert sheet.jp == 1150
    assert sheet.tp_rows[0].current == 340
    assert sheet.attributes["WIS"] == 13


def test_a_session_with_no_calling_has_no_sheet() -> None:
    assert sheet_from_session(Session(player_id="matrym")) is None


def test_the_sheet_shows_declared_resistances_and_normal_otherwise() -> None:
    from parts.world.character_view import sheet_from_session
    from parts.world.jobs import bind_calling
    from parts.world.session import Session

    s = Session(player_id="matrym")
    bind_calling(s, "engineer")
    sheet = sheet_from_session(s)
    assert sheet is not None
    assert sheet.resistances["LGT"] == "Weak"  # declared
    assert sheet.resistances["ERT"] == "Resist"
    assert sheet.resistances["FIR"] == "Normal"  # undeclared -> Normal, never unknown
    assert len(sheet.resistances) == 10  # all ten elements present


def test_milestone_perks_raise_derived_stats_when_unlocked() -> None:
    from parts.world.character_view import TP_MILESTONE, perks_unlocked, sheet_from_session
    from parts.world.job_progress import JobProgress
    from parts.world.jobs import JOBS, bind_calling
    from parts.world.session import Session

    s = Session(player_id="matrym")
    bind_calling(s, "engineer")
    base = sheet_from_session(s)
    assert base is not None
    base_def = base.derived["DEF"]
    s.job_progress["engineer"] = JobProgress("engineer", tp=TP_MILESTONE)  # unlock perk 1
    assert len(perks_unlocked(JOBS["engineer"], TP_MILESTONE)) == 1
    boosted = sheet_from_session(s)
    assert boosted is not None
    assert boosted.derived["DEF"] == base_def + 4  # Reinforced Frame +4 DEF
