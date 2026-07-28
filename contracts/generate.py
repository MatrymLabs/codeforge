"""Generate the CodeForge readiness contract (Fleet Core pilot, ship ADR 0003).

The FastAPI readiness payloads -- `StatusPayload` (GET /api/status) and `BlueprintSummary`
(GET /api/blueprints) -- are the source of truth. This publishes their JSON Schema as a committed,
versioned artifact (`readiness.schema.json`) so a consumer (codeforge-console) can GENERATE its
types from the same contract instead of hand-mirroring it. That is the Fleet Core rule: publish the
contract, let consumers conform to it.

Regenerate with `make contracts`; `tests/test_contracts.py` fails if the committed schema drifts
from the models, so codeforge can never silently diverge from its own published contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic.json_schema import models_json_schema

from parts.api import BlueprintSummary
from parts.dashboard import StatusPayload

# Bump on a breaking contract change; consumers pin/vendor against this.
CONTRACT_VERSION = "1.0.0"
SCHEMA_PATH = Path(__file__).resolve().parent / "readiness.schema.json"


def build_schema() -> dict[str, Any]:
    """The readiness contract as one JSON Schema document.

    The payloads live under `$defs`; a `ReadinessContract` root ties them together so every type is
    reachable (clean code generation, no orphan/`unreachableDefinitions` types). The schema is made
    codegen-friendly: Pydantic's per-field `title` noise is stripped, and each payload object is
    closed (`additionalProperties: false`) so a generated type is exact, not open-ended.
    """
    _, schema = models_json_schema(
        [(StatusPayload, "serialization"), (BlueprintSummary, "serialization")],
    )
    defs: dict[str, Any] = schema["$defs"]
    for model in defs.values():
        model.pop("title", None)
        for prop in model.get("properties", {}).values():
            prop.pop("title", None)  # "Blueprint Id" etc. -> codegen aliases; drop it
        if model.get("type") == "object":
            model.setdefault("additionalProperties", False)  # closed payload; `rows` keeps its own

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/MatrymLabs/codeforge/blob/main/contracts/readiness.schema.json",
        "x-fleet-core": {
            "version": CONTRACT_VERSION,
            "source": "codeforge parts/dashboard.py + parts/api.py",
            "adr": "MatrymLabs/ship docs/adr/0003-fleet-core.md",
        },
        "title": "ReadinessContract",
        "description": (
            "The fleet's readiness API payloads served by codeforge "
            "(GET /api/status -> status, GET /api/blueprints -> blueprints). "
            "Fleet Core contract; see ship ADR 0003."
        ),
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {"$ref": "#/$defs/StatusPayload"},
            "blueprints": {"type": "array", "items": {"$ref": "#/$defs/BlueprintSummary"}},
        },
        "required": ["status", "blueprints"],
        "$defs": defs,
    }


def render() -> str:
    """The committed text: pretty JSON + trailing newline, so a byte-diff is a clean drift gate."""
    return json.dumps(build_schema(), indent=2) + "\n"


def write() -> Path:
    SCHEMA_PATH.write_text(render(), encoding="utf-8")
    return SCHEMA_PATH


if __name__ == "__main__":
    path = write()
    print(f"wrote {path}")
