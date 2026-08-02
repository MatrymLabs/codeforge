# CodeForge contracts (Fleet Core)

Published, versioned **contract authorities** other fleet vessels conform to. This is codeforge's half
of the Fleet Core rule (MatrymLabs/ship [ADR 0003](https://github.com/MatrymLabs/ship/blob/main/docs/adr/0003-fleet-core.md)):
**publish the contract; let consumers generate/conform against it** - no forced runtime dependency.

## readiness.schema.json

The readiness API payloads served by codeforge:
- `StatusPayload` - `GET /api/status` (the evidence board; `parts/dashboard.py`)
- `BlueprintSummary` - `GET /api/blueprints` (`adapters/api.py`)

The Pydantic models are the source of truth; `generate.py` derives the JSON Schema from them.

- **Regenerate:** `make contracts` (runs `python contracts/generate.py`).
- **Drift gate:** `tests/test_contracts.py` fails if the committed schema no longer matches the models,
  so codeforge cannot silently diverge from its own published contract.
- **Version:** `x-fleet-core.version` (currently `1.0.0`); bump on a breaking change so consumers can pin.

## Consumers

`codeforge-console` vendors this schema and **generates** `lib/types.ts` from it (`npm run gen:types`),
with its own CI drift gate - so the readiness contract is defined once, in Python, and the TypeScript
types are provably in step. That replaces the previous hand-mirrored types (which merely *claimed* to be
generated). The schema is vendored (copied), not imported at runtime: zero coupling, faithful reuse.
