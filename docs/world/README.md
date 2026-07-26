# The World Forge — Aethryn's AAA World Library

*The campaign to build a universe, not a game. This library is the design canon for Aethryn as a
persistent, handcrafted, AAA-scale world — enough content to support years of exploration,
progression, and expansion. It builds ON the core [`docs/world_bible.md`](../world_bible.md) (the
premise, cosmology, and the dual fiction/engine reading), which remains the load-bearing charter;
everything here deepens and extends it. Nothing here is hard-coded in Python — the world is data
(`seeds/*.yaml`), and the engine stays genre-neutral.*

> **Doctrine (read first).** Do not build a game. Build a place players remember years after they
> log out. Every location answers *why was this built, who built it, who holds it now, why come here,
> what happened, what stories emerge, what secrets remain.* Every room is intentionally handcrafted.
> The world existed long before the player arrived: players discover history, they do not create it.
> Original IP only — we capture what makes great RPG worlds unforgettable (layered history,
> morally-gray civilizations, ancient tech woven with mystery, dangerous wilds, ruined
> megastructures, rewarding curiosity), never their specifics.

## The one-paragraph pitch

Aethryn is a world that was **made, and remembers being made** — Forged from **Ember** (living
possibility) by the **First Forgers**, then broken by the **Unforging** when their masterwork, the
**First Seed**, was sundered. The forged supercontinent cracked into **Reaches** divided by the
cooling-seas; whole lands fell into the **Cinderdeep** below; the craft of making shattered across
the ages. Now, in the **Age of Rekindling**, ordinary people stumble back into fragments of the old
craft and become **Forgers** — makers whose works *stay*. The world can be rebuilt, or Unforged
again, and every player is both a hero and a small dangerous experiment in whether a broken world
should be handed the power to remake itself. The endgame is not to kill a final enemy; it is to run
the **Forgeward Road** east toward the **Forge** at the world's far heart and become a maker of
worlds, and to learn why the first makers stopped.

## Scale of the design

- **9 great regions of the world**: 7 continental **Reaches** on the Anvil's surface, plus the
  **Forgeward Road** (the overland frontier endgame running east) and the **Cinderdeep** (the
  descending dungeon frontier). Each Reach is designed to support its own RPG. See the [Continental Atlas](continental_atlas.md).
- **Thousands of handcrafted rooms** as the target; hundreds per major region. Room standards and a
  prioritized zone-by-zone build order in the [Build Order & Room Standards](build_order.md).
- **Dozens of factions**, **hundreds of creatures across believable ecosystems**, **dozens of jobs
  across cultural origins**, **multiple schools of magic**, **complete crafting professions**, a
  **living economy**, **hundreds of dungeons**, and **layered questlines** (main / regional / faction
  / guild / companion / hidden). Each has its own encyclopedia below.

## The deliverables (this library)

| # | Deliverable | File | Status |
|---|-------------|------|--------|
| 1 | World Bible (premise, pillars, dual reading) | [`../world_bible.md`](../world_bible.md) + this README | **canon** |
| 2 | Global History (eras, the deep timeline) | [`global_history.md`](global_history.md) | **authored** |
| 3 | Continental Atlas (the Reaches + planes) | [`continental_atlas.md`](continental_atlas.md) | **authored** |
| 4 | Kingdom Atlas (crowns, concords, republics) | `continental_atlas.md` §per-Reach + [`faction_encyclopedia.md`](faction_encyclopedia.md) | authored (folded) |
| 5 | Regional Atlas (zones within Reaches) | `continental_atlas.md` §per-Reach | authored (folded) |
| 6 | Settlement Encyclopedia (cities that live) | `continental_atlas.md` landmark cities + build order | seeded |
| 7 | Faction Encyclopedia | [`faction_encyclopedia.md`](faction_encyclopedia.md) | **authored** |
| 8 | NPC Encyclopedia (archetypes + named figures) | folded into factions/settlements | seeded |
| 9 | Bestiary (creatures, ecosystems, food chains) | [`bestiary.md`](bestiary.md) | **authored** |
| 10 | Job Encyclopedia | core in `docs/job_system.md`; cultural origins here | pointer |
| 11 | Spell / Magic Encyclopedia (schools of Forging) | [`magic_encyclopedia.md`](magic_encyclopedia.md) | **authored** |
| 12 | Crafting Encyclopedia (professions, materials) | core in `docs/world_bible.md` §17-18; expansion pending | pointer |
| 13 | Transportation Guide | [`build_order.md`](build_order.md) §travel | folded |
| 14 | Economy Guide | core in `docs/world_bible.md` §11; expansion pending | pointer |
| 15 | Dungeon Encyclopedia | [`bestiary.md`](bestiary.md) §lairs + build order | seeded |
| 16 | Quest Bible (layered structures) | [`build_order.md`](build_order.md) §quests | seeded |
| 17 | Legendary Item Catalog | [`magic_encyclopedia.md`](magic_encyclopedia.md) §relics | seeded |
| 18 | Cultural Encyclopedia | `continental_atlas.md` §per-Reach cultures | authored (folded) |
| 19 | Exploration Guide (rewarding curiosity) | [`build_order.md`](build_order.md) §exploration | folded |
| 20 | Endgame Content Roadmap | [`build_order.md`](build_order.md) §endgame | folded |
| 21 | Expansion Roadmap | [`build_order.md`](build_order.md) §expansion | folded |
| 22 | MUD Room Construction Standards | [`build_order.md`](build_order.md) §room-standards | **authored** |
| 23 | Zone-by-zone Build Order | [`build_order.md`](build_order.md) §build-order | **authored** |

**Status legend.** *canon* — the load-bearing charter; *authored* — a substantial design document
exists; *seeded* — the framework + first entries exist, ready to grow; *pointer* — the core lives in
an existing doc, expansion is queued. This is a multi-pass campaign: the foundation (history, atlas,
factions, bestiary, magic, build order, room standards) is laid; the enumerable encyclopedias
(settlements, NPCs, dungeons, quests, items, professions) grow entry-by-entry against it.

## How the world becomes the game

The world is designed *first*; the seeds follow. Each authored region here becomes a `seeds/aethryn/`
build (rooms, npcs, items, zones, quests) per the [Build Order](build_order.md). The flagship seed
**`aethryn`** is the first, playable slice of this universe — the Kindlands coast of Emberreach, the
Ember-road to the capital, the Reachwood, the Cooling-Sea, the Ashwastes, the Cinderdeep, and the
Forgeward Road. This library is the map for the decade of content that grows from it.
