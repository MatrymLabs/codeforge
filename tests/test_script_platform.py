"""Contract and hostile-input tests for the governed script platform."""

from __future__ import annotations

import hashlib
import math
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from kernel.script_platform.audit import AuditLedger, ScriptAuditRecord
from kernel.script_platform.broker import BrokerError, CapabilityBroker, CapabilityRequest
from kernel.script_platform.models import (
    LifecycleError,
    LifecycleManager,
    LifecycleStatus,
    ScriptManifest,
)
from kernel.script_platform.state import FileStateStore, StateConflict, StateStoreError
from kernel.script_platform.supervisor import ScriptRunnerSupervisor, WorkerError, WorkerPolicy
from kernel.script_platform.validator import ManifestValidator


def _manifest(**overrides: object) -> ScriptManifest:
    manifest = ScriptManifest(
        script_id="script.aethryn.weather",
        version="1.0.0",
        language="lua",
        source_hash=hashlib.sha256(b"return 1").hexdigest(),
        source_revision=1,
        entrypoints={"timer.weather.advance": "advance"},
        seed_ids=("aethryn",),
        object_types=("room.region",),
        capabilities=frozenset({"state.read:weather.*", "message.emit:room.ambient"}),
        provenance_id="PROV-1",
        owner_id="alice",
    )
    return replace(manifest, **cast(dict[str, Any], overrides))


def test_manifest_validator_accepts_a_scoped_manifest() -> None:
    report = ManifestValidator().validate(_manifest())
    assert report.valid
    assert report.errors == ()


@pytest.mark.parametrize(
    "override,code",
    [
        ({"source_hash": "not-a-digest"}, "invalid_hash"),
        ({"provenance_id": ""}, "missing_provenance"),
        ({"capabilities": frozenset({"shell:run"})}, "forbidden_capability"),
        ({"entrypoints": {}}, "missing_entrypoint"),
    ],
)
def test_manifest_validator_rejects_unsafe_or_incomplete_manifests(
    override: dict[str, object], code: str
) -> None:
    report = ManifestValidator().validate(_manifest(**override))
    assert not report.valid
    assert any(issue.code == code for issue in report.errors)


def test_lifecycle_requires_review_before_activation() -> None:
    lifecycle = LifecycleManager("script.aethryn.weather")
    for status in (
        LifecycleStatus.VALIDATING,
        LifecycleStatus.TESTABLE,
        LifecycleStatus.TESTING,
        LifecycleStatus.REVIEW,
        LifecycleStatus.APPROVED,
        LifecycleStatus.STAGED,
    ):
        lifecycle.transition(status, actor_id="alice")
    with pytest.raises(LifecycleError, match="independent"):
        lifecycle.transition(LifecycleStatus.ACTIVE, actor_id="alice")
    assert (
        lifecycle.transition(LifecycleStatus.ACTIVE, actor_id="reviewer", independent_approval=True)
        == LifecycleStatus.ACTIVE
    )


def test_capability_broker_is_deny_by_default_and_seed_scoped() -> None:
    broker = CapabilityBroker(
        capabilities=frozenset({"state.read:weather.*"}), seed_id="aethryn", host_call_limit=2
    )
    broker.register("state.read", lambda request: {"key": request.resource})
    allowed = CapabilityRequest(
        "script.aethryn.weather", 1, "aethryn", "state.read", "weather.phase"
    )
    assert broker.call(allowed).value == {"key": "weather.phase"}
    with pytest.raises(BrokerError, match="denied"):
        broker.call(
            CapabilityRequest(
                "script.aethryn.weather", 1, "aethryn", "state.write", "weather.phase"
            )
        )
    with pytest.raises(BrokerError, match="cross-seed"):
        broker.call(
            CapabilityRequest("script.aethryn.weather", 1, "other", "state.read", "weather.phase")
        )


def test_capability_broker_enforces_call_quota() -> None:
    broker = CapabilityBroker(capabilities={"clock.now"}, seed_id="aethryn", host_call_limit=1)
    broker.register("clock.now", lambda _request: 42)
    request = CapabilityRequest("script.aethryn.clock", 1, "aethryn", "clock.now")
    assert broker.call(request).value == 42
    with pytest.raises(BrokerError, match="quota"):
        broker.call(request)


def test_state_is_typed_bounded_versioned_and_restartable(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    store = FileStateStore(path, max_bytes=256)
    assert store.read("attachment-1") == (0, {})
    assert store.compare_and_set("attachment-1", 0, {"phase": "rain"}) == 1
    with pytest.raises(StateConflict):
        store.compare_and_set("attachment-1", 0, {"phase": "sun"})
    with pytest.raises(StateStoreError, match="JSON"):
        store.compare_and_set("attachment-1", 1, {"bad": object()})
    with pytest.raises(StateStoreError, match="NaN"):
        store.compare_and_set("attachment-1", 1, {"bad": math.nan})
    recovered = FileStateStore(path, max_bytes=256)
    assert recovered.read("attachment-1") == (1, {"phase": "rain"})


def test_audit_ledger_is_append_only_and_bounded(tmp_path: Path) -> None:
    ledger = AuditLedger(tmp_path / "audit.jsonl")
    record = ScriptAuditRecord(
        event_id="evt-1",
        script_id="script.aethryn.weather",
        source_revision=1,
        seed_id="aethryn",
        sandbox_id="lua-worker-1",
        invocation_cause="timer.weather.advance",
        result="ok",
        correlation_id="corr-1",
        output_summary="x" * 5000,
    )
    ledger.append(record)
    assert len(ledger.records()[0].output_summary) == 2048
    with pytest.raises(ValueError, match="duplicate"):
        ledger.append(record)
    assert AuditLedger(tmp_path / "audit.jsonl").records() == (record,)


def test_supervisor_uses_external_process_and_bounded_protocol(tmp_path: Path) -> None:
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import json, sys\n"
        "payload = json.load(sys.stdin)\n"
        "print(json.dumps({'script_id': payload['manifest']['script_id']}))\n",
        encoding="utf-8",
    )
    result = ScriptRunnerSupervisor().run(
        _manifest(),
        {"event": "timer.weather.advance"},
        executable=Path(sys.executable),
        arguments=(str(worker),),
        policy=WorkerPolicy(wall_ms=1000),
    )
    assert result.payload == {"script_id": "script.aethryn.weather"}


def test_supervisor_kills_a_worker_that_exceeds_wall_budget(tmp_path: Path) -> None:
    worker = tmp_path / "slow_worker.py"
    worker.write_text("import time; time.sleep(2)\n", encoding="utf-8")
    with pytest.raises(WorkerError, match="wall-clock"):
        ScriptRunnerSupervisor().run(
            _manifest(),
            {},
            executable=Path(sys.executable),
            arguments=(str(worker),),
            policy=WorkerPolicy(wall_ms=20),
        )
