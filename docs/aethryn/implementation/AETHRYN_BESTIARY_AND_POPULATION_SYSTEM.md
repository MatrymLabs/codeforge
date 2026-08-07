# Aethryn Bestiary and Population System

Status: implemented as a deterministic, offline packet sidecar. The existing world compiler,
room batches, NPC registry, combat engine, and materialization boundary remain the owners of
individual rooms and individual combatants.

## Terminology

`CreatureSpec` says what a creature, construct, undead, artificial organism, or anomaly is.
`PopulationProfile` says where an archetype can occur and how large its aggregate population may
be. `SpawnPool` supplies bounded reset and depletion limits. `RoamingRoute` and `MigrationRule`
keep movement inside a declared route. `EncounterGroupSpec` describes a related formation.
`CrowdSpec` represents many civilians or workers without creating persistent NPC objects.
`AmbientPresenceSpec` is an environmental or collective signal. `PopulationState` and
`PopulationManifest` are aggregate, deterministic state; they never contain a hidden NPC list.

The five presence layers are environmental evidence, ambient population, individual occupants,
roaming groups, and rare presences. An empty room is valid. Density is assessed from profiles,
crowds, routes, and evidence at zone/region scale rather than by requiring an occupant in each
room.

## Data models and authoring

Packet records use these kinds:

```yaml
creatures: []             # legacy-compatible creature rows / CreatureSpec data
population_profiles: []   # region, zone, habitat, rooms, caps, schedules, probabilities
spawn_pools: []
roaming_routes: []
migration_rules: []
encounter_groups: []      # pack, herd, flock, school, swarm, patrol, caravan, work_crew, ...
crowd_specs: []
ambient_presence: []
```

Creature rows carry stable identity, presentation text, keywords, canon status, region/climate,
habitat, behavior, intelligence, disposition, social organization, activity/movement, food or
operating input, threats/resources, recurrence, ecological/social role, civilization relationship,
combat role, abilities, defenses, retreat/pursuit/assistance, loot/crafting outputs, rarity, and
packet provenance. Biological rows declare habitat, food, and reproduction. Constructs, undead,
artificial organisms, and anomalies use an operating input and an explicit manufacture, summoning,
persistence, or recurrence mechanism instead of forced biological fields.

All generated records inherit packet seed, generator name/version, source design ids, authority
status, and a content digest in the compiled `records.yaml` sidecar. New content defaults to
`GENERATED_LOCAL` or `AUTHORED_LOCAL`; no population record may promote itself into canon.

## Population profiles and ecology validation

Profiles declare candidate rooms, allowed/forbidden room types, minimum/maximum/carrying capacity,
reset, depletion, recovery, time/season/weather/state gates, player-pressure effects, migration,
rarity, direct-presence probability, ambient-evidence probability, hostile-presence probability,
and provenance. Validation rejects unknown rooms, incompatible caps, invalid probabilities,
unbounded routes, habitat conflicts, orphaned group members, and missing food/energy or recurrence.

The aggregate simulator uses a stable hash of packet seed, record id, tick, and generator version.
It caps all populations and can persist a depleted count through `PopulationStateStore`, where the
declared recovery rule restores it. `simulate_population` never calls an LLM and never instantiates
an NPC. Rare and legendary populations remain explicit records with low or state-gated presence.

## Crowds and groups

Crowds define ranges, role composition, schedules, density states, collective activity, mood,
danger response, dispersal, representative NPCs, and accessibility text. The renderer exposes one
collective signal while named or mechanically important representatives remain ordinary NPCs.

Encounter groups define composition, size, leader, formation, cohesion, aggression, assistance,
pursuit, retreat, casualty/leader-loss response, reinforcement, loot ownership, and recurrence.
Groups are rejected when their members are not declared; they are not assembled from unrelated
creatures.

## Runtime and generation packets

The compiler preserves all population record kinds in the compiled `records.yaml`, adds population,
crowd, and evidence references to the room batch, and stamps the same provenance as rooms and
items. The read-only runtime adapter projects crowd activity, evidence, bounded movement, and
aggregate population signals into `WORLD SIGNALS`. Individual occupants still flow through the
existing NPC registry and combat engine. Runtime startup reads static sidecars only; it never calls
Codex, an LLM, or an external content service.

Pure authoring materialization also writes `population.yaml` when compiled population sidecars are
available, so the materialized Seed contains the same population content rather than rebuilding it
at startup.

## Veridia example

`veridia_greenhold_living_slice.yaml` contains Greenhold civilian market traffic, field and ditch
work crews, a domesticated/local livestock profile, a recoverable field-rabbit prey population,
displaced boar pressure, bounded rabbit/boar spawn pools, a road patrol route, a seasonal boar
shift, a boar pack and work crew formation, a market crowd, and tracks/spoor/sounds/movement signs.
The boar output references `raw_hide` and `boar_tusk` for crafting/economic use. The slice leaves
the cistern court and work road empty at some ticks while still projecting nearby life.

## Builder commands

From the repository root:

```text
python -m tools.world bestiary-check [packet]
python -m tools.world population-check [packet]
python -m tools.world inspect-creature <id> [packet]
python -m tools.world inspect-population <id> [packet]
python -m tools.world population-map <zone> [packet]
python -m tools.world encounter-preview <group-id> [packet]
python -m tools.world simulate-population <zone> --ticks <n> --seed <seed> [packet]
python -m tools.world find-overpopulated [packet]
python -m tools.world find-empty-zones [packet]
python -m tools.world find-habitat-conflicts [packet]
python -m tools.world find-orphaned-creatures [packet]
```

The commands default to the Veridia packet when a packet argument is omitted. `compile-packet` and
`materialize` remain the publication boundary and emit the population records with the existing
manifest and validation report.

## Tests and verification

Focused verification used during implementation:

```text
python -m tools.world validate-packet content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml
python -m tools.world population-check content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml
python -m tools.world simulate-population veridia_zone --ticks 4 --seed 41017 content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml
python -m tools.world encounter-preview greenhold_displaced_boar_pair content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml
```

Expected result: the packet and population checks report `CLEAN`; simulation reports a stable
manifest digest; encounter preview reports a bounded 1–2 member pack. The repository test command
for the final implementation is:

```text
pytest -q tests/test_aethryn_population.py tests/test_aethryn_world_compiler.py tests/test_aethryn_runtime.py tests/test_materialize_aethryn.py
pytest -q
```

Results from this implementation:

- The focused population/compiler/runtime/materialization command passed: `37 passed`.
- The broader Aethryn, legacy bestiary, wildlands, roaming, zones, NPC, and combat command passed: `258 passed`.
- Ruff passed for all changed population/compiler/runtime/materialization files.
- The scale-1 pure-authoring command was started with the documented `PYTHONPATH=.` prefix but was stopped after the existing large world assembly exceeded the interactive verification window; the population sidecar collector itself reported 7 creature records and 16 population records from the compiled packages.
