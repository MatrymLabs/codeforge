"""Test twin for parts/cast.py -- the seed→cast planner.

Acceptance (the real templates plan a READY cast) and refusal (unknown/malformed template,
missing starter pack → loud CastError or BLOCKED) are both pinned, plus the honesty rules:
the plan reports a whole-engine copy, never a false à-la-carte module list, and it writes
nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from parts.cast import (
    BLOCKED,
    PLANNED,
    READY,
    CastError,
    available_templates,
    load_template,
    main,
    plan_cast,
    read_manifest,
    render_plan,
    write_manifest,
)


def test_the_shipped_templates_are_on_the_shelf() -> None:
    templates = available_templates()
    assert "blank_mud" in templates
    assert "fantasy_mud" in templates


def test_a_real_template_loads_with_its_required_keys() -> None:
    tpl = load_template("fantasy_mud")
    assert tpl["template_id"] == "fantasy_mud"
    assert tpl["starter_seed_pack"] == "sword-art-online"
    assert tpl["engine_strategy"] == "vendored-whole"


def test_an_unknown_template_fails_loud() -> None:
    with pytest.raises(CastError, match="unknown template"):
        load_template("no_such_template")


def test_a_malformed_template_fails_loud(tmp_path: Path) -> None:
    d = tmp_path / "seed_templates" / "broken"
    d.mkdir(parents=True)
    (d / "template_manifest.json").write_text("{ not valid json")
    with pytest.raises(CastError, match="malformed"):
        load_template("broken", root=tmp_path / "seed_templates")


def test_a_template_missing_a_required_key_fails_loud(tmp_path: Path) -> None:
    d = tmp_path / "seed_templates" / "thin"
    d.mkdir(parents=True)
    (d / "template_manifest.json").write_text(json.dumps({"template_id": "thin"}))
    with pytest.raises(CastError, match="missing required key"):
        load_template("thin", root=tmp_path / "seed_templates")


def test_planning_a_real_cast_is_ready_and_honest() -> None:
    plan = plan_cast("fantasy_mud", "Aethris", commit="abc1234")
    assert plan.verdict == READY
    m = plan.manifest
    assert m.status == PLANNED  # dry run - nothing generated
    assert m.engine_strategy == "vendored-whole"
    assert m.codeforge_commit == "abc1234"
    assert m.seed_id == "CAST-AETHRIS-001"
    # honesty: the engine is copied WHOLE, never claimed as selectable modules
    assert any("WHOLE" in c or "whole" in c for c in m.copied_categories)
    assert any("module-level selection" in lim for lim in m.known_limitations)
    # secrets/state are in the never-copy set
    assert any("secrets" in e for e in m.excluded_categories)
    assert any("runtime state" in e for e in m.excluded_categories)


def test_planning_blocks_when_the_starter_pack_is_missing(tmp_path: Path) -> None:
    # A template whose starter pack is not installed must BLOCK, not silently proceed.
    (tmp_path / "seed_templates" / "ghost").mkdir(parents=True)
    (tmp_path / "seed_templates" / "ghost" / "template_manifest.json").write_text(
        json.dumps(
            {
                "template_id": "ghost",
                "starter_seed_pack": "not-installed",
                "engine_strategy": "vendored-whole",
            }
        )
    )
    (tmp_path / "seeds").mkdir()  # no 'not-installed' pack inside
    plan = plan_cast("ghost", "Nowhere", root=tmp_path)
    assert plan.verdict == BLOCKED
    assert any("not installed" in w for w in plan.warnings)


def test_the_plan_writes_nothing(tmp_path: Path) -> None:
    before = set(p.name for p in tmp_path.iterdir())
    plan_cast("blank_mud", "Sandbox")
    after = set(p.name for p in tmp_path.iterdir())
    assert before == after  # a dry run touches nothing on disk


def test_manifest_round_trips_through_json(tmp_path: Path) -> None:
    original = plan_cast("blank_mud", "RoundTrip", commit="deadbee").manifest
    path = tmp_path / "cast_manifest.json"
    write_manifest(original, path)
    restored = read_manifest(path)
    assert restored == original


def test_reading_a_broken_manifest_fails_loud(tmp_path: Path) -> None:
    bad = tmp_path / "cast_manifest.json"
    bad.write_text("{ broken")
    with pytest.raises(CastError, match="unreadable"):
        read_manifest(bad)


def test_render_plan_shows_the_verdict_and_sections() -> None:
    out = render_plan(plan_cast("fantasy_mud", "Aethris"))
    assert "Cast plan - Aethris" in out
    assert "WOULD COPY:" in out
    assert "WOULD NEVER COPY:" in out
    assert "vendored-whole" in out


def test_cli_main_exits_zero_on_a_ready_plan(capsys) -> None:
    code = main(["fantasy_mud", "Aethris", "abc1234"])
    assert code == 0
    assert "Cast plan" in capsys.readouterr().out


def test_cli_main_usage_error_without_args(capsys) -> None:
    assert main([]) == 2
    assert "usage" in capsys.readouterr().err
