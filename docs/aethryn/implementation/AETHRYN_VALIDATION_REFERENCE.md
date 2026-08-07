# Aethryn Validation Reference

The validator returns a verdict and actionable issues. Each issue contains category, code, path,
message, authority, and corrective action.

## Categories

- `CANON`: locked names, region bands, status promotion, Divine Strike, Netharion, open questions,
  and superseded metaphysics.
- `HIERARCHY`: region, zone, settlement or wilderness, district or neighborhood, and room ownership.
- `GEOGRAPHY`: supported local exit tokens, known targets, and reciprocal exits where required.
- `ROOM_PURPOSE`: a meaningful room function and enough local description.
- `SETTLEMENT`: population, government, food, water, fuel, labor, waste, economy, architecture,
  culture, services, connections, conflict, and daily rhythm.
- `ECOLOGY`: habitat, energy, predators, pressure, recurrence, season, role, civilization relation,
  and persistence reason.
- `ECONOMY`: source, sink, resource, purpose, transport, shortage or surplus, and inventory
  provenance.
- `DUNGEON`: builder, purpose, historical layer, failure, occupants, reclamation reason, entrance,
  grammar, gameplay, revelation, aftermath, and state potential.
- `STATE`: reversible state values, action fields, item-consumption rules, and state-gated pressure
  references.
- `PROVENANCE`: stable ids, display names, source design ids, statuses, generator identity, and
  inherited metadata.
- `DETERMINISM`: non-negative seed and generator identity.
- `PACKET`: declared record counts and packet shape.

## Map checks

`map_concordance.yaml` must cover all fourteen canon regions and must name
`content/seeds/aethryn/world_graph.yaml` as the topology source. The validator records that the
poster is orientation only, that decorative routes are not exits, and that the Deepreach is an
underground diagrammatic inset.

## Current runtime compatibility limit

Room topology is checked and emitted into existing CodeForge room batches. Rich records are validated
and preserved in the package sidecar. Their future runtime behavior requires explicit adapters. The
validator does not claim schedules, economy simulation, ecology recurrence, or state changes are
already active runtime mechanics merely because their design records exist.

## State mutation findings

State findings identify the packet path and the corrective contract. Common codes include
`invalid_actions`, `incomplete_action`, `action_value_outside_schema`, `invalid_consume_item`,
`consume_without_item`, `invalid_state_gate`, `unknown_state_gate_key`, and
`gate_value_outside_schema`.
