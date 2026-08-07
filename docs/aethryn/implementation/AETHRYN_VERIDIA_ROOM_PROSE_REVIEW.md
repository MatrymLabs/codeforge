# Veridia Room Prose Review

This review records ten rooms rendered from the compiler-produced packets. The examples use the
current text-client template. Runtime signals are structured projections and are shown separately
from static room prose.

## Provenance register

| Room | Category | Packet | Seed | Generator |
| --- | --- | --- | ---: | --- |
| `greenhold` | city | `veridia_greenhold_living_slice` | 41017 | `aethryn_world_compiler 1.0.0` |
| `veridia_living_civic_gate` | city civic edge | `veridia_greenhold_living_slice` | 41017 | `aethryn_world_compiler 1.0.0` |
| `veridia_living_farmstead` | agriculture and economy | `veridia_greenhold_living_slice` | 41017 | `aethryn_world_compiler 1.0.0` |
| `brightwater_millrace` | industrial economy | `caeloria_brightwater_river_ledger` | 63041 | `aethryn_world_compiler 1.0.0` |
| `veridia_living_wild_loop` | wilderness | `veridia_greenhold_living_slice` | 41017 | `aethryn_world_compiler 1.0.0` |
| `duskwood_hollow_root_loop` | wilderness | `duskwood_black_hollow_threshold` | 52023 | `aethryn_world_compiler 1.0.0` |
| `veridia_living_road_threshold` | road threshold | `veridia_greenhold_living_slice` | 41017 | `aethryn_world_compiler 1.0.0` |
| `the_black_hollow` | hazardous threshold | `duskwood_black_hollow_threshold` | 52023 | `aethryn_world_compiler 1.0.0` |
| `duskwood_hollow_warden_camp` | service and recovery | `duskwood_black_hollow_threshold` | 52023 | `aethryn_world_compiler 1.0.0` |
| `brightwater_sluice` | dungeon-like hazardous site | `caeloria_brightwater_river_ledger` | 63041 | `aethryn_world_compiler 1.0.0` |

All ten records are `GENERATED_LOCAL`, carry `presentation_version: aethryn-room-v1`, and include
the packet id, source design ids, generator version, and content digest in the materialized batch.

## Representative rendered rooms

### 1. Greenhold, city

```text
Veridia - Greenhold

DESCRIPTION
  Greenhold gathers market, memory, and road traffic around a well while the working edge opens south toward fields, drainage, and an old water threshold.

EXITS
  south - Greenhold Civic Edge
```

The verbose form adds packet-derived Veridia, timber and riverstone, and local terrain context.

### 2. Greenhold Civic Edge, city civic room

```text
Veridia - Greenhold Civic Edge

DESCRIPTION
  The town wall gives way to a maintained civic edge where a public notice, a drainage map, and a low stone channel explain how Greenhold keeps people and water moving together.

EXITS
  north - Greenhold
  east - Cistern Court
  south - South Cartway Threshold
```

The room supports civic maintenance and makes the water dependency visible through a structured
runtime pressure.

### 3. Alder Farmstead, agricultural economy

```text
Veridia - Alder Farmstead

DESCRIPTION
  A small barley holding sits behind a split rail fence, with a hand mill, drying rack, and meadowfoil baskets ready for the trader if the damaged rows can be kept productive.

POINTS OF INTEREST
  meadowfoil margin (examine, gather)
  damaged barley rows (examine, gather)

EXITS
  west - Alder Farm Lane
```

The two interactive resources are structured records, not nouns trapped in the paragraph.

### 4. The Millrace, industrial economy

```text
Caeloria - The Millrace

DESCRIPTION
  Turning wheels drive water through narrow races while meadowfoil grows along wet piling, making the same bank useful to gatherers, millers, wardens, and whatever follows the current.

POINTS OF INTEREST
  riverbank meadowfoil (examine, gather)

EXITS
  down - The Old Sluice
  west - The Lower Weirs
```

The long form adds riverstone construction and the cold old sluice without naming the unknown
mechanism as magic.

### 5. Hedgerow Loop, wilderness

```text
Veridia - Hedgerow Loop

DESCRIPTION
  The path bends through wet grass and thorn hedges in a deliberate loop, passing forage, torn barley stems, and tracks too broad for the foxes that usually keep this edge balanced.

EXITS
  west - South Cartway Threshold
  east - The Shallow Service Hollow
```

The current tracks and encounter are emitted under structured world signals, not baked into the
description.

### 6. Rootbound Loop, wilderness

```text
Duskwood Vale - Rootbound Loop

DESCRIPTION
  The path bends around exposed roots and a line of old warden stakes, closing a safe loop while fresh tracks show that the forest is using the boundary for its own purposes.

EXITS
  north - Warden Lantern Camp
  east - Mirror Pool Margin
```

The room identity comes from root exposure, warden stakes, and a loop purpose. It is not a filler
corridor.

### 7. South Cartway Threshold, road

```text
Veridia - South Cartway Threshold

DESCRIPTION
  The cartway leaves Greenhold between low hedges, a repaired milestone, and a ditch that carries both rain and the town's arguments about who must clear it.

EXITS
  north - Greenhold Civic Edge
  east - Hedgerow Loop
  south - Alder Farm Lane
```

This is the minimal connector example. It has a named road identity, a maintenance purpose, local
materials, and four meaningful connections.

### 8. The Black Hollow, hazardous threshold

```text
Duskwood Vale - The Black Hollow

DESCRIPTION
  The Black Hollow waits beneath its split oak while old path marks, a warden lantern, and a new threshold east make the choice to enter or return legible.

EXITS
  down - The Black Hollow, the threshold
  threshold - Hollowward Threshold
```

The room communicates a decision point without resolving any global question about the Hollow.

### 9. Warden Lantern Camp, service room

```text
Duskwood Vale - Warden Lantern Camp

DESCRIPTION
  A rain-dark camp shelters spare lanterns, route stakes, and a warden's record board carrying route warnings, duty names, and a maintenance argument.

CONDITIONS
  The warden lantern burns dim along the return markers.

POINTS OF INTEREST
  the warden lantern salve (examine, take)
```

The lantern condition is structured state. The salve has a stable item id and material provenance.

### 10. The Old Sluice, hazardous site

```text
Caeloria - The Old Sluice

DESCRIPTION
  A flooded chamber older than the mills holds pale channels and seized flow-gates that once ruled the river without a hand, while a quiet mechanical pulse waits behind the water.

CONDITIONS
  The buried flow-gates remain ticking behind the flooded channels.

POINTS OF INTEREST
  a warden's sluice-token (examine, take)

EXITS
  up - The Millrace
```

The ancient technology is described by material, geometry, behavior, input, output, and failure
mode in the structured item record. The prose leaves the degree of understanding open.

## Minimal and verbose rendering checks

Minimal client rendering uses ordinary `look` and retains only the area title, short description,
structured non-empty sections, and exits. Verbose rendering uses `look verbose` and selects
`long_description` while retaining the same navigation contract. Both projections are generated
from the same materialized room payload.

Exact review commands:

```bash
FORGE_SEED=aethryn PYTHONPATH=. .venv/bin/python - <<'PY'
from kernel.world import world
print(world.render_room("veridia_living_farmstead"))
print(world.render_room("veridia_living_farmstead", verbose=True))
PY
```

The source batch, generated sidecars, similarity report, and rollback copy are the evidence bundle
for this review.

