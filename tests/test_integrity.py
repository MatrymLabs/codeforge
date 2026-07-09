"""Test twin for parts/integrity.py -- the RepoIntegrityRitual.

Integrity-first: the report must be HONEST. These pin that tool detection reflects
reality (injectable `which`), that a missing secret-scanner is reported
`not_configured` (never faked), that overclaim words are flagged, and that the
report states its own limitation. The tool-running boundary is a seam -- no test
runs the real suite.
"""

from datetime import date
from pathlib import Path

from parts.integrity import (
    build_report,
    overclaim_hits,
    presence_gaps,
    save_report,
    tool_status,
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
