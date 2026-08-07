# Aethryn World Pipeline Audit

Status: Phase 0 reality audit, 2026-08-06

## Authority and current system

The current Aethryn authority order is:

1. `content/seeds/aethryn/canon.yaml`
2. `docs/aethryn_lore_bible.md` and `docs/aethryn/aethryn_lore_bible.md` when present
3. `content/seeds/aethryn/world_graph.yaml`
4. `content/seeds/aethryn/generation_contract.yaml`
5. the supplied master design and map-reconciled material
6. current structured seed data
7. authored local content
8. legacy material that does not conflict

The map poster is orientation only. `world_graph.yaml` is the topology authority. A shared sea is a
world reachability relation, not an automatic playable room-to-room route.

The current source-to-runtime path is:

```text
canon.yaml + world_graph.yaml + generation_contract.yaml
    -> canon.py, worldgraph.py, generation_contract.py
structured seed YAML and authored/*.yaml
    -> seed.py loaders and authored_towns.py
runtime generators: wildlands, fields, caves, underground, delves, zones
    -> kernel/world/world.py assembly
room_batches/*.yaml
    -> room_batches.apply_room_batches
all assembled records
    -> Forge engine tick and gateway projections
```

`kernel/world/world.py` is the assembly boundary. Runtime generators are currently invoked during
world construction unless a pure authoring snapshot is selected. `tools/materialize_aethryn.py`
boots that assembly once and serializes an authored package with an `authoring_manifest.yaml`.

## Existing components and classification

### REUSE_EXISTING

- `kernel/world/canon.py`: loads and structurally validates the five canon sections, statuses, Seven
  Crowns, fourteen regions, factions, and correspondence to placed world records.
- `kernel/world/worldgraph.py`: validates region coverage and references, builds land and shared-sea
  reachability, and reports unreachable regions.
- `kernel/world/generation_contract.py`: enforces required area fields, historical layers, dungeon
  grammar, forbidden changes, and archetype share recommendations.
- `kernel/world/seed.py`: existing CodeForge-compatible room and record loaders. Room records remain
  the runtime compatibility contract.
- `kernel/world/survey.py` and `tools/world.py`: the read-only `world` developer command family.
- `kernel/world/room_batches.py`: controlled authored prose drops with stable batch ids, sequencing,
  explicit exits, duplicate-room protection, and runtime application.
- `kernel/world/area_store.py`: deterministic offline area preview, promotion, and export boundary.
- `kernel/world/fieldzone.py`, `wildlands.py`, `caves.py`, `underground.py`, and `delve.py`:
  existing deterministic content generators and runtime adapters.
- `kernel/world/world_manifest.py`: typed seed identity and start-room reconciliation.
- `tools/materialize_aethryn.py`: existing pure-authoring serialization path and rollback-friendly
  snapshot directory model.

### REPAIR_EXISTING

- `canon.check_canon()` currently checks placement correspondence but does not compare a proposed
  design against a locked-canon fingerprint, detect objective answers to open questions, or block
  unauthorized status promotion.
- `survey.validate()` checks duplicate ids, placed location regions, factions, canon correspondence,
  and region reachability. It does not inspect every room, hierarchy, reciprocal exits, settlement
  dependencies, ecology, economy, dungeon grammar, or provenance.
- Room-batch validation protects prose and exits but intentionally rejects design metadata. A compiler
  must keep design metadata in a sidecar manifest while emitting only the fields the room loader can
  consume.
- Materialization records source paths and counts but does not yet emit a content digest, a typed
  generation manifest, or an explicit package restore index.
- Existing generated field and cave records carry seeds, but their determinism is not yet tested as
  one package-level contract.

### EXTEND_EXISTING

- Extend `tools/world.py` and `kernel/world/survey.py` with packet, provenance, economy, ecology,
  canon, map-concordance, orphan, and explanation commands.
- Extend the existing materialization boundary with manifests, digests, package comparison, and
  reversible publication.
- Keep generated rooms in CodeForge room-batch or seed YAML. Do not create a second runtime world
  graph.

### BUILD_NEW

- A typed design model layer for world records, generation packets, manifests, and validation reports.
- A deterministic compiler that consumes a packet and produces a validated CodeForge-compatible
  package plus a sidecar design manifest.
- Cross-cutting validators for hierarchy, room purpose, settlement systems, economy, ecology,
  dungeons, provenance, and deterministic publication.
- A first Veridia packet that exercises the complete data path without attempting mass generation.

### DEFER

- Full structured authoring for all fourteen regions.
- A complete cross-region settlement economy and the actual sea-route room network.
- Large NPC schedule simulation, global faction politics, and full ancient-technology taxonomies.
- Automated promotion of generated content into any canon tier.

### HUMAN_DECISION_REQUIRED

Resolved by project-owner direction on 2026-08-06: future packet promotions are authorized through
explicit packet authorization, Cinderfire and Red Dunes are the approved public display names, and
validated `world materialize` packets publish directly by default. Locked canon still requires a
separate human decision and no promotion is silent. The decision is recorded in
`content/seeds/aethryn/design/promotion_authorization.yaml`.

## Current gaps by required capability

| Capability | Current evidence | Gap |
| --- | --- | --- |
| Canon | `canon.py`, `test_canon.py` | No immutable locked fingerprint or leakage scan |
| Topology | `worldgraph.py`, `test_worldgraph.py` | No room-level hierarchy or reciprocal-exit audit |
| Seed compatibility | `seed.py`, runtime loaders | No packet compiler or sidecar provenance schema |
| Authored expansion | `room_batches.py`, batch tests | Prose-only; no system records or package digest |
| Generators | field, wildland, cave, underground, delve modules | Determinism is local, not package-wide |
| Settlements | settlement and authored town YAML | No required food, water, fuel, labor, waste, or rhythm contract |
| Ecology | creature records and biome generators | No habitat, energy, persistence, predator, or pressure validation |
| Economy | shop, item, recipe, quest seed data | No explicit flow model or inventory provenance validation |
| Dungeons | dungeon seed and delve grammar | No completeness validator for builder-authored dungeon specs |
| Publication | pure-authoring snapshot | No typed manifest, digest comparison, or restore command |
| Runtime safety | world assembly has no model call | Compiler contract needs an explicit no-model test |

## Smallest safe vertical slice

The first slice is Veridia, Greenhold, and its immediate hinterland. It should be a small connected
packet, not a room-count exercise:

- one civic water and waste room;
- one agricultural production room;
- one road threshold;
- one wilderness loop;
- one minor hazardous old-world site;
- one economic dependency from field production to the local shop;
- one ecological pressure linked to the damaged crop;
- one local civic dispute represented as a pressure, not a quest list;
- one reversible state record with an explicit publication and restore path.

The existing Greenhold authored town is the starting material. The compiler should add a namespaced
packet around it and preserve its current authored rooms, quests, NPCs, and items.

## Exact verification commands

Relevant focused checks:

```bash
FORGE_SEED=aethryn PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_canon.py tests/test_worldgraph.py tests/test_survey.py \
  tests/test_generation_contract.py tests/test_room_batches.py \
  tests/test_materialize_aethryn.py
FORGE_SEED=aethryn PYTHONPATH=. .venv/bin/python -m tools.world validate
FORGE_SEED=aethryn PYTHONPATH=. .venv/bin/python tools/validate_room_batches.py
```

Repository gates are intended to be:

```bash
make fix
make check
```

Reality audit result at the start of this implementation: the required `ruff` executable is not
available on the shell PATH, while `.venv/bin/python -m ruff` is available. The complete repository
lint and type gates also report pre-existing failures in unrelated dirty files. The full pytest run
has pre-existing failures and was interrupted at a gateway test. Those are not being relabeled as
compiler failures. Focused tests must be rerun after each implementation phase.

## Decisions for the next phases

1. Use frozen stdlib dataclasses and canonical JSON hashing for typed design records. This avoids a
   new runtime dependency and keeps the compiler offline.
2. Keep CodeForge seed YAML as the deployable runtime output. Design, economy, ecology, pressure,
   provenance, and state records travel in a sidecar package manifest until runtime loaders support
   them directly.
3. Treat `GenerationPacket` as an input specification, not a canon source. Its canon status is
   validated and cannot promote content without an explicit authorization field.
4. Compile to a staging package first. Publication copies a validated package into the configured
   room-batch location only after digest and graph checks pass. Restore uses the previous package
   recorded in the manifest.
5. Begin with the Veridia packet, then use the same packet schema for every later region. Do not
   generate the remaining room drops as part of this slice.
