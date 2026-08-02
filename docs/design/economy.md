# The Aethryn Economy

The Economy & World Foundation campaign builds a living economy for aethryn on top of the systems the
repository already has, rather than replacing them. This document records the **economic philosophy**
(Part I) and the **currency system** (Part II); the later parts (sinks, regional pricing, market
simulation, Seed Platform `EconomyProfile`) are staged behind these foundations.

Guiding rule (the campaign's PRIMARY RULE): **the repository is the source of truth.** Where a system
works, reuse and expand it. The purse was already a working, persisted `coins` scalar earned from
kills and spent at shops; the currency system below *denominates* that scalar, it does not replace it.

## Part I: economic philosophy

The economy is a loop with a **source** and a **sink**, and it stays healthy only while both are
real and roughly balanced.

- **Wealth is created** by effort: felling a foe drops coin scaled to its level and tier
  (`combat._coin_reward`), and selling gathered/looted goods to a merchant pays out. A harder foe,
  fought up, pays more (`kernel/shelf/reward_curve`); a gray foe pays nothing, so grinding trivial
  kills is not a wealth strategy.
- **Wealth is destroyed** by spending. Two live sinks today: the **settlement merchant**
  (`parts/world/townsfolk`, one per town, level-banded draughts, buy-back always below sell) and the
  **Waystone network** (`parts/world/travel`) — the largest sink by design. Fast-travel between the
  14 zone hubs costs a fare that scales with the *destination's* level band (`fare(level)`), so every
  time a traveller skips the road, coin drains back out; a hop to the starter valley is a handful of
  cinders, a leap to the endgame a small fortune. Danger, not cost, gates the far zones. Repairs,
  storage, and taxes are further sinks staged behind these.
- **Inflation is controlled** by the sinks, not by the denomination. As players earn more, the goods
  and services they must keep buying (consumables now; repairs, travel, taxes next) remove coin at a
  rate that scales with their level band. The currency's tiers only change how a balance *reads*;
  they neither create nor destroy value.
- **Player effort is rewarded** proportionally: level-scaled kill rewards, level-banded gear from
  named guardians (`parts/world/armory`), and hunt bounties (`parts/world/quest.register_bounties`)
  all pay more for harder, deeper content, so progress up the world is progress in wealth.
- **New players enter** at the base tier (cinders and sparks) with a starter town's affordable
  draughts; **veterans stay engaged** at the top tiers (embers and forgemarks) with deep-world gear,
  boss guardians, and the sinks that keep a fortune from being idle.

Parts of the philosophy the code does not yet fully realize (staged): regional pricing, merchant
caravans and supply chains, taxes and government influence, player-to-player markets and auctions,
and world-event price shocks. Each becomes a data-driven system behind an `EconomyProfile` (Part
VIII), so a seed can dial economic complexity to its deployment tier.

## Part II: the currency system

Aethryn does not use gold/silver/copper. Its coin is struck from **cooled ember**, in four tiers
that scale from a beginner's pocket to a legendary hoard (`parts/world/coinage.py`):

| Tier | Symbol | Worth | Who deals in it |
|---|---|---|---|
| **Cinder** | `c` | 1 (the base unit) | a new traveller's pocket change |
| **Spark** | `s` | 100 cinders | everyday town purchases |
| **Ember** | `e` | 100 sparks (10,000 cinders) | serious gear and services |
| **Forgemark** | `fm` | 100 embers (1,000,000 cinders) | legendary, once-a-climb transactions |

A purse of 1,234,567 cinders reads **"1 forgemark, 23 embers, 45 sparks, 67 cinders"** (or compact
**"1fm 23e 45s 67c"**). The decimal steps make it easy to understand, communicate, and display; the
same persisted scalar carries a beginner's flecks and a veteran's fortune, so there is no second
balance to track.

Each currency answers the campaign's five questions:

- **What creates it?** Kills and sales (the source above).
- **What destroys it?** Merchant purchases and the coming sinks (repairs, travel, taxes).
- **Who uses it?** Every player and every NPC vendor; one coin, one market.
- **What is it used for?** Consumables now; gear, services, housing, and guild costs as those land.
- **Why does it exist?** To make effort legible as wealth and to give a legendary hoard a name.

**Data-driven.** The tiers are a `Coinage` table, validated at construction (a base step of 1, strictly
positive steps, unique names and symbols). `AETHRYN_COINAGE` is the flagship default, but a seed may
define its own coin (a two-tier bit/crown coin works exactly the same), which is what lets the Seed
Platform vary the currency model per world. `purse(coins)` is the one player-facing formatter, wired
into `wallet`, the merchant's shop (`render_shop`/`buy`/`sell`), and combat's kill reward.
