# Aethryn Compiler Foundation

This phase introduces the first shared compiler boundary without replacing the existing packet
compiler, Seed loader, runtime, or materialization format.

## Contracts

`WorldIR` is an adapter-first normalized representation. Each record contains:

- content type and stable id;
- schema version;
- canon status or local authority;
- source design ids;
- original payload;
- world source digest at the package level.

`SchemaRegistry` declares the contract for each supported content type. It currently records parser,
validator, migration, declared references, serialization format, compiler passes, runtime adapter,
and optional modules. Duplicate schema registration fails loudly.

`ReferenceResolver` checks only declared fields. It accepts normalized records or explicitly supplied
external ids. This preserves current replacement content while making the compatibility boundary
visible in `world_ir.yaml`.

`DiagnosticReport` is the common reason-bearing result. Every finding carries a code, severity,
subsystem, source path, record, field, message, violated rule, authority source, suggested correction,
and related records.

`PassManager` topologically orders real compiler passes, rejects missing dependencies and cycles, and
supports targeted execution. The implemented foundation passes are:

```text
source_loading
  -> normalization
       -> reference_resolution
source_loading
  -> canon_validation
```

## Compatibility boundary

The current packet compiler still owns prose generation, package writing, state sidecars, and room
batch publication. The foundation runs before those operations. It writes a normalized `world_ir.yaml`
sidecar but does not alter the runtime room schema or move stable player data.

Legacy replacement rooms, population pressure ids, and representative NPC ids outside a packet are
passed as explicit compatibility external ids. They are not promoted into canon or generated content.

## Proof

```text
PYTHONPATH=. .venv/bin/pytest -q tests/test_aethryn_compiler_foundation.py tests/test_aethryn_world_compiler.py
```

The phase proof includes Veridia normalization, a structurally different second-world fixture,
duplicate schema rejection, unresolved-reference diagnostics, deterministic packet compilation, pass
ordering, targeted execution, and cycle rejection.

## Delivery extension now present

The package writer now emits package and content schema metadata. The delivery boundary provides
semantic package diffing, integrity checks, deterministic complete-package cache reuse, and bounded
hotfix manifests with base-build identity and rollback identity.

## Deliberate deferrals

- full-world normalization across every legacy procedural source;
- aliases and complete dependency-aware per-record rebuilding;
- content schema migrations and save compatibility beyond compatibility metadata;
- hotfix application, publication approval, and complete package rollback;
- topology, economy, progression, state, presentation, runtime adaptation, and proof packaging passes;
- generic profile and plugin boundaries.
