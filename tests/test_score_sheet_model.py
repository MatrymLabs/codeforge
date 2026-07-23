"""Test twin for parts/world/score_sheet_model.py -- the score-sheet view model (data only)."""

import dataclasses

import pytest

from parts.world.score_sheet_model import (
    ATTR_ORDER,
    DERIVED_ORDER,
    RESIST_ORDER,
    CharacterSheet,
    EquipmentLoadout,
    JobLine,
    JobTP,
    sheet_from_mapping,
)

_RAW = {
    "display_name": "Ada",
    "player_level": 3,
    "current_xp": 120,
    "next_level_xp": 200,
    "hp": [32, 32],
    "mp": [9, 9],
    "jp": 40,
    "race": "Human",
    "primary_job": "Engineer",
    "primary_job_level": 2,
    "counter": "Riposte",
    "movement": "Stride",
    "inherent": "Tinker",
    "signature": "Overclock",
    "attributes": {"STR": 5, "MAG": 3},
    "derived": {"ATK": 12},
    "equipment": {"weapon": "Wrench"},
    "resistances": {"FIR": "Weak"},
    "tp_rows": [{"label": "Engineer", "current": 340, "required": 500}],
}


def test_sheet_from_mapping_builds_the_view_model():
    sheet = sheet_from_mapping(_RAW)
    assert isinstance(sheet, CharacterSheet)
    assert sheet.display_name == "Ada"
    assert sheet.hp == (32, 32) and sheet.mp == (9, 9)
    assert sheet.attributes == {"STR": 5, "MAG": 3}
    assert sheet.equipment == EquipmentLoadout(weapon="Wrench")
    assert sheet.tp_rows == (JobTP("Engineer", 340, 500),)


def test_optional_fields_are_honestly_optional():
    raw = {**_RAW, "mp": None, "guild": None, "secondary_job": None}
    sheet = sheet_from_mapping(raw)
    assert sheet.mp is None and sheet.guild is None and sheet.secondary_job is None
    assert sheet.power is None  # absent when not supplied


def test_coercion_normalizes_types():
    raw = {**_RAW, "player_level": "3", "attributes": {"STR": "5"}}
    sheet = sheet_from_mapping(raw)
    assert sheet.player_level == 3 and sheet.attributes == {"STR": 5}


def test_a_missing_required_key_fails_loud():
    raw = {k: v for k, v in _RAW.items() if k != "display_name"}
    with pytest.raises(KeyError):
        sheet_from_mapping(raw)


def test_the_view_model_is_frozen():
    sheet = sheet_from_mapping(_RAW)
    with pytest.raises(dataclasses.FrozenInstanceError):
        sheet.display_name = "Grace"


def test_the_canonical_orders_are_stable():
    assert ATTR_ORDER == ("STR", "SPD", "MAG", "STA", "WIS", "LUCK")
    assert len(RESIST_ORDER) == 10 and "FIR" in RESIST_ORDER
    assert DERIVED_ORDER[0] == "ATK"


def test_job_line_and_defaults():
    assert JobLine("Engineer", 9, 1150, 340).level == 9
    assert EquipmentLoadout().weapon == ""  # bare slot
