# Aethryn: MMORPG Launch-World Build Plan

**North star (the Seed Scale Directive, `/home/josh/Projects/prompt`, 2026-07-26):** build aethryn
as the launch world of a *premium MMORPG* that comfortably holds ~500 concurrent players without
feeling crowded or empty. Optimize for long-term exploration, replayability, and **player
distribution**, not the smallest playable slice. *"Do not build a dungeon. Build a world."* Measure
success by how **alive, interconnected, explorable, and replayable** the world feels, never by room
count.

This is a **multi-session marathon.** This document is the resumable spine: any session picks up from
the Progress Tracker below. It complements, and does not replace, `docs/world/build_order.md` (the
original phase order) and the World Bible / Continental Atlas (the canon).

---

## World scale (one seed, demo to MMO)

Aethryn scales from a laptop/demo world to a **million-room MMO world** by a single env var, without
re-authoring the map. `CODEFORGE_WILD_SCALE` (default `1`) multiplies every wildlands region's
`trail_length` at load (`parts/world/wildlands.py`).

- **Shipped size (scale 1):** ~53,500 rooms, ~0.9 s boot, ~100 MB. Safe for CI and the free-tier
  demo, which stay at this size.
- **MMO scale (scale 19):** **~1,016,000 rooms**, ~22 s boot, **~1.9 GB** resident. Proven on the Pi
  (15 GB). Boot it with `make serve-mmo` (or `make serve-mmo SCALE=10` for a smaller MMO world).

Why env-gated, not baked into the seed: the always-on demo runs on a 512 MB host and CI fans the
suite across cores, so a 1.9 GB default would OOM both. The floor is the seed's authored size (scale
`< 1` is refused), so scaling only ever *grows* the world. Content **density** is separate from
scale: named guardians are capped per region (`_NOTABLE_CAP`), so a bigger world means more *land* to
populate, not a flooded bounty board. Populating that land to MMO density is the next campaign.

---

## Working method (every session, every increment)

- **Data-driven.** Content lives in `seeds/aethryn/*.yaml` (rooms/npcs/items/abilities/recipes/
  quests/zones/sets/spiral), validated by the loader gates. The world is data; the engine is genre-
  neutral. New engine capability only when data cannot express the need.
- **Tested + gated.** `make check` (ruff + mypy + pytest + coverage) green locally BEFORE any push.
  Branch -> PR -> CI green -> squash-merge -> sync main. Never merge red.
- **Pipelined, no idle.** Build the next increment while CI runs on the last; merge as CI clears.
  Commit each increment the moment `make check` is green (never `git reset --hard` over uncommitted
  work). Open each PR `--base main` only after its dependencies have merged.
- **Honest labels.** A zone is "production density" only when it truly meets the checklist below, not
  aspirationally. Flag engine features that touch persistence/architecture for Josh's go-ahead.

---

## Definition of "production density" (per major zone)

A zone is *done* for launch when a player could spend **many enjoyable hours** there and two players
leveling in it would have **noticeably different experiences**. Concretely, each major zone should
carry:

- [ ] **>= 2 distinct leveling grounds** at its band (so players disperse, no single correct spot)
- [ ] **>= 1 settlement / hub** with real life (trader, keeper, and ambient civilians)
- [ ] **>= 1 region-integrated dungeon**: multiple encounter spaces, a mini-boss gate, optional
      route or hidden room, lore, a meaningful reward, ties to a nearby quest
- [ ] **>= 2 gathering / resource nodes** (resettable), for the gathering playstyle
- [ ] **>= 1 hidden location / exploration secret** (a shrine, a cache, a viewpoint) with a reward
- [ ] **an elite / off-path area** with a prize above the main-path gear
- [ ] **quest density across verbs**: a main-arc beat + local side quests + a discovery + a gather/
      profession task + a bounty/repeatable + a hidden or environmental one
- [ ] **populated life**: civilians, wildlife, a traveler or rare visitor; rumors that surface content
- [ ] **readable lore** (a record/inscription) rooting the zone's history
- [ ] **fast-travel link**: a road, ferry, or hub connection so backtracking is not tedious
- [ ] **no repetitive filler**: every area has its own identity

---

## Zone list + level bands (the launch world)

| Zone | Band | Role |
|------|------|------|
| **Emberreach** (the cradle: coast, Reachwood, Ember-road, capital, Ashwastes, Cinderdeep mouth) | 1-30 | The LAUNCH ZONE - first thing 500 players see; the model for the rest |
| Quenchmere (drowned archipelago) | 18-30 | second continent, sea-crossing |
| Verdance (living jungle) | 22-32 | ecosystem zone |
| Rimefall (frozen north) | 40-52 | preserved golden-age zone |
| Kollforge (molten) | 50-62 | near-Forge zone |
| Sundered Sky (floating shards) | 60-72 | aerial zone |
| Cinderdeep (downward dungeon frontier) | 10 -> deep | the delve axis |
| The Forgeward Road (procedural overland frontier) | 43-300 | the endgame grind to the Forge |

---

## Progress tracker (update every session)

**Emberreach (launch zone)** - IN PROGRESS (Session 1). Baseline before the directive: a strong but
linear cradle. Added toward production density:
- [x] 2nd early leveling ground: the Tidecaves (sea-cave delve off the Saltstrand) - #446
- [x] wilderness sub-zone: the Deep Reachwood (deepwood + Thornmere grove + Forgotten Shrine) - #447
- [x] gathering node (resettable reachwood_sap in the Thornmere) - #447
- [x] hidden location: the Forgotten Shrine (elite keeper + treasure + lore) - #447
- [x] quest density: clear / discovery / gather quests for the new areas - #448
- [x] populated life: hunter, wildlife, fisher, pilgrim, elder (rumors) - #449
- [ ] a landmark / scenic viewpoint
- [ ] a bounty board / repeatable activity for the zone
- [ ] a second dungeon or ruin cluster in the Ashwastes
- [ ] within-zone fast-travel convenience (beyond the existing roads/ferry)
- [ ] final density pass (audit against the checklist above, close remaining gaps)

**Other zones** - each solid at baseline (a hub + a dungeon + gear + a questline + a boss). NOT YET
brought to MMO production density. Order after Emberreach is the model: Quenchmere -> Verdance ->
Rimefall -> Kollforge -> Sundered Sky, then the Cinderdeep and the Forgeward Road get their own passes.

---

## Session log

- **Session 1 (2026-07-26)** - kickoff. Reframed the content campaign to MMO scale. Began Emberreach
  production density (increments #446-#449 above). Goal: bring Emberreach to the full checklist as the
  model zone; leave the tracker current so Session 2 resumes cleanly.
