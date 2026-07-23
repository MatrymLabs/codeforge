"""Test twin for parts/pioneer.py -- Pioneer Mode surfaced in the MUD."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from parts.pioneer import (
    PioneerError,
    load_ladder,
    pioneer,
    render_experiments,
    render_plan,
    render_risks,
)


def test_the_shipped_risk_ladder_loads_with_five_levels() -> None:
    lad = load_ladder()
    levels = [lv["level"] for lv in lad["levels"]]
    assert levels == [1, 2, 3, 4, 5]


def test_a_malformed_ladder_fails_loud(tmp_path: Path) -> None:
    bad = tmp_path / "l.json"
    bad.write_text("{ not json")
    with pytest.raises(PioneerError, match="unreadable"):
        load_ladder(bad)


def test_a_ladder_without_the_key_fails_loud(tmp_path: Path) -> None:
    bad = tmp_path / "l.json"
    bad.write_text(json.dumps({"nope": {}}))
    with pytest.raises(PioneerError, match="missing"):
        load_ladder(bad)


def test_risks_view_shows_the_blocked_level() -> None:
    out = render_risks()
    assert "L5 Blocked" in out
    assert "never" in out


def test_plan_view_is_the_constraint_review_template() -> None:
    out = render_plan()
    assert "Constraint Review" in out
    assert "Rollback plan:" in out


def test_experiments_view_lists_the_filed_honest_split() -> None:
    # The real first experiment must be discoverable by the command.
    out = render_experiments()
    assert "honest-gpu-split" in out
    assert "GPU-less host" in out or "GPU performance package" in out


def test_experiments_view_is_honest_when_empty(tmp_path: Path) -> None:
    out = render_experiments(root=tmp_path)
    assert "none filed yet" in out


def test_pioneer_dispatch_routes_each_view() -> None:
    assert "PIONEER MODE" in pioneer("")
    assert "risk ladder" in pioneer("risks")
    assert "Constraint Review" in pioneer("plan")
    assert "filed experiments" in pioneer("experiments")
    assert "Unknown pioneer view" in pioneer("nonsense")


def test_pioneer_is_reachable_through_the_engine_tick() -> None:
    from forge import handle_command
    from parts.world.session import Session

    out = handle_command(Session(player_id="pio"), "pioneer risks")
    assert "risk ladder" in out
