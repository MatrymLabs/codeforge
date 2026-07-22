"""Test twin for parts/integrity.py -- the RepoIntegrityRitual.

Integrity-first: the report must be HONEST. These pin that tool detection reflects
reality (injectable `which`), that a missing secret-scanner is reported
`not_configured` (never faked), that overclaim words are flagged, and that the
report states its own limitation. The tool-running boundary is a seam -- no test
runs the real suite.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from parts.integrity import (
    build_report,
    career_currency_gaps,
    forward_claims,
    overclaim_hits,
    presence_gaps,
    save_report,
    tool_status,
)


def _seed_board(root: Path, last_updated: str) -> None:
    """Write a minimal career board with the given last_updated, for currency tests."""
    d = root / "data" / "career"
    d.mkdir(parents=True)
    (d / "career_evidence_matrix.json").write_text(
        json.dumps({"career_board": {"last_updated": last_updated, "levels": []}})
    )


def test_tool_status_reflects_the_injected_which():
    present = {"ruff", "pytest"}
    status = tool_status(which=lambda t: "/bin/" + t if t in present else None)
    assert status["ruff"] is True and status["pytest"] is True
    assert status["gitleaks"] is False  # not present -> honest False


def test_presence_gaps_finds_missing_files(tmp_path: Path):
    (tmp_path / "README.md").write_text("x")
    gaps = presence_gaps(root=tmp_path)
    assert "README.md" not in gaps  # present
    assert "LICENSE" in gaps  # missing -> reported


def test_overclaim_scan_flags_risky_words(tmp_path: Path):
    (tmp_path / "README.md").write_text("This is production-ready and CMMC compliant.")
    hits = overclaim_hits(root=tmp_path)
    assert "production-ready" in hits
    assert "cmmc compliant" in hits


def test_overclaim_scan_is_clean_when_wording_is_honest(tmp_path: Path):
    (tmp_path / "README.md").write_text("Readiness only. Human review required.")
    assert overclaim_hits(root=tmp_path) == []


# --- evidence currency (career board vs shipped capability) ---------------------------
def test_currency_flags_capability_shipped_after_the_board_was_updated(tmp_path: Path):
    # The convergence case: capability changed AFTER the board's last update -> reconcile.
    _seed_board(tmp_path, "2026-07-10")
    gaps = career_currency_gaps(
        root=tmp_path, today=date(2026, 7, 22), capability_change=date(2026, 7, 22)
    )
    assert len(gaps) == 1 and "after the career board's last update" in gaps[0]


def test_currency_is_clean_when_the_board_is_current_with_capability(tmp_path: Path):
    # Capability last changed on/before the board's update -> the board is current, no nudge.
    _seed_board(tmp_path, "2026-07-22")
    assert (
        career_currency_gaps(
            root=tmp_path, today=date(2026, 7, 22), capability_change=date(2026, 7, 22)
        )
        == []
    )


def test_currency_falls_back_to_calendar_staleness_without_git(tmp_path: Path):
    # No git signal (capability_change=None): a board untouched for months still nudges.
    _seed_board(tmp_path, "2026-01-01")
    gaps = career_currency_gaps(root=tmp_path, today=date(2026, 7, 22), capability_change=None)
    assert len(gaps) == 1 and "days ago" in gaps[0]


def test_currency_calendar_fallback_stays_quiet_when_recent(tmp_path: Path):
    _seed_board(tmp_path, "2026-07-20")
    assert (
        career_currency_gaps(root=tmp_path, today=date(2026, 7, 22), capability_change=None) == []
    )


def test_currency_reports_an_unparseable_last_updated(tmp_path: Path):
    _seed_board(tmp_path, "last week")  # not an ISO date
    gaps = career_currency_gaps(root=tmp_path, today=date(2026, 7, 22))
    assert len(gaps) == 1 and "unparseable" in gaps[0]


def test_currency_is_empty_when_there_is_no_board(tmp_path: Path):
    assert career_currency_gaps(root=tmp_path, today=date(2026, 7, 22)) == []


def test_report_includes_the_evidence_currency_line(tmp_path: Path):
    # build_report surfaces the currency queue as its own honest section (a queue, not a verdict).
    _seed_board(tmp_path, "2026-01-01")
    text = build_report(root=tmp_path, today=date(2026, 7, 22), tools={})
    assert "evidence currency:" in text


def test_forward_claims_lists_deliberate_markers_only(tmp_path: Path):
    # The reverse-drift queue: unchecked boxes, TODO, and label-form Remaining:/Deferred(.
    (tmp_path / "plan.md").write_text(
        "- [x] shipped thing\n"  # done -> not a claim
        "- [ ] the unbuilt thing\n"  # unchecked -> claimed
        "Remaining: the multiplayer cast\n"  # label form -> claimed
        "TODO: wire the ledger\n"  # TODO -> claimed
        "The remaining tests all pass here.\n"  # prose 'remaining' -> NOT a claim
    )
    hits = forward_claims(root=tmp_path, docs=("plan.md",))
    assert len(hits) == 3
    assert any(":2:" in h and "unbuilt thing" in h for h in hits)
    assert any("Remaining: the multiplayer cast" in h for h in hits)
    assert any("TODO: wire the ledger" in h for h in hits)
    assert not any("tests all pass" in h for h in hits)  # prose is not flagged


def test_forward_claims_is_empty_when_a_roadmap_is_fully_reconciled(tmp_path: Path):
    (tmp_path / "plan.md").write_text("- [x] done\n- [x] also done\nAll shipped and verified.\n")
    assert forward_claims(root=tmp_path, docs=("plan.md",)) == []


def test_forward_claims_skips_a_missing_doc(tmp_path: Path):
    assert forward_claims(root=tmp_path, docs=("nope.md",)) == []


def test_forward_claims_reaches_the_ship_plan_when_mounted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Cross-repo reverse-drift: the ship's DEVELOPMENT_PLAN.md lives outside this tree, so a
    claim there is invisible unless the ritual reaches across the boundary via SHIP_HOME."""
    ship = tmp_path / "ship"
    ship.mkdir()
    (ship / "DEVELOPMENT_PLAN.md").write_text("- [x] shipped slice\n- [ ] the still-unbuilt rung\n")
    monkeypatch.setenv("SHIP_HOME", str(ship))
    hits = forward_claims(root=tmp_path, docs=())
    assert len(hits) == 1
    assert hits[0].startswith("ship:DEVELOPMENT_PLAN.md:2:")
    assert "still-unbuilt rung" in hits[0]


def test_forward_claims_degrades_cleanly_when_the_ship_is_not_mounted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Off-ship (as in CI), no plan is reachable, so the ship scan contributes nothing and the
    gate never fails on a missing sibling repo."""
    monkeypatch.setenv("SHIP_HOME", str(tmp_path / "nowhere"))
    assert forward_claims(root=tmp_path, docs=()) == []


def test_report_surfaces_the_forward_claim_queue():
    report = build_report(today=date(2026, 7, 9))
    assert "forward-claim queue:" in report  # the reverse-drift section is always present


def test_report_queue_is_zero_when_no_roadmaps_are_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # A root without the roadmap docs has an empty queue (the claims-absent path). Clear SHIP_HOME
    # so an ambient ship checkout can't leak claims into this hermetic case.
    monkeypatch.delenv("SHIP_HOME", raising=False)
    report = build_report(root=tmp_path, today=date(2026, 7, 9))
    assert "forward-claim queue:  0" in report
    assert "Reconcile" not in report  # no reconcile next-action when the queue is empty


def test_report_is_honest_about_a_missing_secret_scanner():
    # with no secret scanner present, the report must SAY not_configured, not fake it
    report = build_report(today=date(2026, 7, 9), tools={})  # nothing detected
    assert "secret scan:" in report
    assert "not_configured" in report
    assert "Configure secret scanning" in report


def test_report_shows_detected_when_a_secret_scanner_is_present():
    report = build_report(today=date(2026, 7, 9), tools={"detect-secrets": True})
    assert "secret scan:       detected" in report
    assert "Configure secret scanning" not in report


def test_report_states_its_own_limitation():
    report = build_report(today=date(2026, 7, 9))
    assert "does NOT prove universal originality" in report
    assert "does not prove legal originality, security" in report
    assert "CodeForge Repo Integrity Report" in report


def test_save_report_writes_a_dated_file(tmp_path: Path):
    path = save_report("hello report", root=tmp_path, today=date(2026, 7, 9))
    assert path.exists()
    assert path.name == "2026-07-09-repo-integrity.md"
    assert "hello report" in path.read_text()


def test_run_repo_integrity_writes_a_real_report():
    from parts.integrity import run_repo_integrity

    path = run_repo_integrity()  # builds + saves under reports/repo_integrity/ (gitignored)
    assert path.exists()
    assert "CodeForge Repo Integrity Report" in path.read_text()
