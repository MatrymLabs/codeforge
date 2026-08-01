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

> **Re-baseline note (2026-07-31).** Several systems this scorecard first listed as
> *absent/blocking* have since shipped and are verified in code. Retired from the gap and
> risk lists this pass: loose-item persistence (`parts/world/loose_store.py`, `loose_items`
> table), the combat trinity seams (`parts/world/threat.py` + ally-targeted heals in
> `parts/world/abilities.py`), daily/weekly lockouts (`parts/world/lockouts.py`), the
> auction house (`parts/world/auction.py`, `auction_listings` table), the durability/repair
> coin sink (`parts/world/durability.py`), the guild item-vault (`parts/world/guild.py`),
> and mail attachments (`parts/world/mail.py`). Measured counts and the DB-table list were
> refreshed from `python tools/census.py`. The completion estimates below are still
> Low-confidence engineering estimates; the three dimensions whose substrate materially grew
> (combat, social, economy) were nudged up this pass and are flagged.
>
> **Correction (2026-08-01).** Two prose gaps below were stale against shipped code and are fixed
> this pass: the "no endgame content" gap (the daily-boss + weekly-raid LOOP shipped in #612/#621,
> tested), and the "no economy sink/faucet macro-model" gap (the designed audit + inflation balance
> verdict shipped in #702/#705). Both moved to the retired list; the remaining endgame and economy
> items were narrowed to what is genuinely still open (endgame *depth*; a *live* economy event seam).
> A later pass the same day narrowed endgame *depth* itself: its first two slices shipped -- a
> cohort-scaled raid reward (#711) and a second boss unleash kind, `mend` (#709) -- leaving a gear
> ilvl ceiling, raid difficulty-scaling, and more mechanic kinds.

### Estimated completion (engineering estimate, Low confidence)

"Percent complete versus a AAA MMORPG" is inherently fuzzy: it depends whether the yardstick is a
graphical AAA title, a commercial flagship *text* MUD, or a playable prototype. A single number
would mislead, so the estimate is split by yardstick and by dimension, and every figure here is a
**Low-confidence engineering estimate**, to be tightened once the benchmark columns are cited.

| Dimension | vs. AAA graphical MMORPG | vs. flagship commercial text MUD | Basis (measured) |
|-----------|--------------------------|----------------------------------|------------------|
| **Engine / architecture** | ~45% | ~70% | Pure-function tick, 5-table persistence, a large module base, a CI-gated suite (count via `pytest --collect-only`), 7 native-accelerator organs. Mature core; missing distributed/sharded serving. |
| **Combat systems** | ~40% | ~55% | 76 abilities across **9 ability kinds** (strike/heal/brand/daze/weaken/taunt/cleanse/buff + a new lifesteal `drain`), 10 damage types, boss phases + telegraphed specials + afflictions. Party combat shares XP + round-robin loot; the trinity seams now exist (per-NPC threat/aggro table + taunt, ally-targeted heals). A raid bounty scales with the co-located cohort (#711) and a second boss unleash kind, `mend`, shipped (#709). Deep-kind kits filled out: the callings that fight by DoT/control/lifesteal now wield real movesets. Gaps: raid *difficulty*-scaling (reward-scaling done), deeper boss-mechanic variety (2 kinds now). |
| **Content scale (world)** | ~15% | ~40% | ~26,800 rooms at default scale (procedural), 45 settlements, 16 dungeons. Authored depth thin (75 hand rooms, 7 authored quests). |
| **Content scale (items/NPCs)** | ~10% | ~35% | 185 items, 75 authored NPCs + procedural guardians, 38 recipes. Well below launch density. |
| **Progression / player systems** | ~35% | ~60% | 31 jobs, 6 professions, 4 Orders, level cap 255, ember-coin currency. Broad skeleton, shallow per-system depth. |
| **Social / multiplayer** | ~38% | ~20% | Shipped: party (max 5, shared XP + round-robin loot), atomic player trade, persisted guilds (ranks + chat + coin treasury + item vault), async mail with attachments, friends, world chat, and a raid reward that scales with the co-located cohort (#711). Gaps: no LFG/matchmaking, no housing. (nudged up: item vault + mail attachments + cohort scaling shipped) |
| **Economy** | ~30% | ~30% | Tiered currency, NPC shops, per-town general-store materials market (buy/sell spread), crafting sinks, inns as a coin sink, guild treasury, direct player trade, a coin-escrow auction house, and a durability/repair coin sink. Gaps: no macro sink/faucet model, no cross-region market. (nudged up: auction house + durability shipped) |
| **World simulation** | ~30% | ~55% | Weather, seasons, day/night, respawn policies, dynamic spawns, zone resets. No NPC schedules or faction war. |
| **Live ops / tooling** | ~20% | ~40% | CI, security gates, readiness rituals, admin surface, world generator. No telemetry/analytics pipeline or patch cadence. |
| **Accessibility** | ~15% | n/a | Text-native (screen-reader friendly by medium). No declared text-scaling, colorblind, or remap options in the client contract. |

**Blended engineering read:** roughly **~20-25% of a AAA graphical MMORPG's total scope**, and
roughly **~45% of a credible commercial *text* MUD's scope**. The engine punches well above the
content: CodeForge is architecturally closer to done than Aethryn is content-complete. The keystones
that once headlined the gap list (loose-item persistence, the combat trinity, the auction house) have
since shipped, so the honest one-line summary has moved to *strong spine, a built-but-shallow game*
(corrected 2026-08-01): the multiplayer layer (party, guild, mail, friends, trade, chat), the endgame
LOOP (daily bosses + weekly raids, #612/#621), and the economy sink/faucet model (#702/#705) all
exist on the persistence + combat-trinity substrate; the deepest remaining gaps are now endgame
*depth* (a gear ilvl ceiling; and deeper mechanic variety + raid *difficulty*-scaling atop the first
slices shipped in #709/#711) and authored content density.

### Highest-risk engineering gaps (ranked, re-baselined 2026-07-31)

1. **Thin endgame *depth*.** The endgame LOOP is now built (corrected 2026-08-01): daily boss
   lockouts (#612) + weekly raid bosses (#621) assemble a real daily/weekly cadence -- 16 boss-tier
   foes on a daily bounty and 2 raid-flagged weekly bosses (Netharion's Throne, level 300, with
   above-main-path generated gear and a multi-phase enrage), all lockout-gated and tested
   (`test_combat.py` daily+weekly+reset, `test_lockouts.py`, `test_playthrough.py`). What remains is
   endgame DEPTH, not its existence, and two of its three legs now have a first slice (corrected
   2026-08-01): **raid-size cohort scaling** shipped as a bounty that scales with the co-located party
   (#711), and **boss-mechanic variety** gained a second unleash kind, `mend` (#709), beyond the shared
   enrage. Still open: an explicit **gear treadmill / ilvl ceiling** (the affix roll already scales
   gear, but there is no stored ilvl), raid *difficulty*-scaling (only the reward scales so far), and
   more mechanic kinds. Still the shallowest dimension relative to AAA, but no longer empty.
2. **Content density far below launch scale.** ~185 items and ~75 authored NPCs cannot sustain a
   1-to-255 curve; ~1,680 quests are 8 template generators over ~7 authored arcs (wide, not deep).
   Only Veridia (the cradle) meets production density; the other 13 zones sit at baseline.
3. **No live event-stream telemetry at population.** The economy sink/faucet **macro-model now
   exists** (corrected 2026-08-01): `parts/coin_flow.py` + `make economy-audit` (#702, #705) audit
   the designed faucets (foe drops) vs sinks (repair, the fall) and render an inflation **balance
   verdict** -- which measures the economy as INFLATIONARY ~29% (a conservative floor), the very
   "sinks not balanced as a system" this line once flagged. What remains is a *live* event seam:
   instrumenting the running coin-change paths so actual flow (not just designed) can be tuned at
   population. The audit answers the design question; the live seam answers the ops question.
4. **The shipped social layer is invisible in the client.** Party/guild/mail/friend systems exist in
   the engine but no versioned event schema surfaces them, so the play experience lags the engineering.

*Retired since the 2026-07-29 gap analysis (verified shipped in code): loose-item persistence
(`loose_store.py`, `loose_items` table), the combat trinity seams (`threat.py`, ally-targeted heals in
`abilities.py`), daily/weekly lockouts (`lockouts.py`), the auction house (`auction.py`,
`auction_listings` table), the durability/repair sink (`durability.py`), the guild item-vault
(`guild.py`), and mail attachments (`mail.py`). Retired 2026-08-01 (verified shipped): the **endgame
loop** -- daily boss lockouts + weekly raid bosses assembling a real cadence (#612, #621); and the
**economy sink/faucet macro-model + inflation balance verdict** (`coin_flow.py`, `make
economy-audit`, #702/#705). These no longer belong on the risk list.*

### Highest-value next milestones

1. **Endgame *depth*** (the loop is built -- #612/#621; first depth slices shipped -- cohort-scaled
   raid reward #711, a second boss unleash kind #709): still open is a gear ilvl ceiling, raid
   *difficulty*-scaling (only the reward scales so far), and more per-boss mechanic kinds.
2. **Content-density pass on the leveling spine** (curated 1-to-30, then the next zone, at production
   density: Veridia is the proven pattern).
3. **Live economy event seam** (the designed sink/faucet macro-model + inflation balance verdict
   shipped in #702/#705; the remaining piece is instrumenting the running coin-change paths so actual
   flow can be tuned at population).
4. **Social surfacing in the client** (a versioned Party/Guild/Mail/Friend event schema + rendered
   panels, so the client stops lagging the engine's shipped social layer).

### Fastest paths (engineering estimate, to be firmed after benchmark passes)

- **To a playable prototype:** it largely exists. A single-player vertical slice (create -> level a
  few bands -> craft -> beat a boss -> spend currency) is reachable now; the gap is a curated
  starter-Reach content pass and an onboarding path.
- **To Alpha:** the party layer + group-runnable dungeons + a trade loop + loose-item persistence now
  exist; the remaining Alpha gaps are a content-density pass on the 1-to-30 band, an endgame loop on
  the shipped lockout substrate, and a telemetry seam.
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
| Raids | 0 | 1 | 5 | 15 | Content unbuilt | High | Substrate ready (party + threat + lockouts); the encounter content is the gap |

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
| Skills / abilities | Ability system | 66 | [Pass 2] | [Pass 2] | Measured | census |
| Equipment slots | 8 (weapon/head/body/arm/leg/feet/2 accessory) | 8 | [Pass 2] | ~10-19 typical | Measured | equipment.py |
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
| Total items | Data-driven | 185 | [Pass 2] | [Pass 2] | Measured | census |
| Weapons | slot=weapon | 22 | [Pass 2] | [Pass 2] | Measured | census |
| Armor (head/body/arm/leg/feet) | 5 armor slots | 36 (9+13+10+2+2) | [Pass 2] | [Pass 2] | Measured | census |
| Accessories | 2 accessory slots | 31 (17+14) | [Pass 2] | [Pass 2] | Measured | census |
| Consumables | consume field | 14 | [Pass 2] | [Pass 2] | Measured | census |
| Materials / other | crafting + quest + lore | 82 | [Pass 2] | [Pass 2] | Measured | census |
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
| Party / group | 5-player party, shared XP + round-robin loot | present | [Pass 2] (5 party / 10-40 raid common) | [Pass 2] | Measured | party.py, party_rewards.py, party_loot.py |
| Combat cadence | World-beat tick, synchronous | same | [Pass 2] | [Pass 2] | Measured | forge.py |

**Targets**

| Subsystem | Prototype | Alpha | Launch | Five-Year | Gap Remaining | Priority | Notes |
|-----------|-----------|-------|--------|-----------|---------------|----------|-------|
| Party layer | 5-player party (shipped) | party + shared combat | party + 10 raid | party + 20-40 raid | Raid-size cohort + LFG | High | Party + trinity + cohort-scaled raid reward done (#711); remaining: raid difficulty-scaling, LFG, more raid content |
| Boss mechanics | 4 patterns | 8 | 20 | 40 | Encounter pass-2 staged | High | Composes existing phases/specials/afflictions |
| Status effects | 8 | 16 | 30 | 50 | Medium | Med | Substrate exists |

---

## 7. Social systems

**Status**

| Subsystem | Current CodeForge | Current Aethryn | AAA Benchmark | Historical MUD Benchmark | Confidence | Sources |
|-----------|-------------------|-----------------|---------------|--------------------------|------------|---------|
| Chat channels | Relay channels | present | [Pass 2] | [Pass 2] | Measured | relay.py |
| Guilds | Persisted; ranks + chat + coin treasury | present | [Pass 2] | [Pass 2] | Measured | guild.py, guild_store.py |
| Mail | Async persisted letters (inbox/read/delete) | present | [Pass 2] | [Pass 2] | Measured | mail.py, mail_store.py |
| Friends / ignore | Persisted friends list (no ignore yet) | present | [Pass 2] | [Pass 2] | Measured | friends.py |
| Player trade | Atomic item + coin swap | present | [Pass 2] | [Pass 2] | Measured | trade.py |
| Housing | **None** | 0 | [Pass 2] | [Pass 2] | Measured (absent) | - |

**Targets**

| Subsystem | Prototype | Alpha | Launch | Five-Year | Gap Remaining | Priority | Notes |
|-----------|-----------|-------|--------|-----------|---------------|----------|-------|
| Guilds | ranks + chat + coin bank + item vault (shipped) | + guild hall | + perks | alliances | Guild hall, perks, alliances | Med | Coin bank + item vault done; hall/perks/alliances remain |
| Player trade | direct trade + auction house (shipped) | + auction house | + cross-region market | commodity pricing | Cross-region market, commodity pricing | High | Direct trade + coin-escrow auction house done; regional markets next |
| Mail / friends | friends + mail + attachments (shipped) | + attachments | + ignore + social graph | cross-shard | Ignore list, social graph | Med | Mail + attachments done; ignore + social-graph remain |

---

## 8. Economy

**Status**

| Subsystem | Current CodeForge | Current Aethryn | AAA Benchmark | Historical MUD Benchmark | Confidence | Sources |
|-----------|-------------------|-----------------|---------------|--------------------------|------------|---------|
| Currencies | Tiered ember-coin (1 currency, 4 tiers) | same | [Pass 2] | [Pass 2] | Measured | coinage.py |
| Shops / vendors | Buy/sell; per-town materials market (spread) | present (45 stores) | [Pass 2] | [Pass 2] | Measured | shop.py, stores.py |
| Crafting sinks | Recipes consume materials/coin | present | [Pass 2] | [Pass 2] | Measured | crafting.py |
| Coin sinks | Draught vendors + inn hearth | present (45 inns) | [Pass 2] | [Pass 2] | Measured | inns.py |
| Player trade | Atomic item + coin swap | present | [Pass 2] | [Pass 2] | Measured | trade.py |
| Repair / durability | Gear wears with use; repair is a coin sink | present | [Pass 2] | [Pass 2] | Measured | durability.py |
| Auction / market | Coin-escrow auction house (list / buy / expiry returns unsold) | present | [Pass 2] | [Pass 2] | Measured | auction.py, auction_store.py |
| Sink/faucet balancing | **None modelled** (individual sinks exist, not tuned as a system) | 0 | [Pass 2] | [Pass 2] | Measured (absent) | - |

**Targets**

| Subsystem | Prototype | Alpha | Launch | Five-Year | Gap Remaining | Priority | Notes |
|-----------|-----------|-------|--------|-----------|---------------|----------|-------|
| Market | trade + auction house (shipped) | auction house | + regional markets | commodity pricing | Regional markets, commodity pricing | High | Direct trade + auction house done; regional markets next |
| Sinks/faucets | repair + inn + craft sinks (shipped) | + monitored | modelled + monitored | dynamic tuning | Macro model + monitoring | High | Sinks exist; the macro model needs telemetry to tune |

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
| Persistence | SQLite via SQLAlchemy 2.0, 8 tables (characters, job_progress, accounts, guilds, mail, auction_listings, loose_items, bans) | [Pass 2] | [Pass 2] | Measured | grep `__tablename__` |
| Save cadence | On key events (login/logout/level/command milestones) | [Pass 2] | [Pass 2] | Measured | forge.py save_character |
| Engine LOC (parts + forge) | 43,257 | n/a | n/a | Measured | census |
| Total LOC incl. tests | 81,455 | n/a | n/a | Measured | `wc -l` parts forge tests |
| Modules | 261 python (99 engine + 125 world + 37 shelf) | n/a | n/a | Measured | census |
| Tests | full CI-gated suite (count via command, kept off docs to avoid drift) | n/a | n/a | Measured | `pytest --collect-only -q` |
| Native accelerators | 7 organs (Rust nav, C++ map, Go edge, C textkernel, protobuf, SQL analytics, Lua) | [Pass 2] | [Pass 2] | Measured | ADRs 0010-0014 |
| Max concurrent players | Single-process gateway (untested at scale) | [Pass 2] | [Pass 2] | Estimate | gateway.py |

**Targets**

| Subsystem | Prototype | Alpha | Launch | Five-Year | Gap | Priority | Notes |
|-----------|-----------|-------|--------|-----------|-----|----------|-------|
| Concurrent players | 10 | 100 | 1,000 | 10,000 | Unproven past demo | High | Needs load test + serving model |
| DB tables | 8 | ~10 | ~20 | sharded | Grows with features | Med | Auction + loose-items tables shipped; a world-state + telemetry table are next |
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
