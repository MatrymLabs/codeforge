# Aethryn Design Schema Reference

The design schema is YAML-first and validated before compilation. The files under
`content/seeds/aethryn/design/` are design inputs, not a replacement for the CodeForge seed loader.

## Design files

| Path | Responsibility |
| --- | --- |
| `world_identity.yaml` | world id, level range, start, authority paths, status ladder |
| `universal_rules.yaml` | topology, map, runtime, status, publication, and state rules |
| `historical_ages.yaml` | generation-contract vocabulary, marked authoring-required |
| `terminology.yaml` | canonical terms and explicit aliases |
| `open_questions.yaml` | unresolved questions and rumor-only expression policy |
| `map_concordance.yaml` | poster labels, aliases, orientation, and topology authority |
| `regions/` | region design records |
| `settlements/` | settlement systems and dependencies |
| `dungeons/` | dungeon history, grammar, revelation, and aftermath |
| `ecosystems/` | habitat and recurrence records |
| `economies/` | explicit resource flows and shortages |
| `cultures/` | local cultural records and authoring gaps |
| `factions/` | local pressure and dispute records |
| `religions/` | local religious context, without resolving global questions |
| `militaries/` | local defense context and authoring gaps |
| `packets/` | deterministic compiler inputs |

## Typed model families

`aethryn_models.py` defines `WorldDesignSpec`, `RegionSpec`, `ZoneSpec`, `SettlementSpec`,
`DistrictSpec`, `NeighborhoodSpec`, `WildernessSpec`, `DungeonSpec`, `RoomSpec`, `ExitSpec`,
`NPCSpec`, `CreatureSpec`, `ItemSpec`, `ResourceNodeSpec`, `EconomyFlowSpec`, `EcologyFlowSpec`,
`QuestPressureSpec`, `WorldStateSpec`, `GenerationPacket`, `GenerationManifest`, and
`ValidationReport`.

Every generated record inherits or declares:

- stable id and display name;
- canon status;
- parent region and zone;
- source design ids;
- generation seed;
- generator name and version;
- provenance;
- content digest.

## Packet sections

Each packet declares identity and purpose, inherited constraints, a threat range, geography, climate,
architecture, culture, economy, ecology, required connections, required counts, state scope,
forbidden content, seed, generator identity, source design ids, and expected output paths. The
`records` mapping contains lists for settlements, districts, neighborhoods, wilderness, rooms, NPCs,
creatures, items, resource nodes, economy flows, ecology flows, quest pressures, state changes, and
dungeons.

## Mutation and state-gate contract

A `state_changes` record may declare `actions`. Each action requires `command`, `target`, `from`,
and `to`, with optional `aliases`, `required_item`, `consume_item`, `room_id`, `success_message`,
and `already_message`. `from` and `to` must both be values in the state's `reversible_values`.
`consume_item: true` requires `required_item` and removes one carried instance only after the state
transition succeeds.

A quest pressure may declare a `state_gate` with `key` and a non-empty `active_values` list. The key
must reference a state record in the same packet, and every active value must be allowed by that
state. The live adapter suppresses the pressure when the persisted state leaves those active values.

The runtime exposes structured `ActionOutcome` evidence with status `changed`, `already`,
`refused`, or `unavailable`, while the text command continues to return the player-facing message.

Unknown information is explicit. Use `unknown`, `intentionally_unresolved`, `authoring_required`,
`rumor_only`, or `not_yet_modeled`. Do not fill a required field with invented canon.
