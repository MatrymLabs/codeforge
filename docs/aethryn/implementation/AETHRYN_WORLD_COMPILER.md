# Aethryn World Compiler

The Aethryn World Compiler is an offline build boundary. It consumes a validated generation packet
and emits a CodeForge-compatible room batch plus a sidecar package of typed world records,
provenance, validation evidence, and a digest.

## Contract

```text
packet YAML
  -> packet_from_mapping
  -> canon, hierarchy, geography, purpose, settlement, ecology, economy, dungeon, provenance gates
  -> deterministic record enrichment
  -> CodeForge room-batch YAML and sidecar records
  -> manifest and content digest
  -> staged package and direct publication with rollback
```

The compiler has no model or network boundary. Its only inputs are the packet, the current canonical
sources, the selected repository root, the generator name and version, and the packet seed. It uses
stdlib dataclasses and canonical JSON hashing. The output digest covers the compiled batch and typed
records, not filesystem timestamps.

## Compiler foundation

The adapter-first foundation is implemented in five kernel modules:

- `aethryn_ir.py` normalizes packet records into `WorldIR` while preserving stable ids, authority,
  schema version, source design ids, and a source digest.
- `aethryn_schema.py` registers content type schemas, reference fields, migrations, compiler passes,
  serialization, runtime adapters, and optional modules.
- `aethryn_references.py` resolves declared scalar, list, and mapping-value references. Legacy
  replacement targets are passed as explicit compatibility external ids and are serialized into the
  IR instead of being silently accepted.
- `aethryn_diagnostics.py` provides one structured diagnostic envelope with rule, authority, source,
  related records, and corrective action.
- `aethryn_passes.py` provides the current ordered foundation passes: source loading, normalization,
  canon validation, and reference resolution. Later content passes remain separate backlog work.

`compile_packet` runs the foundation before its existing prose and package writer and emits
`world_ir.yaml` alongside the existing CodeForge room batch and sidecars. The existing materialized
room format remains unchanged.

## Versioned delivery

Every compiled package declares `aethryn-package/1`, the compiler version, content schema versions,
the output digest, and a migration plan. `aethryn_delivery.py` provides record-semantic package
diffs, conservative deterministic cache reuse, package integrity checks, and bounded hotfix
manifests. Hotfix creation requires both base and candidate packages to be clean and digest-valid;
it never publishes or changes canon by itself.

```text
world compile-packet <packet> --output <dir> --cache <cache-dir>
world diff <package-a> <package-b>
world hotfix <base-package> <candidate-package> --output <hotfix-dir>
world cache-inspect <cache-dir>
```

The current cache reuses a complete package when the packet, WorldIR source digest, cache schema,
and compiler version match. It is intentionally conservative until the remaining compiler passes
expose per-record dependency keys.

The foundation can be exercised without publishing:

```text
PYTHONPATH=. .venv/bin/pytest -q tests/test_aethryn_compiler_foundation.py
PYTHONPATH=. .venv/bin/python -m tools.world compile-packet content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml --output /tmp/aethryn-build
```

## Modules

- `kernel/world/aethryn_models.py`: frozen records, generation packets, manifests, provenance, and
  validation reports.
- `kernel/world/aethryn_validation.py`: packet loading and actionable cross-system validation.
- `kernel/world/aethryn_compiler.py`: deterministic compilation, package writing, publication, diff,
  provenance lookup, and restore.
- `kernel/world/aethryn_delivery.py`: package compatibility metadata, semantic diff, cache, integrity,
  and hotfix contracts.
- `kernel/world/aethryn_state.py`: persistent reversible state seam and text projection for the first
  slice.
- `kernel/world/aethryn_runtime.py`: read-only schedule, economy, ecology, and pressure projections
  from published sidecars.
- `kernel/world/aethryn_cli.py`: builder command implementation.
- `tools/world.py`: existing thin `world` entry point extended with builder commands.

## Runtime boundary

The runtime consumes the emitted `room_batches/<packet-id>.yaml` through the existing
`kernel/world/room_batches.py` adapter. NPC and creature names and notable objects are projected into
the existing batch occupant and object fields. Rich system records stay in `records.yaml`, while
`aethryn_runtime.py` projects schedules, economy flows, ecology pressure, and quest pressure into
room text. The `world_state.yaml` sidecar is consumed by `WorldStateStore`, which persists and
projects reversible state without mutating canonical room records. The runtime still does not
simulate movement, production quantities, inventory depletion, or creature population changes.

## Determinism rule

For a fixed packet, source set, generation seed, generator name, and generator version:

```text
compile(packet) -> identical batch bytes and identical output_digest
```

Changing a packet field, source design id, generation seed, generator version, or emitted record must
change the digest. A compiler version change is intentional and should be reviewed as a package
rebuild.

## Packet status

`AUTHORED_LOCAL` and `GENERATED_LOCAL` are publishable local statuses. `CANON_LOCKED` and
`CANON_WORKING` require explicit human authorization and cannot be requested silently by generated
records. Future packet publication is authorized by
`content/seeds/aethryn/design/promotion_authorization.yaml`, but each packet still carries its own
status and authorization fields. `RUMOR` is valid only for disputed or unresolved material and
cannot be used to state an objective answer.
