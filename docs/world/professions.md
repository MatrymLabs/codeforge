# Professions -- the Maker's Trades

*How a hero PRACTICES a trade, as distinct from the calling they FIGHT with. Slice 1b of the
Crafting Campaign: the framework that turns using slice 1a's material chains into progression. This
is the design canon behind `seeds/aethryn/professions.yaml` and `kernel/world/professions.py`.*

## Calling vs. trade

A **calling** (`jobs.yaml`) is a hero's combat identity: one path, a stat spread, a move kit. A
**profession** is a trade they practise on the side. A hero swears to one calling but may work many
trades at once, and a trade never touches combat stats: it is its own axis of progression, earned by
doing the maker's work, not by fighting.

## The model (all data)

A trade is seed data with three fields:

- `name` -- its display name (e.g. Smithing).
- `kind` -- `gather` or `craft`.
- what it governs -- a gather trade lists the material prototypes it `works`; a craft trade lists the
  recipe labels it `makes`.

`professions.py` builds two reverse lookups from that data (`GATHER_OF`: material -> trade;
`CRAFT_OF`: recipe -> trade). When a maker gathers a material or crafts a recipe, `advance` awards
one unit of practice to the governing trade. The trades themselves live entirely in YAML, so a world
declares its own -- exactly the kind of subsystem the Seed Platform will later generalise.

## Aethryn's trades (slice 1b)

| Kind | Trade | Governs |
| --- | --- | --- |
| Gather | Prospecting | the wild ember-shard |
| Gather | Mining | raw ore and drowned ingots |
| Gather | Herbalism | the eight biome gather-herbs |
| Craft | Smithing | the metal recipes (ingot, fitting, buckler, hammer, plate, blade, signet) |
| Craft | Leatherworking | the emberhide stitch recipes |
| Craft | Alchemy | every draught, salve, reagent, and tonic |

Every recipe belongs to exactly one craft trade and every gatherable material to one gather trade;
the conformance test (`tests/test_professions.py`) pins it, so nothing a maker does is unclaimed.

## The skill curve

Practice is a simple, legible count: `level = 1 + practice // PER_LEVEL`, capped at `LEVEL_CAP`
(ten units per rank, twenty ranks). Level is **derived** from earned practice, never stored -- so a
restored hero recomputes their trade ranks exactly (architecture law 3, derive-don't-store). Practice
persists per character in the `professions` column (the `serialize`/`restore` pair, a compact
`trade:practice` string, migrated in `f4a9c1e0b7d2`).

A rank-up appends a line to the gather/craft it came from; ordinary practice is silent. The
`professions` verb shows the full trade sheet: every trade, its kind, level, and progress to next.

## What 1b deliberately does not do

Skill **gating** (a node or recipe that requires a minimum trade level), profession **bonuses**
(yield/quality scaling with rank), and **recipe acquisition** gated by trade are later work --
gating and acquisition belong with slice 1d, and monster-material trades (skinning) arrive with the
bestiary drops in slice 1c. 1b is the track itself: identity, skill-by-doing, and persistence.
