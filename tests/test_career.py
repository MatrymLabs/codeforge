"""Test twin for parts/career.py -- the Career Evidence Sign.

The headline test is the VeritasGate one: the shipped board never marks a skill `proven`
or `partial` while citing a proof path that does not exist. Acceptance (views render) and
refusal (malformed matrix fails loud) are pinned too.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from parts.career import (
    CareerError,
    career,
    load_board,
    render_gaps,
    render_resume,
    unproven_claims,
)


def test_the_shipped_board_loads() -> None:
    board = load_board()
    assert board["title"] == "Career Evidence Sign"
    assert {lvl["level"] for lvl in board["levels"]} == {"entry", "intermediate", "advanced"}


def test_no_proven_or_partial_skill_cites_a_missing_artifact() -> None:
    # VeritasGate: every claim of evidence must point to a real file/dir on disk.
    board = load_board()
    violations = unproven_claims(board)
    assert not violations, "Career board overclaims (proof path does not exist):\n" + "\n".join(
        violations
    )


def test_missing_skills_have_no_fabricated_proof() -> None:
    # A 'missing' skill must NOT carry proof paths -- that would be dishonest.
    board = load_board()
    for lvl in board["levels"]:
        for s in lvl["skills"]:
            if s["status"] == "missing":
                assert s["repo_proof"] == [], f"{s['skill_id']} is missing but cites proof"


def test_a_malformed_matrix_fails_loud(tmp_path: Path) -> None:
    bad = tmp_path / "m.json"
    bad.write_text("{ not json")
    with pytest.raises(CareerError, match="unreadable"):
        load_board(bad)


def test_a_matrix_without_career_board_fails_loud(tmp_path: Path) -> None:
    bad = tmp_path / "m.json"
    bad.write_text(json.dumps({"nope": {}}))
    with pytest.raises(CareerError, match="missing 'career_board'"):
        load_board(bad)


def test_a_skill_missing_a_required_field_fails_loud(tmp_path: Path) -> None:
    bad = tmp_path / "m.json"
    bad.write_text(
        json.dumps(
            {"career_board": {"levels": [{"level": "entry", "skills": [{"skill_id": "x"}]}]}}
        )
    )
    with pytest.raises(CareerError, match="missing"):
        load_board(bad)


def test_gaps_view_surfaces_the_real_gaps() -> None:
    out = render_gaps()
    assert "GAPS" in out
    # runbook/postmortem is a known 'missing' item — it must appear as a gap
    assert "runbook" in out.lower() or "postmortem" in out.lower()


def test_resume_is_generated_from_proven_skills() -> None:
    out = render_resume()
    assert "RESUME TRANSLATION" in out
    assert "Readiness, never certification" in out  # no overclaiming


def test_career_dispatch_routes_each_view() -> None:
    assert "READINESS AT A GLANCE" in career("")
    assert "GAPS" in career("gaps")
    assert "RESUME" in career("resume")
    assert "ENTRY-LEVEL READINESS" in career("role entry")
    assert "PROOF PATHS" in career("evidence")
    assert "Unknown career view" in career("nonsense")


def test_career_is_reachable_through_the_engine_tick() -> None:
    # A feature isn't wired until handle_command proves a player can reach it.
    from forge import handle_command
    from parts.session import Session

    out = handle_command(Session(player_id="career_tick"), "career gaps")
    assert "GAPS" in out
