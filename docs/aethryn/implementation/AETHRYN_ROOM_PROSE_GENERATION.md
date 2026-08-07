# Aethryn Room Prose Generation

This document defines the required prose pass for compiler-produced Aethryn room batches. It
extends the existing world compiler, room-batch adapter, runtime state projection, and Veridia
slice. It does not create a second world model.

## Build boundary

Room prose is generated offline while a packet is compiled. The runtime reads the published room
batch and never calls Codex, an LLM, a network service, or a prose API.

```text
generation packet
  -> packet validation
  -> deterministic record enrichment
  -> room presentation builder
  -> prose and canon validation
  -> similarity report
  -> CodeForge room batch
  -> materialization and rollback publication
```

The implementation lives in:

- `kernel/world/aethryn_room_prose.py`, the deterministic presentation builder and similarity
  report;
- `kernel/world/aethryn_validation.py`, the packet-level prose gate;
- `kernel/world/aethryn_compiler.py`, the batch and sidecar emitter;
- `kernel/world/room_batches.py`, the publication and runtime loading gate;
- `kernel/world/world.py`, the text-client renderer;
- `forge.py`, the `look` and `look verbose` command projection.

## Prose sources and inheritance order

The compiler resolves a room in this order:

1. Explicit room `short_description`, `long_description`, and `points_of_interest` values in the
   packet are the highest local prose input.
2. The packet room `description`, `display_name`, `room_type`, `purpose`, parent region, and parent
   zone supply the room identity and gameplay purpose.
3. Packet geography and architecture profiles provide deterministic environmental context. They
   are used to make the room belong to its region, not to invent global lore.
4. Item and resource records anchored with `source_room` become structured points of interest.
   State changes and quest pressures become structured conditions.
5. The deterministic context sentence completes a missing long description. It is a build fallback,
   not a license to fill unknown canon.

`kernel/world/authoring_prose.py` remains the authored voice layer for legacy and materialized seed
rooms. Compiler-produced Aethryn batches carry their own presentation fields and are not routed
through a legacy lore fallback.

## Room payload

Every compiler-produced room in a batch declaring `presentation_spec: aethryn-room-v1` contains:

| Field | Meaning |
| --- | --- |
| `name` | Stable display title. |
| `area_name` | Region or zone display name used by the text template. |
| `room_type` | City, wilderness, road, dungeon, service, threshold, or another declared type. |
| `primary_purpose` | One or more gameplay purposes. |
| `short_description` | One or two immediate-identity sentences for ordinary `look`. |
| `long_description` | Room-specific prose for `look verbose`. |
| `points_of_interest` | Structured interactive nouns with stable ids, display labels, kinds, and actions. |
| `conditions` | Structured state and pressure references. Temporary values stay outside static prose. |
| `exits` | Direction to destination labels. Topology still comes from `world_graph.yaml`. |
| `parent_region`, `parent_zone` | Hierarchy inheritance. |
| `canon_status` | Inherited content authority status. |
| `prose_status` | `GENERATED_LOCAL` by default, or `AUTHORED_LOCAL` for a reviewed override. |
| `source_design_ids` | Design records that support the room. |
| `generation_seed` | Packet seed used for deterministic selection. |
| `generator_name`, `generator_version` | Rebuild identity. |
| `provenance` | Packet, source paths, authority, seed, and generator evidence. |
| `content_digest` | Digest of the enriched room record. |

The batch also carries stable `occupant_refs`, `object_refs`, population references, crowd
references, and ambient evidence references where those systems contribute to the room.

## Presentation template

The payload is rendered using the current presentation specification:

```text
AREA - ROOM NAME

DESCRIPTION
short_description, or long_description for look verbose

CONDITIONS
structured visible state, only when present

POINTS OF INTEREST
stable display labels and available actions, only when present

EXITS
direction - destination label
```

Runtime occupants, weather, combat, opened doors, depleted resources, and temporary hazards are
projected from structured systems. They are not permanently concatenated into static room prose.

## Generation process

`build_room_presentation` performs only deterministic operations:

- normalize whitespace;
- derive a bounded short description from the first one or two source sentences;
- compose a context sentence using the packet region, terrain, architecture, room type, and
  purpose;
- derive points of interest from explicitly anchored records;
- derive conditions from packet state changes and quest pressures;
- assign `GENERATED_LOCAL` and packet provenance;
- produce a stable similarity report over the batch.

The packet seed and generator version are part of every output manifest. The same packet, source
inputs, seed, generator name, and generator version must produce the same batch bytes and digest.

## Validation rules

The packet validator and room-batch loader reject:

- missing or empty short and long descriptions;
- short descriptions longer than two sentences or long descriptions too short for verbose look;
- placeholder text and unchanged long descriptions across rooms;
- legacy Forge, Ember, or Unforging metaphysics;
- unsupported objective answers to unresolved global questions;
- temporary-state markers in static prose;
- missing area, purpose, region vocabulary, or structured points of interest;
- interactive records that have no stable point-of-interest projection;
- generated prose marked `CANON_LOCKED` or `CANON_WORKING`;
- missing seed, generator, parent, source, provenance, digest, or presentation fields;
- dangling exits or invalid room-batch fields.

The similarity report is written to `room_prose_similarity.yaml`. Regional words may repeat. Exact
long-description reuse is a validation failure, while repeated regional terminology remains visible
as a report rather than being incorrectly rejected.

## Authored overrides

An author may add explicit `short_description`, `long_description`, or structured points to a room
packet after reviewing the source evidence. The record remains local and must state
`prose_status: AUTHORED_LOCAL`. Generated prose must remain `GENERATED_LOCAL`. No room prose may be
silently promoted into current canon.

If a question is unresolved, write a rumor, damaged record, disputed interpretation, or faction
belief and mark the relevant record `RUMOR`. Do not use room prose to resolve the question.

## Exact builder commands

Validate each packet before publication:

```bash
PYTHONPATH=. .venv/bin/python -m tools.world validate-packet \
  content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml
```

Compile a reviewable staging package without publishing it:

```bash
PYTHONPATH=. .venv/bin/python -m tools.world compile-packet \
  content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml \
  --output /tmp/aethryn-veridia-room-prose
```

Inspect the batch and similarity evidence:

```bash
sed -n '1,220p' /tmp/aethryn-veridia-room-prose/room_batches/veridia_greenhold_living_slice.yaml
cat /tmp/aethryn-veridia-room-prose/room_prose_similarity.yaml
```

Materialize and publish with a rollback copy of the previous batch:

```bash
PYTHONPATH=. .venv/bin/python -m tools.world materialize \
  content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml
```

Run the room prose acceptance tests:

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_aethryn_room_prose.py
PYTHONPATH=. .venv/bin/python tools/validate_room_batches.py
```

The published batch is under `content/seeds/aethryn/room_batches/`. The prior artifact is retained
under `content/seeds/aethryn/.aethryn_rollbacks/` and can be restored with the existing compiler
restore operation.

