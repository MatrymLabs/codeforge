# Aethryn Master Lore and World Design Index

Status: working design index

Updated: 2026-08-06

Purpose: provide one place to find the files that define Aethryn's canon, map, regions, cities,
dungeons, stories, cultures, mechanics, and open design space.

This document is an index and orientation guide. The individual source files remain authoritative
for their own domains.

## How to use this document

Brainstorm in this order:

1. Confirm the current canon.
2. Choose a region from the map.
3. Choose a city, settlement, dungeon, or wilderness corridor.
4. Read the existing local files.
5. Add ideas as local details, rumors, conflicts, people, and places.
6. Convert approved ideas into authored YAML and room batches.

Do not begin with hundreds of rooms. Begin with the identity of the place and the reason a player
would remember it.

## Authority ladder

### Tier 1: Current canon

These files define the current Netharion and divine-strike version of Aethryn.

- `content/seeds/aethryn/canon.yaml`
  - Machine-checkable locked canon.
  - Names, regions, Seven Crowns, Netharion, the deliberate divine strike, and open mysteries.
- `docs/aethryn_lore_bible.md`
  - Readable companion to `canon.yaml`.
- `docs/aethryn_seed_reconciliation.md`
  - Explains the source hierarchy, canon tiers, built coverage, and remaining gaps.
- `content/seeds/aethryn/world.yaml`
  - Seed identity, title, spawn, level curve, and world metadata.
- `docs/aethryn/AETHRYN_FOUNDER_DECISIONS.yaml`
  - Open decisions reserved for Josh's judgment.

The external Coding Seed pack is identified by the reconciliation document as the originating
source. The supplied poster is also a visual topology source:

`/home/josh/Downloads/Matrym_Labs_Research_Archive_2026-08-02/a_highly_detailed_fantasy_world_map_poster_layout.png`

### Tier 2: Current machine topology

- `content/seeds/aethryn/world_graph.yaml`
  - Canonical region adjacency and sea relationships.
- `content/seeds/aethryn/settlements.yaml`
  - Map settlements and their level bands.
- `content/seeds/aethryn/dungeons.yaml`
  - Map dungeon mouths and level bands.
- `content/seeds/aethryn/zones.yaml`
  - Zone names, room hubs, level ranges, biomes, and reset behavior.
- `content/seeds/aethryn/waystones.yaml`
  - Fast-travel nodes for the fourteen regions.
- `content/seeds/aethryn/rooms.yaml`
  - Generated macro map and primary room graph.

The poster defines zone and landmark topology. It does not define every individual room exit.
Room manuscripts may therefore use local route inference while preserving the poster-level graph.

### Tier 3: Current authored world expansion

- `content/seeds/aethryn/fields.yaml`
  - Authored open-world field regions with rivers, roads, landmarks, and deterministic generation.
- `content/seeds/aethryn/wildlands.yaml`
  - Generated wilderness corridors between major places.
- `content/seeds/aethryn/underground.yaml`
  - Regional caves and deeper underzones.
- `content/seeds/aethryn/cave_families.yaml`
  - Reusable regional cave patterns.
- `content/seeds/aethryn/generation_contract.yaml`
  - Required fields and content rules for generated areas.
- `content/seeds/aethryn/room_batches/README.md`
  - Authoring contract for prose room drops.
- `content/seeds/aethryn/room_batches/*.yaml`
  - Authored room-batch content currently installed in the Seed.

## Regions and topology brainstorming

Use these files when deciding how a region feels, what it trades, what threatens it, and how it
connects to neighboring regions:

- `content/seeds/aethryn/world_graph.yaml`
- `content/seeds/aethryn/zones.yaml`
- `content/seeds/aethryn/settlements.yaml`
- `content/seeds/aethryn/dungeons.yaml`
- `content/seeds/aethryn/fields.yaml`
- `content/seeds/aethryn/wildlands.yaml`
- `content/seeds/aethryn/underground.yaml`
- `content/seeds/aethryn/waystones.yaml`
- `docs/aethryn/AETHRYN_EXIT_DIRECTION_POLICY.yaml`
- `docs/aethryn/AETHRYN_NAVIGATION_MIGRATION_PLAN.md`
- `docs/aethryn/AETHRYN_MAIN_ROOM_EXIT_AUDIT.yaml`
- `docs/world/veridia_field_walk.md`

The current major regions are:

- Veridia, levels 1-30
- Duskwood Vale, levels 20-50
- Caeloria, levels 30-60
- Eldryn Forest, levels 50-80
- Frostspire Peaks, levels 60-90
- Zhaar Desert, levels 80-130
- Xil'nath Jungle, levels 90-150
- Thalorin, levels 100-140
- Ashen Wastes, levels 120-170
- Korvash Highlands, levels 150-200
- The Shattered Isles, levels 180-230
- Skyward Spires, levels 200-250
- The Deepreach, levels 100-250
- The Voidscar, levels 250-300

## Cities, towns, and landmarks

The city and landmark interiors live under:

`content/seeds/aethryn/authored/`

Current authored files:

- `ashen_monoliths.yaml`
- `aurelian_city.yaml`
- `brightwater.yaml`
- `caeloria_city.yaml`
- `elderwatch.yaml`
- `eldryn_city.yaml`
- `frosthold.yaml`
- `greenhold.yaml`
- `lumengrotto.yaml`
- `moltenhold.yaml`
- `moonshade.yaml`
- `ravenwatch.yaml`
- `riverbend.yaml`
- `silverwatch.yaml`
- `stonefang_keep.yaml`
- `stonehelm.yaml`
- `stormreach.yaml`
- `sunmeadow.yaml`
- `sunscar_city.yaml`
- `twilight_grove.yaml`
- `veridia_wayhouse.yaml`
- `voidspire.yaml`
- `westgate.yaml`
- `wildgrowth.yaml`
- `zulkarak.yaml`

Use these files to brainstorm:

- Who founded the place?
- What does the settlement produce or protect?
- What does it fear?
- Who benefits from the current order?
- What old technology or divine remnant is hidden nearby?
- What local problem brings an outsider into the story?
- What would make the city recognizable after one sentence?

## Local stories and quest threads

All authored local story files live under:

`content/seeds/aethryn/quests/`

This directory includes quest threads for:

- Aurelian City
- Brightwater
- Caeloria City
- Elderwatch
- Eldryn City
- Frosthold
- Greenhold
- Lumengrotto
- Moltenhold
- Moonshade
- Ravenwatch
- Riverbend
- Silverwatch
- Stonefang Keep
- Stonehelm
- Stormreach
- Sunmeadow
- Sunscar City
- Twilight Grove
- Voidspire
- Westgate
- Wildgrowth
- Zulkarak
- The Veridia first road

Quest files are the best place to study existing local conflicts, rewards, factions, landmarks,
and recurring themes before inventing new ones.

## Culture, people, magic, and daily life

Seed data:

- `content/seeds/aethryn/npcs.yaml`
- `content/seeds/aethryn/items.yaml`
- `content/seeds/aethryn/jobs.yaml`
- `content/seeds/aethryn/abilities.yaml`
- `content/seeds/aethryn/professions.yaml`
- `content/seeds/aethryn/recipes.yaml`
- `content/seeds/aethryn/sets.yaml`
- `content/seeds/aethryn/campaign.yaml`
- `content/seeds/aethryn/quest.yaml`

Design references:

- `docs/world/faction_encyclopedia.md`
- `docs/world/magic_encyclopedia.md`
- `docs/world/global_history.md`
- `docs/world/bestiary.md`
- `docs/world/crafting_materials.md`
- `docs/world/professions.md`
- `docs/world/reputation.md`
- `docs/world/afflictions.md`
- `docs/world/boss_specials.md`

The faction and magic encyclopedia files under `docs/world/` are legacy fiction references unless
they agree with the current canon. The mechanical files remain useful for designing playable
content.

## Room prose and external content

Installed room batches:

- `content/seeds/aethryn/room_batches/duskwood_black_hollow_0010.yaml`
- `content/seeds/aethryn/room_batches/duskwood_vale_0011.yaml`
- `content/seeds/aethryn/room_batches/skyward_spires_0012.yaml`
- `content/seeds/aethryn/room_batches/veridia_massive_0013.yaml`

Additional installed or earlier batches:

- `content/seeds/aethryn/room_batches/veridia_content_batch_01.yaml`
- `content/seeds/aethryn/room_batches/veridia_content_batch_02.yaml`
- `content/seeds/aethryn/room_batches/caeloria_content_batch_0004.yaml`
- `content/seeds/aethryn/room_batches/voidscar_content_batch_0003.yaml`

External manuscripts and backlog material:

- `/home/josh/Downloads/Aethryn_Caeloria_Batch01_Massive.txt`
- `/home/josh/Downloads/Aethryn_Duskwood_BlackHollow_Batch01.txt`
- `/home/josh/Downloads/Aethryn_Veridia_Batch03_Density.txt`
- `/home/josh/Downloads/Aethryn_Voidscar_Level_250_300_Batch_01_500_Rooms.txt`
- `/home/josh/Downloads/Aethryn_Voidscar_Level_250_300_Batch_01_Manifest.csv`
- `/home/josh/Downloads/Aethryn_Voidscar_Level_250_300_Batch_01_README.txt`
- `/home/josh/Downloads/Matrym_Labs_Research_Archive_2026-08-02/Aethryn_Duskwood_Vale_Batch01.txt`
- `/home/josh/Downloads/Matrym_Labs_Research_Archive_2026-08-02/Aethryn_Skyward_Spires_Level_200_250_Massive_Room_Drop_01_500_Rooms.txt`
- `/home/josh/Downloads/Matrym_Labs_Research_Archive_2026-08-02/Aethryn_Veridia_Massive_Batch_MaxEffort.txt`

The imported room manuscripts preserve prose and visible objects, but their directions do not
always provide canonical destination IDs. The current importer records this as
`link_inference: ordered_route`.

## Design and brainstorming references

- `docs/aethryn/AETHRYN_DEEP_RESEARCH_REPORT.md`
  - Current implementation findings, navigation, character flow, jobs, and gaps.
- `docs/aethryn/AETHRYN_OPEN_RESEARCH_GAPS.yaml`
  - Unresolved evidence and design gaps.
- `docs/aethryn/AETHRYN_IMPLEMENTATION_ROADMAP.yaml`
  - Planned implementation sequence.
- `docs/aethryn/AETHRYN_ROOM_MOCKUPS.md`
  - Illustrative room and city presentation examples.
- `docs/aethryn/AETHRYN_PRESENTATION_STYLE_GUIDE.md`
  - Voice, layout, and presentation conventions.
- `docs/aethryn/AETHRYN_SOURCE_REGISTRY.yaml`
  - Research sources and design observations.
- `docs/aethryn/AETHRYN_COMPARISON_MATRICES.md`
  - Comparative design research.
- `docs/aethryn/AETHRYN_JOB_FAMILIES.yaml`
- `docs/aethryn/AETHRYN_JOB_INVENTORY.yaml`
- `docs/aethryn/AETHRYN_JOB_REQUIREMENTS.yaml`
- `docs/aethryn/AETHRYN_JOB_UNLOCK_GRAPH.yaml`
- `docs/aethryn/AETHRYN_SKILLS_AND_ABILITIES_SPEC.md`

## Legacy material

These files contain the earlier Forge, Ember, and Unforging version of Aethryn:

- `docs/world_bible.md`
- `docs/world/README.md`
- `docs/world/continental_atlas.md`
- `docs/world/faction_encyclopedia.md`
- `docs/world/global_history.md`
- `docs/world/magic_encyclopedia.md`
- `docs/world/build_order.md`

They are valuable for alternate ideas and provenance, but they are not current canon. Do not mix a
legacy fact into the Netharion canon without marking it as a new local idea, rumor, or deliberate
reconciliation decision.

## Brainstorming worksheet

For every new region, city, dungeon, or room cluster, capture:

- Name and region
- Level band
- Current canon facts it must respect
- Who built it
- Why it exists
- Who lives or works there now
- What resource, trade, or route sustains it
- What conflict is visible today
- What older historical layer remains underneath
- What technology, divine remnant, or scar is present
- What faction claims, protects, exploits, or fears it
- What the player can do there
- What rumor may be false
- What evidence would make the idea canon, local truth, or rumor
- Which existing file will receive the approved idea

## Recommended next artifact

The next design artifact should be a region workbook, not another raw room dump. Start with one
region from the poster, then record its cities, roads, dungeons, factions, historical layers,
open mysteries, and story seeds. Once that workbook is approved, compile its city interiors and room
batches into the existing Seed structure.
