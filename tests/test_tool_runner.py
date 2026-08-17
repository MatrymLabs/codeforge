"""Test twin for kernel/seedlab/tool_runner.py -- controlled build/test execution in a source.

Acceptance: an approved profile runs inside the source root (cwd boundary), captures output and exit
code, redacts secrets, times out a hung command, and persists evidence that survives restart and
feeds the Hub's builds/tests facets.

Refusal (the control plane's fences): an unlisted profile is refused and never runs; a missing
binary reports exit 127; a corrupt run log fails loud.

Every command here is fixed, harmless argv (sys.executable) -- no network, no arbitrary code.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from kernel.seedlab.project_model import Provenance
from kernel.seedlab.source_connector import LocalSource
from kernel.seedlab.tool_runner import (
    CommandRefused,
    FileRunLog,
    InMemoryRunLog,
    RunLogError,
    ToolRunResult,
    redact,
    render_run,
    run_and_record,
    run_labels,
    run_tool,
)

_CLOCK = "2026-08-01T00:00:00+00:00"


def _source(tmp_path: Path) -> LocalSource:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    return LocalSource(root, Provenance("demo-src", owner="josh"))


def _run(
    source: LocalSource, argv: list[str], *, timeout: float = 120.0, cap: int = 20_000
) -> ToolRunResult:
    return run_tool(
        source,
        "job",
        seed_id="seed-1",
        allowlist={"job": argv},
        clock=lambda: _CLOCK,
        timeout=timeout,
        cap=cap,
    )


# --- acceptance --------------------------------------------------------------------------------
def test_an_approved_command_runs_and_captures(tmp_path: Path) -> None:
    result = _run(_source(tmp_path), [sys.executable, "--version"])
    assert result.ok and result.exit_code == 0
    assert "Python" in result.output


def test_runs_inside_the_source_root(tmp_path: Path) -> None:
    src = _source(tmp_path)
    result = _run(src, [sys.executable, "-c", "import os; print(os.getcwd())"])
    assert result.output.strip() == str(src.root)  # the working-directory boundary


def test_a_failing_command_is_recorded_not_raised(tmp_path: Path) -> None:
    result = _run(_source(tmp_path), [sys.executable, "-c", "import sys; sys.exit(3)"])
    assert result.exit_code == 3 and result.ok is False


def test_a_hung_command_times_out(tmp_path: Path) -> None:
    result = _run(
        _source(tmp_path), [sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.4
    )
    assert result.timed_out is True and result.exit_code == 124


def test_a_missing_binary_reports_127(tmp_path: Path) -> None:
    result = _run(_source(tmp_path), ["definitely-not-a-real-binary-xyz"])
    assert result.exit_code == 127 and "not found" in result.output


def test_secrets_are_redacted_from_output(tmp_path: Path) -> None:
    result = _run(_source(tmp_path), [sys.executable, "-c", "print('password=hunter2')"])
    assert "hunter2" not in result.output and "[REDACTED]" in result.output


def test_redact_masks_key_blocks_and_assignments() -> None:
    out = redact("token=abc123\n-----BEGIN X-----\nkey\n-----END X-----\nok")
    assert "abc123" not in out and "BEGIN X" not in out and "ok" in out


def test_render_run_shows_verdict_and_output(tmp_path: Path) -> None:
    text = render_run(_run(_source(tmp_path), [sys.executable, "--version"]))
    assert "OK" in text and "Python" in text and "--- output ---" in text


def test_run_and_record_persists_and_survives_restart(tmp_path: Path) -> None:
    src = _source(tmp_path)
    log = FileRunLog(tmp_path / "runs")
    run_and_record(
        log,
        src,
        "job",
        seed_id="seed-1",
        kind="test",
        allowlist={"job": [sys.executable, "--version"]},
        clock=lambda: _CLOCK,
    )
    # Restart: a new log object over the same root recovers the run.
    recovered = FileRunLog(tmp_path / "runs").for_seed("seed-1")
    assert len(recovered) == 1 and recovered[0].kind == "test" and recovered[0].ok


def test_run_labels_feed_the_hub_facets(tmp_path: Path) -> None:
    src = _source(tmp_path)
    log = InMemoryRunLog()
    run_and_record(
        log,
        src,
        "job",
        seed_id="seed-1",
        kind="test",
        allowlist={"job": [sys.executable, "--version"]},
        clock=lambda: _CLOCK,
    )
    run_and_record(
        log,
        src,
        "job",
        seed_id="seed-1",
        kind="build",
        allowlist={"job": [sys.executable, "--version"]},
        clock=lambda: _CLOCK,
    )
    assert len(run_labels(log, "seed-1", "test")) == 1
    assert len(run_labels(log, "seed-1", "build")) == 1
    assert run_labels(log, "seed-1", "test")[0].startswith("job exit=0")


def test_run_lights_up_the_hub_tests_facet(tmp_path: Path) -> None:
    from kernel.seedlab.kernel import BlueprintKernel, InMemorySeedStore
    from kernel.seedlab.project_hub import ProjectHub, ProjectState

    kernel = BlueprintKernel(InMemorySeedStore(), clock=lambda: _CLOCK)
    kernel.create_seed("Demo", "josh", "a demo", seed_id="seed-1")
    log = InMemoryRunLog()
    run_and_record(
        log,
        _source(tmp_path),
        "job",
        seed_id="seed-1",
        kind="test",
        allowlist={"job": [sys.executable, "--version"]},
        clock=lambda: _CLOCK,
    )
    hub = ProjectHub(kernel)
    state = ProjectState("seed-1", tests=run_labels(log, "seed-1", "test"))
    assert "exit=0" in hub.command("seed-1", "list tests", state)


def test_uses_a_real_clock_by_default(tmp_path: Path) -> None:
    result = run_tool(
        _source(tmp_path), "job", seed_id="seed-1", allowlist={"job": [sys.executable, "--version"]}
    )
    assert "T" in result.when and len(result.when) > 10  # a real ISO-8601 timestamp


def test_output_is_capped(tmp_path: Path) -> None:
    result = _run(_source(tmp_path), [sys.executable, "-c", "print('x' * 500)"], cap=50)
    assert "truncated" in result.output and len(result.output) < 200


def test_for_seed_is_empty_when_no_runs(tmp_path: Path) -> None:
    assert FileRunLog(tmp_path / "runs").for_seed("seed-unknown") == []


# --- refusal -----------------------------------------------------------------------------------
def test_an_unlisted_profile_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CommandRefused, match="not an approved"):
        run_tool(_source(tmp_path), "rm-rf", seed_id="seed-1", allowlist={"safe": ["true"]})


def test_a_corrupt_run_log_fails_loud(tmp_path: Path) -> None:
    log = FileRunLog(tmp_path / "runs")
    (log.root / "seed-1.jsonl").write_text("{not json\n", encoding="utf-8")
    with pytest.raises(RunLogError, match="corrupt"):
        log.for_seed("seed-1")


def test_from_dict_refuses_malformed() -> None:
    with pytest.raises(RunLogError, match="malformed"):
        ToolRunResult.from_dict({"profile": "x"})  # missing required fields
