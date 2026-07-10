# NPCs that fight back

*Turn the training dummy's one-sided combat into a real exchange: an NPC can strike back, so a fight is a loop of blows, not a single command.*

- **id:** `npc_combat`
- **status:** draft

## Requirements

1. An NPC carries combat stats (hit points, attack, defence) derived from its seed record, never hard-coded.
2. Attacking an NPC triggers a counter-attack in the same tick, resolved by validated engine logic (state is canonical).
3. Combat text is a projection: renderers report the exchange but never mutate hit points.
4. A defeated player is handled safely (respawn or fail-safe), never left in a broken state.
5. The whole loop is reachable through handle_command and pinned by an engine-tick test.

## Tasks

- [ ] Extend the NPC seed schema with optional combat stats and a loader gate that fails loud.
- [ ] Add a resolve_exchange(attacker, defender) pure function with acceptance and refusal tests.
- [ ] Wire the counter-attack into the existing attack verb in the tick.
- [ ] Add hostile-case tests: dead NPC, missing stats, self-attack.
- [ ] Document the combat loop and file it in the Classification Registry.

## Stack

- **engine:** custom Python tick (handle_command)
- **content:** YAML seed records
- **persistence:** derive-don't-store (stats recompute on restore)
- **tests:** pytest twin + engine-tick reachability test
