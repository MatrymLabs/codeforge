"""Test twin for parts/arc.py -- ARC composes gate verdicts into one honest readiness report."""

import pytest

from forge import handle_command
from parts import chronicle
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
from parts.arc_ledger import VerdictError, record_verdict
from parts.session import Session


def _file_evidence(root, status=READY, source="test_evidence: ok", commit="testcommit"):
    """File an `evidence` verdict where ARC now reads it: the Chronicle (slice 1b)."""
    chronicle.append(
        "evidence",
        {"status": status, "source": source, "dimension": "evidence"},
        commit=commit,
        root=root,
    )


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


def test_filed_review_of_an_empty_repo_is_all_missing_except_a_clean_control(tmp_path):
    report = filed_review(tmp_path)
    by_name = {d.name: d.status for d in report.dimensions}
    # Every evidence dimension is MISSING (nothing filed)...
    assert all(s == MISSING for n, s in by_name.items() if n != "control")
    # ...except Control: an empty Chronicle has no open incident, which is a real pass, not unknown.
    assert by_name["control"] == READY
    assert report.verdict == WATCHLIST  # the missing dimensions still hold it


def test_an_open_serious_incident_holds_readiness_on_watchlist(tmp_path):
    from parts import chronicle

    _seed_evidence(tmp_path)
    _file_all_runtime_ready(tmp_path)  # everything else READY
    assert filed_review(tmp_path).verdict == READY  # baseline: clean Chronicle -> READY
    chronicle.record_incident("prod outage", "critical", commit="c", root=tmp_path)
    report = filed_review(tmp_path)
    assert {d.name: d.status for d in report.dimensions}["control"] == WATCHLIST
    assert report.verdict == WATCHLIST  # the Chronicle now holds the verdict


def test_a_low_or_closed_incident_does_not_hold_readiness(tmp_path):
    from parts import chronicle

    _seed_evidence(tmp_path)
    _file_all_runtime_ready(tmp_path)
    chronicle.record_incident("minor typo", "low", commit="c", root=tmp_path)
    chronicle.record_incident("was serious", "high", status="closed", commit="c", root=tmp_path)
    assert filed_review(tmp_path).verdict == READY  # low + closed do not trip Control


def test_an_ai_eval_regression_holds_readiness_on_watchlist(tmp_path):
    from datetime import UTC, datetime

    from parts import chronicle

    _seed_evidence(tmp_path)
    _file_all_runtime_ready(tmp_path)
    stamp = datetime(2026, 7, 1, tzinfo=UTC)
    chronicle.record_ai_eval(
        "arch.q", 1.0, model="m", passed=True, commit="a", root=tmp_path, stamp=stamp
    )
    chronicle.record_ai_eval(
        "arch.q", 0.4, model="m", passed=False, commit="b", root=tmp_path, stamp=stamp
    )
    report = filed_review(tmp_path)
    assert {d.name: d.status for d in report.dimensions}["control"] == WATCHLIST
    assert report.verdict == WATCHLIST


def test_runtime_missing_holds_the_verdict_on_watchlist(tmp_path):
    _seed_evidence(tmp_path)
    # Six dimensions READY, four runtime MISSING -> not READY overall.
    assert filed_review(tmp_path).verdict == WATCHLIST


def _file_all_runtime_ready(root):
    """File a READY verdict for every runtime dimension (what a full gate run would produce)."""
    for dim in ("change", "patch", "release"):
        record_verdict(dim, READY, f"{dim}-gate: ok", commit="testcommit", root=root)
    _file_evidence(root)  # evidence lives in the Chronicle (slice 1b), not arc-evidence/


def test_all_ten_compose_to_ready_when_runtime_verdicts_are_filed(tmp_path):
    # The point of the slice: with the six filed dims READY AND all four runtime verdicts filed
    # READY, ARC can finally reach a true READY (no longer stuck on WATCHLIST by construction).
    _seed_evidence(tmp_path)
    _file_all_runtime_ready(tmp_path)
    assert filed_review(tmp_path).verdict == READY


def test_a_filed_blocked_runtime_verdict_blocks_overall(tmp_path):
    _seed_evidence(tmp_path)
    _file_all_runtime_ready(tmp_path)
    record_verdict("release", BLOCKED, "release_gate: security failed", commit="c", root=tmp_path)
    assert filed_review(tmp_path).verdict == BLOCKED


def test_an_unfiled_runtime_dimension_stays_missing(tmp_path):
    # The driver files only release+evidence; change+patch have no store and stay MISSING (honest).
    _seed_evidence(tmp_path)
    record_verdict("release", READY, "release_gate: ok", commit="c", root=tmp_path)
    _file_evidence(tmp_path, source="test_evidence: ok", commit="c")
    status = {d.name: d.status for d in filed_review(tmp_path).dimensions}
    assert status["release"] == READY and status["evidence"] == READY
    assert status["change"] == MISSING and status["patch"] == MISSING
    assert filed_review(tmp_path).verdict == WATCHLIST  # missing change/patch hold it


def test_evidence_is_read_from_the_chronicle_not_arc_evidence(tmp_path):
    # Slice 1b: a record_verdict("evidence") is no longer where ARC looks; the Chronicle is.
    _seed_evidence(tmp_path)
    record_verdict("evidence", READY, "stale arc-evidence write", commit="c", root=tmp_path)
    status = {d.name: d.status for d in filed_review(tmp_path).dimensions}
    assert (
        status["evidence"] == MISSING
    )  # nothing in the Chronicle -> MISSING, ignoring arc-evidence
    _file_evidence(tmp_path)
    assert filed_review(tmp_path).dimensions  # sanity
    status = {d.name: d.status for d in filed_review(tmp_path).dimensions}
    assert status["evidence"] == READY  # now the Chronicle has it


def test_a_malformed_chronicle_evidence_record_fails_loud(tmp_path):
    _seed_evidence(tmp_path)
    chronicle.append(
        "evidence",
        {"status": "green", "source": "x", "dimension": "evidence"},  # 'green' is not an ARC status
        commit="c",
        root=tmp_path,
    )
    with pytest.raises(chronicle.ChronicleError, match="malformed"):
        filed_review(tmp_path)


def test_a_malformed_runtime_verdict_fails_loud(tmp_path):
    _seed_evidence(tmp_path)
    directory = tmp_path / "arc-evidence"
    directory.mkdir()
    (directory / "2026-07-12-release.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(VerdictError):
        filed_review(tmp_path)


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
