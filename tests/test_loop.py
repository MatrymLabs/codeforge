"""Test twin for parts/loop.py -- the manufacturing loop tracer."""

from parts.loop import TraceReport, main, render_trace, trace


def test_trace_workflow_engine_passes_all_stages():
    """THE SPINE PROOF: every manufacturing stage passes for workflow-engine."""
    report = trace("workflow-engine")
    assert isinstance(report, TraceReport)
    assert report.part_id == "workflow-engine"
    assert report.verdict == "pass"
    # every stage should be pass or skip (skip is OK, e.g. no blueprint)
    for stage in report.stages:
        assert stage.status in ("pass", "skip"), (
            f"{stage.stage} unexpectedly {stage.status}: {stage.detail}"
        )


def test_trace_unknown_part_reports_manifest_fail():
    """A bad part_id fails at the manifest stage."""
    report = trace("no-such-part-ever")
    assert report.verdict == "fail"
    manifest_stage = next(s for s in report.stages if s.stage == "manifest")
    assert manifest_stage.status == "fail"


def test_trace_report_is_filed_under_reports(tmp_path):
    """Evidence lands at reports/loop/."""
    # Create minimal structure for a trace (will fail, but should still file)
    trace("no-such-part", root=tmp_path, stamp="2026-07-12")
    report_path = tmp_path / "reports" / "loop"
    assert report_path.exists()
    filed = list(report_path.glob("*.md"))
    assert len(filed) == 1


def test_render_trace_shows_all_stages():
    """The text output contains each stage name and its status."""
    report = trace("workflow-engine")
    text = render_trace(report)
    assert "MANUFACTURING LOOP TRACE" in text
    assert "manifest" in text
    assert "catalog" in text
    assert "assembly" in text
    assert "tests" in text
    assert "docs" in text
    assert "VERDICT: PASS" in text


def test_main_exits_zero_on_pass():
    assert main(["trace", "workflow-engine"]) == 0


def test_main_exits_one_on_fail():
    assert main(["trace", "no-such-part-ever"]) == 1


def test_main_shows_usage_with_no_args():
    assert main([]) == 1
