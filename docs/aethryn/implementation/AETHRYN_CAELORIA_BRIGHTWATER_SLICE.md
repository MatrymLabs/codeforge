# Caeloria Brightwater River Ledger Slice

Packet: `caeloria_brightwater_river_ledger`

This is the next regional production slice after Greenhold and the Black Hollow threshold. It
uses existing Brightwater authored content: the Weir Market, Millrace, Licensing Hall, Old Sluice,
and Lower Weirs.

## Living mechanism

```text
meadowfoil gathering
        -> chandler provisions
        -> mill and river labor
        -> old sluice maintenance pressure
        -> licensing dispute over recovered infrastructure
        -> lower-weir creature danger
```

The packet deliberately does not inflate the room count. It compiles five existing authored rooms
with explicit hierarchy, economy, ecology, dungeon, pressure, state, and provenance records. Each
room replacement is intentional and preserves the authored Brightwater route.

## Canon posture

The slice is `AUTHORED_LOCAL` content under the locked Caeloria region and threat band. The old
sluice is described by material, geometry, behavior, input, output, failure mode, and local
interpretation. Its builders and exact age remain unresolved. The packet does not answer any global
question or change regional topology.

## Build command

```text
FORGE_SEED=aethryn PYTHONPATH=. .venv/bin/python -m tools.world materialize \
  content/seeds/aethryn/design/packets/caeloria_brightwater_river_ledger.yaml \
  --output content/seeds/aethryn/generated/caeloria_brightwater_river_ledger
```

The command validates, stages, publishes, and retains a prior active batch under
`.aethryn_rollbacks/` when one exists. Use `--stage-only` to defer publication.

## Deliberate limitation

NPC schedules, economy flows, ecology recurrence, and licensing pressure are validated sidecar
records and now appear as read-only room signals through `aethryn_runtime.py`. Full schedule-driven
movement, inventory depletion, production quantities, and population simulation remain later
mutation adapters. The declared `maintain sluice` mutation is the first local state transition.
