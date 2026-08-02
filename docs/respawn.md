# Respawn Philosophy

Every respawn in Aethryn exists for a **gameplay reason**. This document is that philosophy, and the
catalog of the policies that carry it. The code catalog lives in `kernel/world/respawn.py`
(MOD-04.099); each policy names the real behavior that implements it, and the test twin pins that the
behavior still exists -- so no respawn drifts loose from its stated purpose.

## Principles

A respawn balances competing pressures:

- **Availability** -- a returning player should find something to do; a stripped zone is a dead zone.
- **Exploration** -- static, predictable spawns turn a world into a checklist. Where it fits, a
  respawn should *move* (a wandering pickup, a rotating rare), rewarding players who look around.
- **Competition vs. frustration** -- a contested node breeds camping. Per-player renewal (the gather
  node) sidesteps it; object instancing means a respawn never fights a copy a player carried off.
- **Economic stability** -- a resource that respawns too fast floods the market; too slow starves the
  crafters. Cadence is a lever, tuned per resource, not a constant.
- **Deterministic world, dynamic runtime** -- world *generation* is deterministic (the same seed
  builds the same map). Respawn *timing and placement* run at the beat, so they may vary -- drawn
  from a seedable RNG (`respawn.SPAWN_RNG`) that a test can pin exactly.

## Shipped policies

| Key | What | Trigger | Cadence | Why |
| --- | --- | --- | --- | --- |
| `zone_item_reset` | a resettable seed pickup | its area comes due on the beat | `beats_between`, while empty | keep pickups available without a permanent strip |
| `gather_node` | a worked ore/herb vein | the beat, after it was worked | per-player after a cooldown | always somewhere to forage; no node-locking |
| `training_dummy` | the sparring dummy | felled in combat | immediate, full health | an endless, safe sparring partner |
| `lethal_recover` | a lethal boss (+ the felled hero) | the boss fells a player | boss to full; player to start | earn the fight again; no corpse-camping |

## The dynamic-spawn primitive

`respawn.pick_room(candidates, weights=None, rng=None)` chooses one spawn site from a pool -- uniform,
or weighted so some rooms draw more often. It returns `""` for an empty pool (a caller with no valid
site spawns nothing, never crashes). This is the building block for the **dynamic** policies the
campaign (Part IV) calls for, so a pickup or a rare can appear at one of several valid places rather
than always the same spot.

## Roadmap (dynamic policies, built on `pick_room`)

- **Wandering pickup** -- a resettable item with a `spawn_pool` respawns at one of several valid
  sites (the "a medicinal herb grows at several places" example). *(next slice: opt-in `spawn_pool`
  on the item schema + the zone reset draws a site.)*
- **Rare-spawn rotation** -- a named rare elite relocates among a zone's rooms on the beat.
- **Population-aware, weather-, season-, reputation-, quest-state-, and faction-gated spawns** --
  these ride the world-simulation layer (factions / season / weather); the `weights` argument to
  `pick_room` is the seam they pull. Season and weather have landed: `kernel/world/climate.py`
  (MOD-04.100) derives `season_of(beat)` / `weather_of(beat)` purely from the world beat (the
  `weather` verb shows the sky), so seasonal-availability and weather-dependent spawns can gate on
  them. Factions / reputation ride the next slice.
