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

## Security

- Threat model: the adversaries are hostile seed content (an NPC authored with negative, absurd, or missing combat stats) and a griefing player spamming rapid attacks. There is no network trust boundary here; the risk is malformed data and unsafe state, not an external attacker.
- Trust boundaries: combat stats enter ONLY through a validated seed record via the loader gate, never hard-coded and never player-supplied; the engine tick is the only door that mutates hit points (state is canonical, text is a projection).
- AuthN/AuthZ: attacking an NPC is an ordinary player action, so no rank gate applies; but resolution runs strictly through validated engine logic, and no player input can set or overwrite a stat directly.
- Failure modes: missing or invalid combat stats fail loud at the seed loader (never a silent default); a defeated player is handled by a safe respawn/fail-safe and never left in a broken state; self-attack and dead-NPC cases are explicit refusal tests; renderers report the exchange but never mutate hit points.
- Data classification: combat stats are non-sensitive game state; no secrets or PII are involved.

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
