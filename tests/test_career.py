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
    ownership_gaps,
    render_claim,
    render_gaps,
    render_ownership,
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


def test_no_ownership_claim_outruns_its_record() -> None:
    # KeelGate: a skill claiming defendable ownership (level >= 4) must cite a real keel
    # record on disk. The shipped board must have zero violations, so the human-keel claim
    # cannot quietly overinflate the way an evidence claim cannot (see unproven_claims).
    board = load_board()
    violations = ownership_gaps(board)
    assert not violations, "Ownership claim outruns its record:\n" + "\n".join(violations)


def test_undeclared_ownership_is_honest_not_a_violation() -> None:
    # Ownership is a second, optional axis: most skills carry no `ownership` block yet, and
    # that undeclared state is honest (a gap to claim), never a KeelGate failure.
    board = load_board()
    skills = [s for lvl in board["levels"] for s in lvl["skills"]]
    assert any("ownership" not in s for s in skills), "expected some undeclared skills"
    assert any("ownership" in s for s in skills), "expected at least one seeded ownership claim"
    assert ownership_gaps(board) == []


def test_ownership_view_shows_declared_and_undeclared() -> None:
    out = render_ownership()
    assert "OWNERSHIP (the human keel)" in out
    assert "keel:" in out  # at least one declared entry renders its keel line
    assert "declared" in out and "undeclared" in out


def test_a_malformed_ownership_level_fails_loud(tmp_path: Path) -> None:
    bad = tmp_path / "m.json"
    bad.write_text(
        json.dumps(
            {
                "career_board": {
                    "levels": [
                        {
                            "level": "entry",
                            "skills": [
                                {
                                    "skill_id": "x",
                                    "skill": "x",
                                    "status": "proven",
                                    "repo_proof": ["README.md"],
                                    "next_proof_task": "y",
                                    "ownership": {"level": 9},
                                }
                            ],
                        }
                    ]
                }
            }
        )
    )
    with pytest.raises(CareerError, match="ownership level"):
        load_board(bad)


def test_gaps_view_surfaces_the_real_gaps() -> None:
    # Structural, not pinned to a specific skill: as gaps are closed the list shrinks, but
    # while any partial/missing remains the view must show it with a next-proof-task + count.
    board = load_board()
    open_gaps = [
        s for lvl in board["levels"] for s in lvl["skills"] if s["status"] in ("partial", "missing")
    ]
    out = render_gaps()
    assert "GAPS" in out
    if open_gaps:
        assert "next:" in out
        assert "gap(s)" in out
    else:
        assert "No gaps recorded" in out


def test_ownership_view_shows_a_demonstrated_unlock() -> None:
    # A Classroom-demonstrated skill (not declared in the matrix) renders as `demonstrated`,
    # with the path to make it durable.
    out = render_ownership(demonstrated={"entry.python.basics": 2})
    assert "(demonstrated)" in out
    assert "career claim entry.python.basics" in out
    assert "demonstrated 1" in out


def test_claim_bridges_a_demonstrated_unlock() -> None:
    # `career claim` proposes the ownership block for Josh to commit -- it never writes it.
    out = render_claim("entry.python.basics", demonstrated={"entry.python.basics": 2})
    assert '"ownership"' in out and '"level": 2' in out
    assert "lessons/python_basics.yaml" in out  # cites the real lesson file (it exists)
    assert "commit it" in out.lower()
    assert "Level 4" in out  # refuses to grant portfolio-ready from a lesson


def test_claim_refuses_an_undemonstrated_skill() -> None:
    out = render_claim("entry.python.basics", demonstrated={})
    assert "not demonstrated yet" in out


def test_claim_rejects_an_unknown_skill() -> None:
    out = render_claim("no.such.skill", demonstrated={"no.such.skill": 2})
    assert "No such skill" in out


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
    assert "OWNERSHIP (the human keel)" in career("ownership")
    assert "Unknown career view" in career("nonsense")


def test_career_is_reachable_through_the_engine_tick() -> None:
    # A feature isn't wired until handle_command proves a player can reach it.
    from forge import handle_command
    from parts.session import Session

    out = handle_command(Session(player_id="career_tick"), "career gaps")
    assert "GAPS" in out
