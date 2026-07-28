# Quest Archetype Library

The world of Aethryn grows its quests from **generators**, not hand-placed one-offs. A generator
takes the world's own content (its zones, biomes, creatures, foes, settlements, dungeons, materials)
and produces many quests of one shape. This document is the **library** those generators belong to:
the catalog of archetypes, what each is for, and the roadmap of the ones still to build.

The code catalog lives in `parts/world/quest_archetypes.py` (MOD-04.095). Each archetype there
carries the same design fields listed below, beside the predicate that recognises a live quest as a
member, so the doc and the code cannot drift. `classify(quest_id)` maps any quest to its archetype,
and the test twin proves **every** quest a booted world posts classifies to exactly one archetype
(or `authored`) -- no archetype ever ships uncatalogued.

## Design principles

- **Data-driven, not hardcoded.** A quest is a `QuestSpec` (states, steps, triggers, labels); a
  generator emits them from world data. A new archetype is a new generator plus a catalog record.
- **Volume comes from distinct targets, never duplicate IDs.** "Do N here" quests are **scoped to
  their zone** (`cull.scope_key`) so a kill/harvest only advances the board where it happened. Two
  towns never share one lockstep quest.
- **No counter engine.** "Do N" is modeled as an N-step chain -- one step per event -- so the run
  state *is* the tally and it persists like any quest.
- **Authored where it matters, generated for volume.** Prototype/flagship content is hand-written;
  scale is reached by validated archetypes. The two coexist; `classify` returns `authored` for the
  hand-written arcs.
- **Scale with deployment.** The same generators fill a 50-room demo or a million-room world; the
  count follows the world's zones/foes/materials, not a fixed list.

## Shipped archetypes

| Key | Name | Loop | Scope (volume) | Replay |
| --- | --- | --- | --- | --- |
| `spine` | The Main Road | Arrive in each zone in level order | the whole zone set | campaign, once |
| `storyline` | Zone Tale | Reach the dungeon, slay its warden, bear word home | each town+dungeon zone | one-shot per zone |
| `dungeon_crawl` | Dungeon Descent | Cross the mouth, reach the deepest chamber | each dungeon | one-shot per dungeon |
| `bounty` | Hunt Contract | Fell a named foe | every named foe | one-shot per foe |
| `cull` | Cull Contract | Fell N of a creature type in a zone | zone x type x count-tier | repeatable-feeling |
| `forage` | Forage Contract | Gather N of a material in a zone | zone x material x count-tier | repeatable-feeling |
| `errand` | Travel Errand | Travel to a destination | each settlement | one-shot per settlement |
| `delivery` | Courier Delivery | Take a parcel in town A, hand it over in town B | each settlement → partner | one-shot per settlement |

Each record in the code carries **purpose, narrative role, gameplay loop, success condition,
rewards, replay value, and scope** -- read `CATALOG` in the module for the full text.

## The Zone Story Framework

Every zone already carries its story across six generators -- a tale (`storyline`), a dungeon and its
named `warden`, a surface `landmark`, a depths `inscription`, and a board of `cull` / `forage`
contracts. `parts/world/zone_story.py` (MOD-04.098) is the framework that gathers those pieces from
the **live world** into one `ZoneStory` and renders a dossier -- the history, dangers, and
opportunities of a place at a glance. It is read-only and derived: a zone's story is exactly the sum
of its filed content, never a second source of truth.

Players read it with the **`region`** verb (CMD-04.092), which shows the dossier of the zone they
stand in. The completeness test pins that a dungeon-bearing zone reports its full depths (a warden
implies its inscription). This is where the campaign's Part II ("every zone should possess...") is
made legible and checkable; the still-missing pieces (supporting arcs, faction conflicts, local
mysteries, long-term consequences) hang off this framework as they land.

## Roadmap (archetypes still to build)

Grouped by the machinery they need. Each becomes a new generator + a catalog record, expanding the
existing systems (never replacing canonical content).

**Reuse today's machinery (kill / gather / travel / on_enter chains):**
- Cull-by-kin -- SHIPPED (culls name each class AND its kin; see the cull row's scope)
- Delivery -- SHIPPED (the `delivery` row above)
- Dungeon Crawl -- SHIPPED (the `dungeon_crawl` row above)
- Collection (bring N of a dropped item), Trade
- Elite Hunt (a tougher named target)
- Treasure Hunt / Treasure Mapping (a placed cache at one of several sites)

**Need new triggers or light systems:**
- Escort / Defense (protect an NPC or a place over time)
- Investigation / Mystery / Criminal Investigation (gather clues, reach a verdict)
- Puzzle, Stealth, Assassination, Rescue, Survival
- Profession Progression, Reputation, Achievement, Repeatable Daily / Weekly

**Need the world-simulation layer (factions, world state, season, weather):**
- Faction Story, Guild Story, Political Intrigue, Diplomacy / Negotiation
- Town Reconstruction, Settlement Growth, Economic Recovery
- Research Expedition, Archaeology, Ancient Ruins, Lost Civilization, Legendary Artifact
- Monster Ecology, Environmental Disaster, Seasonal Festival, Time-Limited Event
- Random Encounter, Emergent World Event, World Boss

## Adding an archetype

1. Write a generator in `parts/world/<name>.py`: a pure function from world data to a list of
   `QuestSpec`, with an `is_<name>(quest_id)` predicate and (for "do N here") a zone-scoped trigger.
2. If it needs a new world-event trigger, add it to `seed.QuestStep` and `quest._TRIGGER_KEYS`, and
   fire it from the action that should advance it (combat, gather, movement, ...).
3. Register it in `world.py` (fold it into the engine after the world is assembled).
4. Add a record to `CATALOG` in `parts/world/quest_archetypes.py` and a row above here.
5. File its MOD designation, add it to the world-boundary closure, and write its test twin.

The completeness test then guarantees the new archetype's quests are recognised -- and that nothing
ships outside the library.
