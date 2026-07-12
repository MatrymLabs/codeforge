"""Test twin for parts/arc.py -- ARC composes gate verdicts into one honest readiness report."""

import pytest

from forge import handle_command
from parts.arc import (
    BLOCKED,
    DIMENSIONS,
    MISSING,
    READY,
    WATCHLIST,
    ArcError,
    Dimension,
    arc,
    compose,
    filed_review,
)
from parts.session import Session


def _seed_evidence(root):
    """Create the minimal filed evidence ARC reads, under a tmp root."""
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "docs" / "adr" / "0001-x.md").write_text("adr")
    (root / "docs" / "hardware_store" / "patterns").mkdir(parents=True)
    (root / "docs" / "hardware_store" / "patterns" / "p.md").write_text("pattern")
    (root / "tests").mkdir()
    (root / "tests" / "test_x.py").write_text("def test_x(): pass")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("name: CI")
    (root / "benchmarks").mkdir()
    (root / "benchmarks" / "b.py").write_text("x = 1")
    (root / "security-evidence").mkdir()
    (root / "security-evidence" / "s.json").write_text("{}")
    (root / "dependency_ledger.toml").write_text("[deps]\n")


def test_filed_review_reads_evidence_and_leaves_runtime_missing(tmp_path):
    _seed_evidence(tmp_path)
    status = {d.name: d.status for d in filed_review(tmp_path).dimensions}
    assert status["architecture"] == READY
    assert status["testing"] == READY
    assert status["dependency"] == READY
    assert status["security"] == READY
    assert status["change"] == MISSING  # runtime; no filed verdict
    assert status["release"] == MISSING


def test_filed_review_of_an_empty_repo_is_all_missing(tmp_path):
    report = filed_review(tmp_path)
    assert all(d.status == MISSING for d in report.dimensions)
    assert report.verdict == WATCHLIST  # missing is never a pass


def test_runtime_missing_holds_the_verdict_on_watchlist(tmp_path):
    _seed_evidence(tmp_path)
    # Six dimensions READY, four runtime MISSING -> not READY overall.
    assert filed_review(tmp_path).verdict == WATCHLIST


def _dim(name: str, status: str) -> Dimension:
    return Dimension(name, status, source=f"{name}-gate")


# --- acceptance: the composition rule --------------------------------------


def test_all_ready_composes_to_ready():
    report = compose([_dim("testing", READY), _dim("security", READY)])
    assert report.verdict == READY


def test_any_blocked_dimension_blocks_the_whole_report():
    report = compose([_dim("testing", READY), _dim("security", BLOCKED), _dim("release", READY)])
    assert report.verdict == BLOCKED


def test_a_watchlist_dimension_holds_the_report_on_watchlist():
    report = compose([_dim("testing", READY), _dim("performance", WATCHLIST)])
    assert report.verdict == WATCHLIST


def test_a_missing_dimension_is_never_a_pass():
    # No blocked, no watchlist, but one MISSING: the report is NOT ready.
    report = compose([_dim("testing", READY), _dim("change", MISSING)])
    assert report.verdict == WATCHLIST


def test_blocked_beats_missing():
    report = compose([_dim("change", MISSING), _dim("security", BLOCKED)])
    assert report.verdict == BLOCKED


# --- refusal: hostile cases fail loud --------------------------------------


def test_empty_review_fails_loud():
    with pytest.raises(ArcError):
        compose([])


def test_an_unknown_status_fails_loud():
    with pytest.raises(ArcError) as err:
        Dimension("testing", "green", source="x")
    assert "status must be one of" in str(err.value)


def test_a_status_without_a_source_fails_loud():
    with pytest.raises(ArcError) as err:
        Dimension("testing", READY, source="   ")
    assert "cite its source" in str(err.value)


# --- the verb / ARC Chamber panel ------------------------------------------


def test_arc_status_reports_all_ten_dimensions_with_a_mixed_verdict():
    out = arc("status")
    # Slice 2: the runtime dimensions are still MISSING, so the whole verdict stays WATCHLIST.
    assert "VERDICT: WATCHLIST" in out
    for name, _source in DIMENSIONS:
        assert name in out
    assert "ready" in out  # some dimensions now read real filed evidence
    assert "missing" in out  # the runtime ones honestly have no filed verdict
    assert "not certification" in out  # readiness language, never certification


def test_bare_arc_verb_shows_the_panel():
    assert "Assurance, Readiness, Control" in arc("")


def test_unknown_arc_action_is_refused_cleanly():
    assert "Unknown arc action" in arc("wibble")


def test_arc_is_reachable_through_the_engine_tick():
    session = Session(player_id="matrym", location="courtyard")
    out = handle_command(session, "arc")
    assert "ARC" in out and "VERDICT" in out
