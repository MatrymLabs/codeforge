"""Test twin for benchmarks/perf_journeys.py -- the five-journey harness's evidence report.

Acceptance: a canned results dict renders a readable table and files a dated report under
reports/performance/ (matching the engine-tick bench). Refusal / robustness: a journey missing
its stats renders zeros rather than crashing. Measurement itself is not exercised here (that is
slow and host-dependent); these tests pin the reporting seam, which is the part issue #160 added.
"""

from __future__ import annotations

from pathlib import Path

from benchmarks.perf_journeys import render_journeys, write_journeys_report

# A canned run - the shape `run()` returns, without paying the measurement cost.
_RESULTS: dict[str, dict] = {
    "startup": {
        "median_us": 158900.0,
        "p95_us": 179700.0,
        "max_us": 192000.0,
        "reps": 15,
        "kind": "cold_subprocess",
    },
    "command": {
        "median_us": 10.2,
        "p95_us": 11.7,
        "max_us": 122.3,
        "reps": 20000,
        "kind": "warm_rotation",
    },
    "combat": {
        "median_us": 11.5,
        "p95_us": 13.3,
        "max_us": 66.1,
        "reps": 5000,
        "kind": "warm_strike",
    },
    "qa_gate_all": {
        "median_us": 5400.0,
        "p95_us": 9100.0,
        "max_us": 15000.0,
        "reps": 200,
        "kind": "warm",
    },
    "catalog_search": {
        "median_us": 159.0,
        "p95_us": 215.0,
        "max_us": 800.0,
        "reps": 2000,
        "kind": "warm",
    },
}


def test_render_shows_every_journey_and_the_header() -> None:
    out = render_journeys(_RESULTS)
    assert "FIVE-JOURNEY PERFORMANCE BENCHMARK" in out
    assert "median_us" in out and "p95_us" in out
    for journey in _RESULTS:
        assert journey in out


def test_report_is_filed_as_dated_evidence(tmp_path: Path) -> None:
    path = write_journeys_report(_RESULTS, root=tmp_path, stamp="2026-07-13")
    assert path == tmp_path / "reports" / "performance" / "2026-07-13-five-journeys.md"
    assert path.exists()
    body = path.read_text(encoding="utf-8")
    assert "startup" in body and "catalog_search" in body
    assert body.endswith("\n")


def test_a_missing_stat_renders_zero_rather_than_crashing() -> None:
    # A journey that failed to record its distribution must not break the report.
    out = render_journeys({"startup": {"kind": "cold_subprocess"}})
    assert "startup" in out
    assert "0" in out  # missing median/p95/max default to 0
