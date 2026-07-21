# Areas and the beat-driven reset scheduler

*Group rooms into named areas over the flat world graph, and give each area a reset cadence that advances on the world beat, so a world can be organized into regions that refill over time. Studied clean-room from the Diku/Circle/tbaMUD family (license class B, LGPL); an original Python implementation that honors 'the tick is the only clock'.*

- **id:** `zone_scheduler`
- **status:** validated

## Requirements

1. Areas are seed data: a zones.yaml groups rooms by their existing labels (never vnums), validated by a fail-loud loader gate (member rooms exist, no room in two areas, known reset_mode, positive cadence).
2. The reset scheduler rides the world beat only (the same clock aggression.menace uses); no background thread and no second door into world state (architecture law 4).
3. An area comes due per its reset_mode (never / empty_only / always) and beats_between; due detection is a pure, read-only query.
4. Grouping is a projection: a room render gains an area banner; a room in no area renders exactly as before (state is canonical, text is a projection).
5. The scheduler is reachable through handle_command and pinned by an engine-tick wiring test.
6. The repopulation ACTION is a single deferred seam: no world mutation until the instancing and quest-permanent model is decided (the smallest safe slice first).

## Security

- Threat model: the adversary is malformed area data (a zone naming a missing room, claiming a room twice, an unknown reset_mode, or a non-positive cadence) and a resource-exhaustion risk from unbounded repopulation. There is no network trust boundary; the risk is bad data and unsafe state, not an external attacker.
- Trust boundaries: areas enter ONLY through a validated seed file via the load_zones gate, parsed with the same CSafeLoader + unique-key loader as every other seed pack; the engine tick is the only door that advances the schedule.
- AuthN/AuthZ: area grouping and the beat are ordinary world state, no rank gate applies; no player input can define or mutate an area.
- Failure modes: every malformed-area case fails loud at the loader (never a silent default); the repop action is a documented no-op seam, so no unsafe mutation can fire before the instancing / quest-permanent / felled-NPC model is decided; per-beat work is bounded by the declared areas, so a crafted world cannot turn the beat into a denial of service.
- Data classification: area membership and reset cadence are non-sensitive game state; no secrets or PII are involved.

## Tasks

- [ ] Add a Zone TypedDict, RESET_MODES, and a fail-loud load_zones gate to parts/seed.py.
- [ ] Add parts/zones.py: grouping queries + a beat-driven scheduler that rides the world beat.
- [ ] Wire an area banner into render_scene and tick_zones into handle_command.
- [ ] Ship real areas for the flagship seed (seeds/aethryn/zones.yaml).
- [ ] File the zone-scheduler Hardware Card with clean-room provenance (catalog/parts.yaml).
- [ ] DEFERRED: land the repop action once object instancing, a resettable-vs-quest-permanent model, and the felled-NPC decision are resolved by Josh.

## Stack

- **engine:** custom Python tick (handle_command); the beat is the only clock
- **content:** YAML seed records (zones.yaml), fail-loud loader gate
- **provenance:** clean-room from the Diku family (license class B, LGPL); original Python
- **tests:** pytest twin + engine-tick wiring test (tests/test_zones.py)
