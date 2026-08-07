# Aethryn Materialization and Rollback

Compilation creates a staged package. `materialize` then publishes it directly by default, while
`--stage-only` preserves a staging-only workflow.

## Staging

`compile-packet` and `materialize` first create a package containing:

- `room_batches/<packet-id>.yaml`;
- `records.yaml` with typed system records and record digests;
- `world_ir.yaml` with normalized records, source digest, authority, and explicit external ids;
- `manifest.yaml` with packet, generator, compiler, package schema, content schemas, counts, input
  digest, output digest, migration plan, and status;
- `provenance.yaml`;
- `validation_report.yaml`.

The staging directory can be inspected, diffed, tested, and discarded without changing the active
seed.

The optional package cache is keyed by packet payload, WorldIR source digest, cache schema, and
compiler version. A cache hit restores a previously validated complete package and does not publish
it.

## Publication

`world materialize ...` copies the staged room batch into
`content/seeds/aethryn/room_batches/`. If the target exists, the previous bytes are copied first to
`.aethryn_rollbacks/<packet-id>.yaml`. The package manifest remains the source record for the digest
and source design ids. Publication does not edit canon or change a canon status.

## Restore

The restore function copies the rollback artifact back to the active room-batch directory. A future
CLI restore command can wrap this same function after adding an explicit artifact selection and
confirmation gate. Until then, restore is available as a tested Python boundary and the rollback
file is ordinary recoverable data.

Hotfix packages are separate review artifacts. They record the base build digest, candidate digest,
changed stable ids, migration reasons, and the base build identity needed for rollback. They do not
publish automatically.

## Safety gates

Before publication:

1. packet validation is clean;
2. the output digest is recorded;
3. room-batch validation is clean;
4. `world validate` and focused compiler tests are clean;
5. a human reviews canon status, topology, and visible local content.

Runtime startup never invokes the compiler or a model. A published package is static seed data until
the normal CodeForge loader reads it.
