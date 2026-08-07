# Duskwood Black Hollow Threshold Slice

Packet: `duskwood_black_hollow_threshold`

This is the next restrained production slice after Greenhold. It extends the existing Black Hollow
room with a Ravenwatch boundary route, a warden camp, a fernshade gathering margin, a connected
forest loop, a mirror pool, and a shallow buried return gate.

## Living mechanism

```text
fernshade gathering
        -> lantern salve shortage
        -> dim return markers
        -> creature pressure at the route
        -> warden access dispute
        -> maintain lantern
        -> lit return markers and resolved shortage
```

The packet adds 7 rooms and preserves the existing Black Hollow exits. The room batch is sequence
15, so it overlays the earlier Black Hollow threshold only where explicitly declared and remains
ordinary CodeForge room-batch data.

The sidecar defines one local settlement edge, one district, two neighborhoods, one wilderness
record, two NPC roles, two creature records, two notable objects, one resource node, two economy
flows, two ecology flows, two quest pressures, one dungeon record, and one reversible lantern state.

## Canon posture

The slice is `AUTHORED_LOCAL`. It uses the locked Duskwood Vale region and threat band without
altering either. It preserves the existing Black Hollow and leaves global divine, Netharion, and
superseded-metaphysics questions unresolved. The buried return marker is described by material,
geometry, behavior, input, output, failure mode, local interpretation, and understanding level.

## Runtime proof

- packet validation passes before compilation;
- compilation is deterministic and emits a digest and provenance records;
- direct materialization publishes the room batch and retains any prior artifact;
- the route has reciprocal exits and a return loop;
- the shared Aethryn item registry places one authored salve in Ravenwatch for transport to the
  compiled warden camp;
- `maintain lantern` refuses without the salve, then persists the lantern state and projects the lit
  return markers into room text;
- the state-gated shortage signal disappears after the lantern is relit;
- ecology, economy, and pressure records remain explicit sidecar data until their runtime adapters
  are added.

## Build command

```text
FORGE_SEED=aethryn PYTHONPATH=. .venv/bin/python -m tools.world materialize \
  content/seeds/aethryn/design/packets/duskwood_black_hollow_threshold.yaml \
  --output content/seeds/aethryn/generated/duskwood_black_hollow_threshold
```

Use `--stage-only` when publication is intentionally deferred. The normal command publishes after
validation, while the packet's explicit authorization and the existing canon gates remain required.
