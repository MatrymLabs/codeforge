"""Test twin for parts/shelf/reporting.py -- the shared ReportWriter."""

from __future__ import annotations

from pathlib import Path

from parts.shelf.reporting import report_path, write_report


def test_report_path_is_dated_under_the_category(tmp_path: Path) -> None:
    p = report_path("frameup", root=tmp_path, stamp="2026-07-10")
    assert p == tmp_path / "reports" / "frameup" / "2026-07-10.md"
    assert p.parent.is_dir()  # created on demand


def test_slug_is_appended_to_the_stamp(tmp_path: Path) -> None:
    p = report_path("repo_integrity", root=tmp_path, stamp="2026-07-10", slug="repo-integrity")
    assert p.name == "2026-07-10-repo-integrity.md"


def test_write_report_writes_and_normalizes_trailing_newline(tmp_path: Path) -> None:
    p = write_report("frameup", "hello\n\n\n", root=tmp_path, stamp="2026-07-10")
    assert p.read_text(encoding="utf-8") == "hello\n"  # exactly one trailing newline


def test_write_report_returns_the_path(tmp_path: Path) -> None:
    p = write_report("misc", "body", root=tmp_path, stamp="2026-07-10")
    assert p.exists() and p.read_text().strip() == "body"
