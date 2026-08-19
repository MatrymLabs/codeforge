from __future__ import annotations

import json

import pytest

from kernel.evidence_manifest import (
    EvidenceManifest,
    EvidenceManifestError,
    Result,
    sha256_file,
    write_manifest,
)

SHA = "a" * 64


def _manifest(**overrides: object) -> EvidenceManifest:
    values: dict[str, object] = {
        "blueprint_id": "seam-probe",
        "blueprint_version": "1.2.0",
        "work_order_id": "WO-EVIDENCE-1",
        "proof_run_id": "run-2026-08-19-001",
        "tool": "pytest",
        "tool_version": "9.1.1",
        "commit_sha": "a" * 40,
        "exact_command": ("python", "-m", "pytest", "-q"),
        "exit_code": 0,
        "result": Result.PASS,
        "artifact_sha256": SHA,
        "producing_bench": "codeforge-codex",
        "verifying_bench": "codeforge-claude",
        "exceptions": (),
    }
    values.update(overrides)
    return EvidenceManifest(**values)


def test_manifest_round_trips_every_required_field(tmp_path) -> None:
    manifest = _manifest(
        exceptions=(
            {
                "owner": "principal-engineer",
                "reason": "temporary tool outage",
                "expiration": "2026-09-01",
            },
        )
    )
    destination = write_manifest(manifest, tmp_path / "manifest.json")

    loaded = json.loads(destination.read_text(encoding="utf-8"))
    assert loaded["blueprint_id"] == "seam-probe"
    assert loaded["blueprint_version"] == "1.2.0"
    assert loaded["exact_command"] == ["python", "-m", "pytest", "-q"]
    assert loaded["result"] == "PASS"
    assert loaded["exceptions"] == [
        {
            "owner": "principal-engineer",
            "reason": "temporary tool outage",
            "expiration": "2026-09-01",
        }
    ]
    assert EvidenceManifest.from_dict(loaded) == manifest


@pytest.mark.parametrize("result", Result)
def test_all_four_verdicts_are_explicit(result: Result) -> None:
    exit_code = 0 if result is Result.PASS else None
    assert _manifest(result=result, exit_code=exit_code).result is result


def test_missing_verifying_bench_is_refused_at_construction() -> None:
    with pytest.raises(EvidenceManifestError, match="verifying_bench is required"):
        _manifest(verifying_bench="")


def test_exception_without_expiration_is_refused_at_construction() -> None:
    with pytest.raises(EvidenceManifestError, match="exception expiration is required"):
        _manifest(exceptions=({"owner": "owner", "reason": "reason", "expiration": ""},))


def test_tool_crash_cannot_be_serialized_as_pass() -> None:
    with pytest.raises(EvidenceManifestError, match="PASS result requires exit_code 0"):
        _manifest(exit_code=1, result=Result.PASS)


def test_sha256_file_is_the_artifact_hash(tmp_path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_bytes(b"proof\n")
    assert (
        sha256_file(artifact) == "f6ed42a9d765eeb230a069bbc3d5dc346b2669594bb0b83cc6d14d5d967b8961"
    )
