"""Test twin for parts/score_sheet.py -- the character score sheet.

Per the spec's testing guidance: ONE golden snapshot pins the format (regression detection),
focused field tests pin the content, alignment tests pin the frame, and a battery of edge
cases proves the renderer survives real data (long names, missing guild, no secondary job,
absent MP, unknown resistance, empty slots, maximum-width equipment) without breaking the
frame or crashing.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from parts.score_sheet import (
    CharacterSheet,
    EquipmentLoadout,
    JobTP,
    render_score_sheet,
    sheet_from_mapping,
)

_FIX = Path(__file__).parent / "fixtures" / "characters"


def _matrym() -> CharacterSheet:
    data = json.loads((_FIX / "matrym_engineer.json").read_text(encoding="utf-8"))
    return sheet_from_mapping(data)


def _lines(sheet: CharacterSheet) -> list[str]:
    return render_score_sheet(sheet).splitlines()


# --- golden snapshot (format regression) ----------------------------------------
def test_matrym_matches_the_golden_sheet() -> None:
    golden = (_FIX / "matrym_engineer_score.txt").read_text(encoding="utf-8").rstrip("\n")
    assert render_score_sheet(_matrym()) == golden


# --- alignment / frame ----------------------------------------------------------
def test_no_line_ever_exceeds_the_frame_width() -> None:
    assert all(len(line) <= 70 for line in _lines(_matrym()))


def test_the_frame_lines_are_exactly_the_frame_width() -> None:
    lines = _lines(_matrym())
    assert lines[0] == "=" * 70 and lines[-1] == "=" * 70


def test_the_stat_dividers_split_at_a_fixed_column() -> None:
    dividers = [ln for ln in _lines(_matrym()) if ln.startswith("-")]
    assert dividers and all(ln[28] == "+" and len(ln) == 70 for ln in dividers)


# --- focused field content ------------------------------------------------------
def test_identity_level_and_job_appear_in_the_header() -> None:
    header = _lines(_matrym())[1]
    assert "Matrym" in header
    assert "PLvl 12" in header
    assert "Job: Engineer (Lv 9)" in header  # player level is separate from job level


def test_resources_and_progression_render() -> None:
    out = render_score_sheet(_matrym())
    assert "HP   142 / 142" in out
    assert "MP   38 / 38" in out
    assert "XP   4,820" in out and "JP   1,150" in out  # thousands separators


def test_every_attribute_and_derived_stat_renders() -> None:
    out = render_score_sheet(_matrym())
    for code, val in (("STR", "18"), ("SPD", "22"), ("WIS", "7"), ("LUCK", "16")):
        assert code in out and val in out
    for code in ("ATK", "DEF", "EVA", "MAG DEF", "ACC"):
        assert code in out


def test_the_job_loadout_and_tp_rows_render() -> None:
    out = render_score_sheet(_matrym())
    for ability in ("Emergency Repair", "Field Deployment", "Systems Thinking", "Forge Overdrive"):
        assert ability in out
    assert "TP (Engineer)   340 / 500" in out
    assert "TP (Secondary)   90 / 500" in out  # separate TP totals per job


# --- edge cases -----------------------------------------------------------------
def test_a_missing_secondary_job_reads_unassigned() -> None:
    assert "Secondary Job  Unassigned" in render_score_sheet(_matrym())


def test_absent_mp_omits_the_mp_line() -> None:
    out = render_score_sheet(replace(_matrym(), mp=None))
    assert "MP " not in out


def test_a_missing_guild_is_omitted_cleanly() -> None:
    out = render_score_sheet(replace(_matrym(), guild=None))
    assert "Guild" not in out
    assert all(len(line) <= 70 for line in out.splitlines())


def test_an_unknown_resistance_renders_as_a_question_mark() -> None:
    out = render_score_sheet(replace(_matrym(), resistances={"FIR": "Normal"}))
    assert "ICE:?" in out  # unknown -> "?", never a crash


def test_an_empty_accessory_slot_is_skipped() -> None:
    bare = replace(_matrym(), equipment=EquipmentLoadout(weapon="Wrench"))
    out = render_score_sheet(bare)
    assert "Weapon : Wrench" in out
    assert "Accessory 1" not in out


def test_a_long_name_does_not_break_the_frame() -> None:
    out = render_score_sheet(replace(_matrym(), display_name="Bartholomew" * 8))
    assert all(len(line) <= 70 for line in out.splitlines())


def test_a_long_job_name_does_not_break_the_frame() -> None:
    out = render_score_sheet(replace(_matrym(), primary_job="Grand Master Field Engineer" * 3))
    assert all(len(line) <= 70 for line in out.splitlines())


def test_maximum_width_equipment_names_stay_inside_the_frame() -> None:
    huge = EquipmentLoadout(weapon="X" * 200, body="Y" * 200, accessory_1="Z" * 200)
    out = render_score_sheet(replace(_matrym(), equipment=huge))
    assert all(len(line) <= 70 for line in out.splitlines())


def test_multiple_tp_records_all_render() -> None:
    rows = (JobTP("Engineer", 1, 2), JobTP("Scholar", 3, 4), JobTP("Vanguard", 5, 6))
    out = render_score_sheet(replace(_matrym(), tp_rows=rows))
    assert "TP (Scholar)" in out and "TP (Vanguard)" in out


# --- refusal --------------------------------------------------------------------
def test_an_unknown_display_mode_is_refused_loud() -> None:
    with pytest.raises(ValueError, match="unknown display_mode"):
        render_score_sheet(_matrym(), display_mode="hologram")


# --- display modes --------------------------------------------------------------
def test_every_framed_mode_renders_within_the_frame() -> None:
    # developer is a raw dump, not a framed sheet, so it is exempt from the 70-col frame.
    for mode in ("standard", "compact", "jobs", "equipment", "resistances"):
        out = render_score_sheet(_matrym(), display_mode=mode)
        assert all(len(line) <= 70 for line in out.splitlines()), mode


def test_the_developer_view_renders() -> None:
    assert render_score_sheet(_matrym(), display_mode="developer").strip()


def test_compact_drops_the_derived_and_resistance_blocks() -> None:
    out = render_score_sheet(_matrym(), display_mode="compact")
    assert "MAG DEF" not in out and "FIR:" not in out
    assert "STR" in out  # but keeps identity + core stats


def test_resistances_mode_shows_the_grid() -> None:
    out = render_score_sheet(_matrym(), display_mode="resistances")
    assert "LGT:Weak" in out and "PSN:Resist" in out


def test_developer_mode_marks_prototype_formulas() -> None:
    out = render_score_sheet(_matrym(), display_mode="developer")
    assert "DEVELOPER VIEW" in out and "prototype_balance_only" in out


def test_jobs_mode_lists_unlocked_jobs() -> None:
    from parts.score_sheet import JobLine

    sheet = replace(_matrym(), jobs=(JobLine("Engineer", 9, 1150, 340),), primary_job="Engineer")
    out = render_score_sheet(sheet, display_mode="jobs")
    assert "Engineer" in out and "Lv 9" in out and "(active)" in out
