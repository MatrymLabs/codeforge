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
)
from parts.session import Session


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


def test_arc_status_reports_all_ten_dimensions_missing_in_slice_one():
    out = arc("status")
    assert "VERDICT: WATCHLIST" in out  # nothing wired yet, so nothing is a pass
    for name, _source in DIMENSIONS:
        assert name in out
    assert out.count("missing") >= len(DIMENSIONS)
    assert "not certification" in out  # readiness language, never certification


def test_bare_arc_verb_shows_the_panel():
    assert "Assurance, Readiness, Control" in arc("")


def test_unknown_arc_action_is_refused_cleanly():
    assert "Unknown arc action" in arc("wibble")


def test_arc_is_reachable_through_the_engine_tick():
    session = Session(player_id="matrym", location="courtyard")
    out = handle_command(session, "arc")
    assert "ARC" in out and "VERDICT" in out
