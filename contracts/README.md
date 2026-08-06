# CodeForge contracts (Fleet Core)

Published, versioned **contract authorities** other fleet vessels conform to. This is codeforge's half
of the Fleet Core rule (MatrymLabs/ship [ADR 0003](https://github.com/MatrymLabs/ship/blob/main/docs/adr/0003-fleet-core.md)):
**publish the contract; let consumers generate/conform against it** - no forced runtime dependency.

## readiness.schema.json

The readiness API payloads served by codeforge:
- `StatusPayload` - `GET /api/status` (the evidence board; `kernel/dashboard.py`)
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

## native_seed.v1.examples.json

The Native Seed GMCP package examples shared by `codeforge` and `codeforge-client`:

- Server to client: `Seed.Hello`, `Seed.Profile`, `Project.Status`, `Source.Tree`,
  `Source.Connection`, `Model.Schema`,
  `Build.Report`, `Architecture.Map`, `Research.Findings`, `Form.Schema`, `Blueprint.List`,
  `Deploy.Manifest`, `Deploy.Status`, and `Seed.Created`.
- Client to server: `Seed.Create`, `Form.Submit`, and `Workspace.Request`.

`contracts/native_seed.py` builds the examples from Forge's current package builders. The committed
artifact is a drift gate, not a runtime dependency: consumers vendor or read the JSON examples and
prove their parsers still accept them. `Seed.Profile` is emitted as pure data by
`kernel.gmcp.seed_profile` and the canonical `aethryn_profile`; the client validates it before
applying presentation. The workspace connector entry is additive: it locks the structured
provenance and connection details emitted for a registered local source.
