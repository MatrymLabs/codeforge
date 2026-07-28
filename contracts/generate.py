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
    """The readiness contract as a single JSON Schema document (all payloads under `$defs`)."""
    _, schema = models_json_schema(
        [(StatusPayload, "serialization"), (BlueprintSummary, "serialization")],
        title="CodeForge Readiness Contract",
        description=(
            "The fleet's readiness API payloads served by codeforge "
            "(GET /api/status, GET /api/blueprints). Fleet Core contract; see ship ADR 0003."
        ),
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/MatrymLabs/codeforge/blob/main/contracts/readiness.schema.json",
        "x-fleet-core": {
            "version": CONTRACT_VERSION,
            "source": "codeforge parts/dashboard.py + parts/api.py",
            "adr": "MatrymLabs/ship docs/adr/0003-fleet-core.md",
        },
        **schema,
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
