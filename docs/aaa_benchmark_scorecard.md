# AAA MMORPG Benchmark Scorecard: CodeForge and Aethryn

**A living quantitative engineering specification.** This document benchmarks the CodeForge engine
and its flagship world, Aethryn, against professionally engineered MMORPGs and historical MUDs, and
turns every subsystem into measurable development targets (prototype, alpha, launch, five year).

It is an *engineering* scorecard, not a design doc. It answers one question per subsystem: *what
measurable amount of this must exist before Aethryn can legitimately be called a flagship text
MMORPG?*

---

## How to read this (method and honesty)

This ship runs on one law: **no claim without correspondence.** That law shapes how every cell here
is sourced, and every cell is labelled with which kind it is:

| Kind | Meaning | How it is trusted |
|------|---------|-------------------|
| **Measured** | Counted from the repo right now | Reproduced by `python tools/census.py` (content) or the exact command noted (engine). High confidence by construction. |
| **Cited benchmark** | An industry value with an authoritative source | Filled in the research passes (below); each carries a source and a confidence level. |
| **Engineering estimate** | A target *we* set, not a fact we claim | Clearly flagged, with the assumption stated. Never presented as measured or cited. |
| **Pending** | Not yet researched | Marked `[Pass 2]` etc. Left visible, never faked, never blank-and-forgotten. |

**Staging (why the benchmark columns are not all filled yet).** The prompt that commissioned this
forbids inventing numbers. So this was built evidence first: **Slice 1 (this commit)** establishes
the full subsystem scaffold and fills every *current-status* column with a measured count, plus
proposes prototype and alpha targets as flagged engineering estimates. The *AAA benchmark* and
*historical MUD benchmark* columns are filled in cited research passes (see
[Research roadmap](#research-roadmap)), so that when a benchmark number appears here it arrives with
a source, not a guess.

**Reproduce the current column.** All Aethryn content counts below come from:

```
python tools/census.py
```

Engine metrics use the command noted at each row (for example, test count is
`pytest --collect-only -q | tail -1`). Census taken at the commit that introduced this file.

---

## Executive dashboard

### Estimated completion (engineering estimate, Low confidence)

"Percent complete versus a AAA MMORPG" is inherently fuzzy: it depends whether the yardstick is a
graphical AAA title, a commercial flagship *text* MUD, or a playable prototype. A single number
would mislead, so the estimate is split by yardstick and by dimension, and every figure here is a
**Low-confidence engineering estimate**, to be tightened once the benchmark columns are cited.

| Dimension | vs. AAA graphical MMORPG | vs. flagship commercial text MUD | Basis (measured) |
|-----------|--------------------------|----------------------------------|------------------|
| **Engine / architecture** | ~45% | ~70% | Pure-function tick, 3-table persistence, 215 modules, a large CI-gated suite (count via `pytest --collect-only`), 7 native-accelerator organs. Mature core; missing distributed/sharded serving. |
| **Combat systems** | ~30% | ~55% | 63 abilities, 10 damage types, boss phases + telegraphed specials + afflictions. Solo-vs-NPC only; no party/raid/group. |
| **Content scale (world)** | ~15% | ~40% | ~26,800 rooms at default scale (procedural), 45 settlements, 16 dungeons. Authored depth thin (75 hand rooms, 7 authored quests). |
| **Content scale (items/NPCs)** | ~10% | ~35% | 180 items, 75 authored NPCs + procedural guardians, 38 recipes. Well below launch density. |
| **Progression / player systems** | ~35% | ~60% | 31 jobs, 6 professions, 4 Orders, level cap 255, ember-coin currency. Broad skeleton, shallow per-system depth. |
| **Social / multiplayer** | ~8% | ~20% | Chat channels exist. No guilds, mail, friends, party, trade, auction, or housing. **Largest gap.** |
| **Economy** | ~12% | ~30% | Tiered currency, shops, crafting sinks. No player market, auction, or macro sinks/faucets balancing. |
| **World simulation** | ~30% | ~55% | Weather, seasons, day/night, respawn policies, dynamic spawns, zone resets. No NPC schedules or faction war. |
| **Live ops / tooling** | ~20% | ~40% | CI, security gates, readiness rituals, admin surface, world generator. No telemetry/analytics pipeline or patch cadence. |
| **Accessibility** | ~15% | n/a | Text-native (screen-reader friendly by medium). No declared text-scaling, colorblind, or remap options in the client contract. |

**Blended engineering read:** roughly **~20-25% of a AAA graphical MMORPG's total scope**, and
roughly **~45% of a credible commercial *text* MUD's scope**. The engine punches well above the
content: CodeForge is architecturally closer to done than Aethryn is content-complete. The honest
one-line summary is *strong spine, thin flesh, no crowd* (multiplayer social/economy is the least
built dimension).

### Highest-risk engineering gaps (ranked)

1. **No multiplayer group layer.** Combat, quests, and rewards are single-session. Party/raid/guild
   is the deepest structural gap and touches the tick, persistence, and networking at once.
2. **Content density far below launch scale.** ~180 items and ~75 authored NPCs cannot sustain a
   level-1-to-255 curve; the procedural world is broad but shallow in authored encounters.
3. **No economy sinks/faucets model.** A currency exists but nothing balances inflation at
   population; this breaks quietly and late.
4. **No telemetry/analytics.** Live-ops decisions would be blind; there is no measured session
   length, retention, or economy-flow data path.
5. **Serving model is single-process.** Fine for a demo; a sharded/instanced model is unproven for
   concurrency at MMO scale.

### Highest-value next milestones

1. **Party + shared combat** (unlocks the "multi-user" in MUD; prerequisite for dungeons/raids).
2. **Content-density pass to a playable 1-to-30 band** (authored quests, NPCs, items at real
   density for one starter Reach).
3. **Player trade + market** (the smallest real economy loop; sink/faucet instrumentation rides on
   it).
4. **Telemetry seam** (a typed event stream feeding a simple analytics table; reuses the SQL
   analytics organ).

### Fastest paths (engineering estimate, to be firmed after benchmark passes)

- **To a playable prototype:** it largely exists. A single-player vertical slice (create -> level a
  few bands -> craft -> beat a boss -> spend currency) is reachable now; the gap is a curated
  starter-Reach content pass and an onboarding path.
- **To Alpha:** add the party layer + one dungeon runnable by a group + a trade loop + a
  content-density pass on the 1-to-30 band + a telemetry seam.
- **To Launch:** economy balancing at population, guild layer, achievements/titles system, a full
  level-cap content curve, moderation/support tooling, and load-tested concurrent serving.

---

## Column legend (for the comparison tables)

Each subsystem is scored on the commissioned structure, rendered as two stacked tables to fit:

**Status table:** Current CodeForge - Current Aethryn - AAA Benchmark - Historical MUD Benchmark -
Confidence - Sources.
**Targets table:** Prototype - Alpha - Launch - Five-Year - Gap Remaining - Priority - Notes.

Benchmark and source columns marked `[Pass N]` are staged research (see roadmap). Target columns are
engineering estimates unless a cited benchmark has landed.

---

## 1. World scale

**Status**

| Subsystem | Current CodeForge | Current Aethryn | AAA Benchmark | Historical MUD Benchmark | Confidence | Sources |
|-----------|-------------------|-----------------|---------------|--------------------------|------------|---------|
| Rooms | Engine: generator scales one seed 1x to ~1M (`CODEFORGE_WILD_SCALE`) | ~26,811 at default scale (75 authored + 26,736 generated) | [Pass 2] | [Pass 2] (DikuMUD-era worlds often 5k-15k rooms) | Current: **Measured** | census |
| Regions / zones | Data-driven zones | 14 zones, 14 wildlands regions | [Pass 2] | [Pass 2] | Measured | census |
| Settlements (cities/villages) | Seed-defined | 45 settlements | [Pass 2] | [Pass 2] | Measured | census |
| Dungeons | Seed-defined | 16 dungeons | [Pass 2] | [Pass 2] | Measured | census |
| Raids | Not modelled as a distinct tier | 0 | [Pass 2] | [Pass 2] | Measured | census |
| Fast-travel nodes | Waystone network | 14 waystones | [Pass 2] | [Pass 2] | Measured | census |
| Max exits per room | 6 cardinal + up/down (data) | same | [Pass 2] | ~6-10 (Diku dirs) | Measured | world.py DIRECTIONS |

**Targets** (engineering estimates unless cited)

| Subsystem | Prototype | Alpha | Launch | Five-Year | Gap Remaining | Priority | Notes |
|-----------|-----------|-------|--------|-----------|---------------|----------|-------|
| Rooms (authored-quality) | 300 | 1,500 | 6,000 | 20,000 | Authored depth is the gap, not raw count | High | Procedural breadth exists; authored encounter density does not |
| Zones | 3 polished | 7 | 20 | 40 | Polish, not count | Med | 14 exist but thinly populated |
| Dungeons | 3 | 8 | 25 | 60 | Mechanics depth | High | Count is close; group mechanics missing |
| Raids | 0 | 1 | 5 | 15 | Whole tier absent | Med | Blocked on party layer |

---

## 2. Population (NPCs)

**Status**

| Subsystem | Current CodeForge | Current Aethryn | AAA Benchmark | Historical MUD Benchmark | Confidence | Sources |
|-----------|-------------------|-----------------|---------------|--------------------------|------------|---------|
| Authored NPCs | Seed-driven | 75 | [Pass 2] | [Pass 2] | Measured | census |
| Procedural NPCs | Guardian-per-N-rooms in wildlands | scales with world | [Pass 2] | [Pass 2] | Measured (mechanism) | wildlands.py |
| Bosses | tier=boss + phases/specials | 16 | [Pass 2] | [Pass 2] | Measured | census |
| Merchants | Shop system | via shop wares (not a tier flag) | [Pass 2] | [Pass 2] | Partial | shop.py |
| Aggressive NPCs | Beat-driven menace | 16 | [Pass 2] | [Pass 2] | Measured | census |

**Targets**

| Subsystem | Prototype | Alpha | Launch | Five-Year | Gap Remaining | Priority | Notes |
|-----------|-----------|-------|--------|-----------|---------------|----------|-------|
| Authored NPCs | 150 | 600 | 3,000 | 10,000 | Large | High | Dialogue depth is the real cost, not the row |
| Bosses | 20 | 50 | 150 | 400 | Mechanics variety | High | Encounter pass-2 mechanics staged |
| Named/quest NPCs | 40 | 200 | 1,000 | 3,000 | Large | High | Ties to quest count |

---

## 3. Content (quests, dialogue, lore)

**Status**

| Subsystem | Current CodeForge | Current Aethryn | AAA Benchmark | Historical MUD Benchmark | Confidence | Sources |
|-----------|-------------------|-----------------|---------------|--------------------------|------------|---------|
| Authored quests | State-machine quests | 7 authored | [Pass 2] | [Pass 2] | Measured | census |
| Procedural quests | errands / bounties / deliveries / rumors / storylines generators | scales (14 zone storylines) | [Pass 2] | [Pass 2] | Measured (mechanism) | census, storylines.py |
| Dialogue | Per-NPC dialogue trees | 75 NPCs carry dialogue | [Pass 2] | [Pass 2] | Measured | census |
| Achievements / titles | `title` verb; classroom achievements | game achievements not a system | [Pass 2] | [Pass 2] | Partial | titles.py |
| Lore / books | Item lore fields | 41 items carry lore | [Pass 2] | [Pass 2] | Measured | census |

**Targets**

| Subsystem | Prototype | Alpha | Launch | Five-Year | Gap Remaining | Priority | Notes |
|-----------|-----------|-------|--------|-----------|---------------|----------|-------|
| Authored quests | 25 | 120 | 600 | 2,500 | Very large | High | Biggest content lever for "feels like a game" |
| Procedural quest variety | 5 archetypes | 12 | 25 | 50 | Medium | Med | Generators exist; need variety + reward tuning |
| Achievements system | seam | 50 | 300 | 1,000 | System absent | Med | Reuse the registry/evidence pattern |

---

## 4. Player systems (progression)

**Status**

| Subsystem | Current CodeForge | Current Aethryn | AAA Benchmark | Historical MUD Benchmark | Confidence | Sources |
|-----------|-------------------|-----------------|---------------|--------------------------|------------|---------|
| Level cap (character) | 255 (locked curve) | 255 | [Pass 2] | [Pass 2] | Measured | progression.py |
| Jobs / classes | Data-driven | 31 | [Pass 2] | [Pass 2] | Measured | census |
| Professions | Gather + craft trades | 6 | [Pass 2] | [Pass 2] | Measured | census |
| Skills / abilities | Ability system | 63 | [Pass 2] | [Pass 2] | Measured | census |
| Equipment slots | 6 (weapon/head/body/arm/2 accessory) | 6 | [Pass 2] | ~10-19 typical | Measured | equipment.py |
| Factions / Orders | Reputation + tiers | 4 Orders | [Pass 2] | [Pass 2] | Measured | census |
| Currencies | Tiered ember-coin | 1 currency, 4 tiers | [Pass 2] | [Pass 2] | Measured | coinage.py |
| Inventory slots | Unbounded list (no cap) | n/a | [Pass 2] | [Pass 2] | Measured | items.py |

**Targets**

| Subsystem | Prototype | Alpha | Launch | Five-Year | Gap Remaining | Priority | Notes |
|-----------|-----------|-------|--------|-----------|---------------|----------|-------|
| Jobs / classes | 6 polished | 12 | 20 | 30 | Depth, not count | Med | 31 exist; balance/identity is the work |
| Professions | 6 | 8 | 12 | 18 | Recipe depth | Med | Crafting campaign shipped 1a-1d |
| Abilities | 40 | 120 | 300 | 600 | Large | High | Per-job kits are thin |
| Equipment slots | 6 | 8 | 10 | 12 | Small | Low | Add rings/trinket/back to reach genre norm |

---

## 5. Itemization

**Status**

| Subsystem | Current CodeForge | Current Aethryn | AAA Benchmark | Historical MUD Benchmark | Confidence | Sources |
|-----------|-------------------|-----------------|---------------|--------------------------|------------|---------|
| Total items | Data-driven | 180 | [Pass 2] | [Pass 2] | Measured | census |
| Weapons | slot=weapon | 22 | [Pass 2] | [Pass 2] | Measured | census |
| Armor (head/body/arm) | 3 armor slots | 32 (9+13+10) | [Pass 2] | [Pass 2] | Measured | census |
| Accessories | 2 accessory slots | 31 (17+14) | [Pass 2] | [Pass 2] | Measured | census |
| Consumables | consume field | 14 | [Pass 2] | [Pass 2] | Measured | census |
| Materials / other | crafting + quest + lore | 81 | [Pass 2] | [Pass 2] | Measured | census |
| Recipes | Refinement chains | 38 | [Pass 2] | [Pass 2] | Measured | census |
| Equipment sets | Set bonuses | 7 | [Pass 2] | [Pass 2] | Measured | census |

**Targets**

| Subsystem | Prototype | Alpha | Launch | Five-Year | Gap Remaining | Priority | Notes |
|-----------|-----------|-------|--------|-----------|---------------|----------|-------|
| Total items | 300 | 1,200 | 5,000 | 15,000 | Large | High | Itemization drives the reward loop |
| Recipes | 60 | 200 | 600 | 1,500 | Large | Med | Chains exist; breadth is the gap |
| Rarity tiers | 3 | 5 | 6 | 7 | System partial | Med | Formalise a rarity ladder |

---

## 6. Combat

**Status**

| Subsystem | Current CodeForge | Current Aethryn | AAA Benchmark | Historical MUD Benchmark | Confidence | Sources |
|-----------|-------------------|-----------------|---------------|--------------------------|------------|---------|
| Damage / resistance types | 10 (FIR ICE LGT WND ERT WTR HLY DRK PSN CRS) | same | [Pass 2] | [Pass 2] | Measured | score_sheet_model.py |
| Status effects | Foe: burn/weaken/daze/brand; player: DoT + daze | same | [Pass 2] | [Pass 2] | Measured | afflictions.py |
| Boss mechanics | Phases (enrage) + telegraphed specials | 16 bosses, 2 with specials | [Pass 2] | [Pass 2] | Measured | boss_phases/specials |
| Party / group | **None** | 0 | [Pass 2] (5 party / 10-40 raid common) | [Pass 2] | Measured (absent) | combat.py |
| Combat cadence | World-beat tick, synchronous | same | [Pass 2] | [Pass 2] | Measured | forge.py |

**Targets**

| Subsystem | Prototype | Alpha | Launch | Five-Year | Gap Remaining | Priority | Notes |
|-----------|-----------|-------|--------|-----------|---------------|----------|-------|
| Party layer | seam | 5-player party | party + 10 raid | party + 20-40 raid | **Whole layer absent** | **Highest** | Unlocks dungeons/raids/social |
| Boss mechanics | 4 patterns | 8 | 20 | 40 | Encounter pass-2 staged | High | Composes existing phases/specials/afflictions |
| Status effects | 8 | 16 | 30 | 50 | Medium | Med | Substrate exists |

---

## 7. Social systems

**Status**

| Subsystem | Current CodeForge | Current Aethryn | AAA Benchmark | Historical MUD Benchmark | Confidence | Sources |
|-----------|-------------------|-----------------|---------------|--------------------------|------------|---------|
| Chat channels | Relay channels | present | [Pass 2] | [Pass 2] | Measured | relay.py |
| Guilds | **None** | 0 | [Pass 2] | [Pass 2] | Measured (absent) | - |
| Mail | **None** | 0 | [Pass 2] | [Pass 2] | Measured (absent) | - |
| Friends / ignore | **None** | 0 | [Pass 2] | [Pass 2] | Measured (absent) | - |
| Player trade | **None** | 0 | [Pass 2] | [Pass 2] | Measured (absent) | - |
| Housing | **None** | 0 | [Pass 2] | [Pass 2] | Measured (absent) | - |

**Targets**

| Subsystem | Prototype | Alpha | Launch | Five-Year | Gap Remaining | Priority | Notes |
|-----------|-----------|-------|--------|-----------|---------------|----------|-------|
| Guilds | 0 | basic (create/join/roster) | ranks + bank + hall | alliances | Whole system | High | After party layer |
| Player trade | 0 | direct trade | + auction house | + cross-region market | Whole system | High | Smallest real economy loop |
| Mail / friends | 0 | friends | + mail | + social graph | Whole system | Med | Cheap, high retention value |

---

## 8. Economy

**Status**

| Subsystem | Current CodeForge | Current Aethryn | AAA Benchmark | Historical MUD Benchmark | Confidence | Sources |
|-----------|-------------------|-----------------|---------------|--------------------------|------------|---------|
| Currencies | Tiered ember-coin (1 currency, 4 tiers) | same | [Pass 2] | [Pass 2] | Measured | coinage.py |
| Shops / vendors | Buy/sell | present | [Pass 2] | [Pass 2] | Measured | shop.py |
| Crafting sinks | Recipes consume materials/coin | present | [Pass 2] | [Pass 2] | Measured | crafting.py |
| Repair / durability | **None** | 0 | [Pass 2] | [Pass 2] | Measured (absent) | - |
| Auction / market | **None** | 0 | [Pass 2] | [Pass 2] | Measured (absent) | - |
| Sink/faucet balancing | **None modelled** | 0 | [Pass 2] | [Pass 2] | Measured (absent) | - |

**Targets**

| Subsystem | Prototype | Alpha | Launch | Five-Year | Gap Remaining | Priority | Notes |
|-----------|-----------|-------|--------|-----------|---------------|----------|-------|
| Market | 0 | trade | auction house | regional markets | Whole system | High | Ties to social trade |
| Sinks/faucets | 0 | repair sink | modelled + monitored | dynamic tuning | Whole model | High | Needs telemetry to tune |

---

## 9. World simulation

**Status**

| Subsystem | Current CodeForge | Current Aethryn | AAA Benchmark | Historical MUD Benchmark | Confidence | Sources |
|-----------|-------------------|-----------------|---------------|--------------------------|------------|---------|
| Respawn | Policy catalog (static/dynamic/seasonal) | present | [Pass 2] | [Pass 2] | Measured | respawn.py, zones.py |
| Weather / seasons / day-night | Climate clock | present | [Pass 2] | [Pass 2] | Measured | climate.py |
| Dynamic spawns | Wanderers, seasonal-gated | present | [Pass 2] | [Pass 2] | Measured | zones.py |
| NPC schedules | **None** | 0 | [Pass 2] | [Pass 2] | Measured (absent) | - |
| Faction wars / world events | **None** | 0 | [Pass 2] | [Pass 2] | Measured (absent) | - |

**Targets**

| Subsystem | Prototype | Alpha | Launch | Five-Year | Gap Remaining | Priority | Notes |
|-----------|-----------|-------|--------|-----------|---------------|----------|-------|
| World events | 0 | 1 scripted | 5 recurring | dynamic | System absent | Med | High spectacle-per-effort |
| NPC schedules | 0 | key NPCs | town-wide | ecology | System absent | Low | Nice-to-have depth |

---

## 10. Engineering

**Status** (measured; command noted)

| Subsystem | Current CodeForge | AAA Benchmark | Historical MUD Benchmark | Confidence | Command / Source |
|-----------|-------------------|---------------|--------------------------|------------|------------------|
| Tick model | Synchronous pure-function `handle_command`, world-beat | [Pass 2] | [Pass 2] | Measured | forge.py |
| Persistence | SQLite via SQLAlchemy 2.0, 3 tables (characters, job_progress, accounts) | [Pass 2] | [Pass 2] | Measured | grep `__tablename__` |
| Save cadence | On key events (login/logout/level/command milestones) | [Pass 2] | [Pass 2] | Measured | forge.py save_character |
| Engine LOC (parts + forge) | 34,373 | n/a | n/a | Measured | census |
| Total LOC incl. tests | 63,239 | n/a | n/a | Measured | `wc -l` parts forge tests |
| Modules | 215 python (95 engine + 87 world + 33 shelf) | n/a | n/a | Measured | census |
| Tests | full CI-gated suite (count via command, kept off docs to avoid drift) | n/a | n/a | Measured | `pytest --collect-only -q` |
| Native accelerators | 7 organs (Rust nav, C++ map, Go edge, C textkernel, protobuf, SQL analytics, Lua) | [Pass 2] | [Pass 2] | Measured | ADRs 0010-0014 |
| Max concurrent players | Single-process gateway (untested at scale) | [Pass 2] | [Pass 2] | Estimate | gateway.py |

**Targets**

| Subsystem | Prototype | Alpha | Launch | Five-Year | Gap | Priority | Notes |
|-----------|-----------|-------|--------|-----------|-----|----------|-------|
| Concurrent players | 10 | 100 | 1,000 | 10,000 | Unproven past demo | High | Needs load test + serving model |
| DB tables | 3 | ~8 | ~20 | sharded | Grows with features | Med | Party/guild/mail/market add tables |
| Telemetry | seam | typed events | analytics pipeline | live dashboards | Absent | High | Reuse SQL analytics organ |

---

## 11. Live operations

| Subsystem | Current | Prototype | Alpha | Launch | Confidence | Notes |
|-----------|---------|-----------|-------|--------|------------|-------|
| CI / gates | Green CI, security + readiness rituals | keep | keep | keep | Measured | Mature |
| Telemetry / analytics | SQL analytics organ (offline) | seam | live events | pipeline | Measured | No live feed yet |
| Patch cadence | Ad hoc (branch->PR->merge) | weekly | biweekly | seasonal | Estimate | [Pass 2] for industry cadence |
| Support / moderation tooling | Admin surface + rank gates | keep | +reports | +moderation queue | Measured | Partial |

---

## 12. Accessibility

| Subsystem | Current | Benchmark leader | Prototype | Launch | Confidence | Notes |
|-----------|---------|------------------|-----------|--------|------------|-------|
| Screen-reader friendliness | Text-native medium | [Pass 2] | audit | certified path | Estimate | Inherent advantage of text |
| Text scaling | Client-side (terminal/GUI) | [Pass 2] | declare | option | Partial | Not a declared contract |
| Colorblind / reduced motion | Not declared | [Pass 2] | declare | option | Estimate | Client concern (codeforge-console/client) |
| Remapping | Client-side | [Pass 2] | declare | option | Estimate | Client concern |

---

## 13. Technology stack

| Subsystem | Current | AAA Benchmark | Confidence | Notes |
|-----------|---------|---------------|------------|-------|
| Server architecture | Modular monolith, threaded TCP gateway | [Pass 2] (monolith vs microservices tradeoff) | Measured | Deliberate; ADR-backed |
| Networking model | Telnet + GMCP/MSDP; synchronous tick | [Pass 2] | Measured | gateway.py |
| Database | SQLite / SQLAlchemy 2.0 | [Pass 2] (Postgres/sharded typical) | Measured | Postgres path exists in analytics organ |
| Procedural generation | Wildlands generator (deterministic) | [Pass 2] | Measured | wildlands.py |
| Content pipeline | YAML seeds + validators + emitters | [Pass 2] | Measured | seed.py, tools/emit_map_world.py |

---

## Research roadmap

The benchmark columns are filled in cited passes. Each pass researches primary sources (GDC talks,
postmortems, engine docs, academic and live-service engineering articles) and records a value, a
source, and a confidence level per cell. Not started yet; this slice is the measured scaffold.

- **Pass 2 - World, population, content benchmarks.** Room/area/NPC/quest/item counts for the target
  set (WoW, FFXIV, GW2, EVE, RuneScape/OSRS, ESO, and the historical MUDs: DikuMUD, CircleMUD, ROM,
  SMAUG, LP, Achaea, Aardwolf, GemStone). Cite each.
- **Pass 3 - Combat, progression, itemization benchmarks.** Level caps, time-to-cap, party/raid
  sizes, ability counts, damage/resist schemes, gear-slot norms, rarity ladders.
- **Pass 4 - Social, economy, world-sim benchmarks.** Guild sizes, market/auction throughput,
  currency/sink models, world-event cadence, NPC-schedule depth.
- **Pass 5 - Engineering, live-ops, accessibility, tech benchmarks.** Latency/tick/memory targets,
  concurrency densities, patch/expansion cadence, staffing ratios, accessibility leaders, and the
  architecture tradeoffs (monolith vs microservices, replication, interest management).
- **Pass 6 - Failure patterns and lessons.** Postmortems from failed/troubled MMORPGs (WildStar,
  Chronicles of Elyria, and networking/persistence lessons from Star Citizen where applicable) and
  their engineering implications for Aethryn.
- **Pass 7 - Definition-of-Complete checklists.** A per-subsystem "done" checklist tied to the
  launch targets, so a checked box means measured-and-verified, never aspirational.

---

## Definition of Complete (stub - Pass 7)

Each subsystem will carry a checklist whose boxes are measured, not asserted. Seeded here so the
structure is visible; the criteria firm up once launch targets are benchmark-backed.

- [ ] World scale: launch room/zone/dungeon targets met and authored-quality, not just generated.
- [ ] Population: launch NPC/boss/quest-NPC counts met with dialogue depth.
- [ ] Combat: party layer shipped; N boss mechanics; status-effect breadth.
- [ ] Progression: ability kits per job at target depth; balanced curve to cap.
- [ ] Itemization: item/recipe/rarity targets met; reward loop tuned.
- [ ] Social: guild + trade + mail + friends shipped and load-tested.
- [ ] Economy: market live; sinks/faucets modelled and monitored.
- [ ] Engineering: concurrency target load-tested; telemetry pipeline live.
- [ ] Accessibility: declared options audited against the benchmark leader.

---

*Slice 1 (measured scaffold + dashboard). Current-status columns are reproducible via
`python tools/census.py`. Benchmark columns are staged research (Pass 2+). No number in the current
column is estimated; no benchmark number is invented.*
