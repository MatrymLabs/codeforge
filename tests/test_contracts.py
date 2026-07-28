"""Test twin for the readiness contract (Fleet Core pilot, ship ADR 0003).

Drift gate: the committed contracts/readiness.schema.json MUST equal what the live Pydantic models
generate, so codeforge cannot silently diverge from its own published contract (the same discipline
matrym-hashchain's conformance vectors give the ledger). Acceptance: the contract still covers
the real payloads and is versioned. Refusal: a stale committed file fails loud with the fix command.
"""

from __future__ import annotations

from contracts.generate import SCHEMA_PATH, build_schema, render


def test_committed_schema_matches_the_models():
    committed = SCHEMA_PATH.read_text(encoding="utf-8")
    assert committed == render(), (
        "readiness.schema.json is stale (the models changed): run `make contracts` and commit"
    )


def test_contract_covers_every_readiness_payload():
    defs = build_schema()["$defs"]
    assert set(defs) == {"StatusCard", "StatusPayload", "BlueprintSummary"}
    assert defs["StatusPayload"]["required"] == ["engine", "cards"]
    assert defs["StatusCard"]["required"] == [
        "key",
        "title",
        "status",
        "headline",
        "detail",
        "rows",
    ]
    assert defs["BlueprintSummary"]["required"] == [
        "blueprint_id",
        "title",
        "intent",
        "status",
        "requirement_count",
    ]


def test_contract_is_versioned_for_consumers():
    core = build_schema()["x-fleet-core"]
    assert core["version"] and isinstance(core["version"], str)  # consumers pin/vendor against this
