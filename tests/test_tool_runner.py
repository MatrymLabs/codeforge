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
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kernel.permission_policy import PermissionDenied, PermissionPolicy, PermissionRule
from kernel.seedlab.audit_registry import FileAuditStore
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
from kernel.session_identity import SessionIdentity
from kernel.session_registry import FileSessionRegistry, SessionRegistryError

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


def _identity(*, seed_id: str = "seed-1", capabilities: frozenset[str] | None = None):
    now = datetime.now(UTC)
    return SessionIdentity(
        principal_id="human:josh",
        principal_kind="human",
        session_id="session-1",
        seed_id=seed_id,
        issued_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
        correlation_id="trace-1",
        capabilities=(frozenset({"tool.test"}) if capabilities is None else capabilities),
    )


# --- acceptance --------------------------------------------------------------------------------
def test_an_approved_command_runs_and_captures(tmp_path: Path) -> None:
    result = _run(_source(tmp_path), [sys.executable, "--version"])
    assert result.ok and result.exit_code == 0
    assert "Python" in result.output


def test_run_emits_redacted_structured_worker_logs(tmp_path: Path) -> None:
    logs: list[dict[str, object]] = []
    result = run_tool(
        _source(tmp_path),
        "job",
        seed_id="seed-1",
        correlation_id="trace-1",
        allowlist={"job": [sys.executable, "--version"]},
        clock=lambda: _CLOCK,
        log_sink=logs.append,
        worker_id="worker-1",
    )

    assert result.ok
    assert [entry["event"] for entry in logs] == ["tool.started", "tool.completed"]
    assert all(entry["seed_id"] == "seed-1" for entry in logs)
    assert all(entry["correlation_id"] == "trace-1" for entry in logs)
    assert all(entry["worker_id"] == "worker-1" for entry in logs)
    assert logs[-1]["output_digest"].__class__ is str
    assert "output" not in logs[-1] and "argv" not in logs[-1]


def test_run_records_source_digest_resource_policy_and_audit_identity(tmp_path: Path) -> None:
    result = run_tool(
        _source(tmp_path),
        "job",
        seed_id="seed-1",
        correlation_id="trace-1",
        allowlist={"job": [sys.executable, "--version"]},
        resource_limits={"cpu_seconds": 5, "memory_bytes": 128 * 1024 * 1024},
    )

    assert result.ok
    assert result.source_id == "demo-src"
    assert result.input_digest.startswith("sha256:")
    assert result.output_digest.startswith("sha256:")
    assert result.audit_id.startswith("audit:tool-")
    assert result.resource_limits["wall_seconds"] == 120.0
    assert "cpu_seconds" in result.resource_limits["enforced"]
    assert result.resource_usage["wall_seconds"] >= 0


def test_run_and_record_can_append_a_durable_audit_link(tmp_path: Path) -> None:
    audit = FileAuditStore(tmp_path / "audit.jsonl")
    log = InMemoryRunLog()
    result = run_and_record(
        log,
        _source(tmp_path),
        "job",
        seed_id="seed-1",
        allowlist={"job": [sys.executable, "--version"]},
        audit_store=audit,
        audit_actor="alice",
    )

    assert result.audit_id in audit.all_records()[0]["detail"]
    assert audit.verify() is True


def test_execution_checks_identity_scope_and_capability(tmp_path: Path) -> None:
    policy = PermissionPolicy((PermissionRule("tool.test", scope="seed-1"),))
    result = run_tool(
        _source(tmp_path),
        "job",
        seed_id="seed-1",
        kind="test",
        allowlist={"job": [sys.executable, "--version"]},
        identity=_identity(),
        policy=policy,
    )
    assert result.ok


def test_execution_requires_authoritative_session_registry_state(tmp_path: Path) -> None:
    identity = _identity()
    registry = FileSessionRegistry(
        tmp_path / "sessions", audit=FileAuditStore(tmp_path / "session-audit.jsonl")
    )
    registry.issue(identity)
    policy = PermissionPolicy((PermissionRule("tool.test", scope="seed-1"),))
    registry.invalidate(identity.session_id, actor="operator", reason="logout")

    with pytest.raises(SessionRegistryError, match="invalidated"):
        run_tool(
            _source(tmp_path),
            "job",
            seed_id="seed-1",
            kind="test",
            allowlist={"job": [sys.executable, "--version"]},
            identity=identity,
            policy=policy,
            session_registry=registry,
        )


def test_execution_refuses_cross_seed_identity_before_subprocess(tmp_path: Path) -> None:
    policy = PermissionPolicy((PermissionRule("tool.test", scope="seed-1"),))
    with pytest.raises(PermissionDenied, match="scoped to Seed"):
        run_tool(
            _source(tmp_path),
            "job",
            seed_id="seed-1",
            kind="test",
            allowlist={"job": [sys.executable, "--version"]},
            identity=_identity(seed_id="seed-other"),
            policy=policy,
        )


def test_execution_refuses_missing_capability_before_subprocess(tmp_path: Path) -> None:
    policy = PermissionPolicy((PermissionRule("tool.test", scope="seed-1"),))
    with pytest.raises(PermissionDenied, match="missing capability"):
        run_tool(
            _source(tmp_path),
            "job",
            seed_id="seed-1",
            kind="test",
            allowlist={"job": [sys.executable, "--version"]},
            identity=_identity(capabilities=frozenset()),
            policy=policy,
        )


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


def test_timeout_stops_descendants_before_durable_completion(tmp_path: Path) -> None:
    marker = tmp_path / "child-survived"
    child_code = (
        "import pathlib, sys, time; time.sleep(0.8); pathlib.Path(sys.argv[1]).write_text('alive')"
    )
    parent_code = (
        "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', "
        f"{child_code!r}, sys.argv[1]]); time.sleep(5)"
    )

    result = _run(
        _source(tmp_path), [sys.executable, "-c", parent_code, str(marker)], timeout=0.3
    )

    assert result.timed_out is True and result.exit_code == 124
    # The child would create this after the parent was stopped if the runner only terminated the
    # direct process. Give a surviving child enough time to do so before asserting the boundary.
    import time

    time.sleep(1.0)
    assert not marker.exists()


def test_a_running_command_can_be_cancelled(tmp_path: Path) -> None:
    checks = 0

    def cancel() -> bool:
        nonlocal checks
        checks += 1
        return checks > 2

    result = run_tool(
        _source(tmp_path),
        "job",
        seed_id="seed-1",
        allowlist={"job": [sys.executable, "-c", "import time; time.sleep(5)"]},
        cancel_check=cancel,
    )
    assert result.cancelled is True and result.ok is False and result.timed_out is False


def test_revocation_is_rechecked_at_the_execution_boundary(tmp_path: Path) -> None:
    policy = PermissionPolicy((PermissionRule("tool.test", scope="seed-1"),))
    identity = _identity()
    policy.revoke("tool.test", scope="seed-1", actor_id=identity.principal_id)
    with pytest.raises(PermissionDenied, match="revocation"):
        run_tool(
            _source(tmp_path),
            "job",
            seed_id="seed-1",
            kind="test",
            allowlist={"job": [sys.executable, "--version"]},
            identity=identity,
            policy=policy,
        )


def test_revocation_during_a_running_command_marks_the_result_non_success(tmp_path: Path) -> None:
    policy = PermissionPolicy((PermissionRule("tool.test", scope="seed-1"),))
    identity = _identity()
    revoked = False

    def revoke_after_start() -> bool:
        nonlocal revoked
        if not revoked:
            policy.revoke("tool.test", scope="seed-1", actor_id=identity.principal_id)
            revoked = True
        return False

    result = run_tool(
        _source(tmp_path),
        "job",
        seed_id="seed-1",
        kind="test",
        allowlist={"job": [sys.executable, "-c", "import time; time.sleep(0.15)"]},
        identity=identity,
        policy=policy,
        cancel_check=revoke_after_start,
    )
    assert result.revoked is True and result.ok is False


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
    from kernel.seedlab.kernel import InMemorySeedStore, SeedKernel
    from kernel.seedlab.project_hub import ProjectHub, ProjectState

    kernel = SeedKernel(InMemorySeedStore(), clock=lambda: _CLOCK)
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


def test_explicit_output_resource_limit_is_enforced_and_recorded(tmp_path: Path) -> None:
    result = run_tool(
        _source(tmp_path),
        "job",
        seed_id="seed-1",
        allowlist={"job": [sys.executable, "-c", "print('x' * 500)"]},
        resource_limits={"output_bytes": 50},
    )
    assert result.resource_limits["output_bytes"] == 50
    assert "truncated at 50 bytes" in result.output


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
