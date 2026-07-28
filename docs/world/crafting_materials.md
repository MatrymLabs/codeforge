# Crafting Materials and Refinement Chains

*The physical economy of Aethryn: what the world is made of, and how a maker turns the raw world
into finished goods. This is the design canon behind `seeds/aethryn/items.yaml` (the materials) and
`seeds/aethryn/recipes.yaml` (the chains). It is the Crafting Campaign's Parts I-V, scoped to what
slice 1a actually ships, with the professions (1b), monster materials (1c), and recipe acquisition
(1d) marked as the next tiers built on this foundation.*

## Philosophy (why refinement exists)

Before slice 1a, Aethryn's maker loop had only two tiers: a raw material (an ember-shard, a herb, a
salvaged ingot) crafted straight into a finished good. That is a two-step economy, and a two-step
economy is shallow: there is no journey between the wilds and the gear.

Refinement adds the missing middle. A material now climbs a chain:

```
RAW  ->  REFINED  ->  COMPONENT  ->  PRODUCT
```

Each tier is a distinct item, and each step is a recipe that consumes the lower tier to mint the
next. The value of a crafted good is the sum of the work along its chain, not a single lucky drop.
This is what makes crafted equipment worth buying, gives professions something to specialise in
(1b), and gives the geography a reason to matter: a material is only as available as the places it
comes from.

Design rules the chains hold to:

- **Geography determines materials, never the reverse.** Raw ore is quarried where the world has
  ore-biomes (volcanic flats, glacier waste, highland moor, salt desert), not sprinkled everywhere.
- **Every material has a real source.** Nothing in the library is dead weight: a raw tier is
  gathered or dropped, and every refined tier is reachable from a raw tier by a recipe.
- **The refinement earns the reward.** A refined product out-performs the raw shortcut. The direct
  `herb -> salve` heals 20; the refined `herb -> reagent -> tonic` heals 50. Spending the extra
  step is a choice the numbers reward.
- **It is all data.** The tiers and chains live in seed YAML, cross-checked against the item
  registry at boot (`parts.world.seed.load_recipes`). No chain can reference a material that is not
  a real item. crafting.py did not change; the depth is content.

## The material library (slice 1a)

Two exemplar chains ship in 1a, chosen because each is rooted in a material that already had a
source, so the whole chain is reachable the moment it lands.

### Metal chain (Smithing)

The four ore-biomes quarry **raw ore** (`raw_ore`) alongside the ember-shard, the drowned ingot, and
their herb (`parts.world.wildlands._gather_node`). From there:

| Tier | Item | Recipe | From |
| --- | --- | --- | --- |
| Raw | `raw_ore` | (gathered) | ore-biome nodes |
| Refined | `wrought_ingot` | `smelt_wrought_ingot` | 3x raw_ore |
| Component | `iron_fitting` | `forge_iron_fitting` | 2x wrought_ingot |
| Product | `travelers_buckler` (arm, DEF 3 / EVA 1) | `assemble_travelers_buckler` | 2x iron_fitting + 2x ember_shard |

### Alchemy chain

Any biome's gather-herb (the eight shipped in the content campaign) distils to a shared **herbal
reagent**, brewed with wild ember into a **restorative tonic**.

| Tier | Item | Recipe | From |
| --- | --- | --- | --- |
| Raw | the eight biome herbs | (gathered) | biome nodes |
| Refined | `herbal_reagent` | `distil_<herb>_reagent` (one per herb) | 3x that herb |
| Product | `restorative_tonic` (heals 50) | `brew_restorative_tonic` | 2x herbal_reagent + 1x ember_shard |

The eight distil recipes converge on one reagent, exactly as the eight salve recipes converge on one
salve: every forageable herb feeds the refined tier, so no herb is a dead end.

## What 1a deliberately does not do (the next tiers)

- **Hide -> leather** and monster materials shipped as **slice 1c**: furred and feathered creatures
  drop `raw_hide`, scaled and shelled ones drop `chitin_scale` (the `parts.world.bestiary` loot
  tables, by body-class), and Leatherworking refines each into gear (hide -> cured leather -> a hide
  jerkin; chitin -> a hardened plate -> a scaled bracer). The unbodied (elemental/undead/colossus)
  drop no such material -- there is no pelt to take.
- **Professions** (mining, herbalism, smithing, alchemy, ...) shipped as **slice 1b**: a data-driven
  skill track over these same chains, composing with the existing calling ladder. See
  [professions.md](professions.md).
- **Recipe acquisition** shipped as **slice 1d**: a recipe may carry a `requires` gate (a craft
  profession + level, and/or a sworn Order), and craftability **derives** from the player's
  professions and allegiance -- no stored "known recipe" flag (derive-don't-store). Practising a
  trade unlocks its master recipes, so leveling a profession has a payoff and advanced recipes feel
  earned. Aethryn gates its master tier (the grand draughts, the forgefire elixir, the reaver's
  blade, and the Reachlord's Signet, which also demands the Making Order). The same `requires` seam
  is where trainer/quest acquisition can later hang; the gate check lives in
  `parts.world.crafting.locked_reason`.

Every future tier is an extension of this same RAW -> REFINED -> COMPONENT -> PRODUCT spine, and is
exactly the kind of proven subsystem the Seed Platform will later generalise into a generator.
