# Aethryn Seed Reconciliation (source, tiers, coverage)

*This doc traces Aethryn's canon back to its external source and states, honestly, what the code
already encodes and what the source still carries that the code does not. It exists because the
authoritative seed arrived after the first implementation, uses its own canon vocabulary, and lives
alongside an older, superseded world design in this repo. No claim without correspondence: the
coverage matrix below is checked against the shipped seed, not asserted.*

## The authoritative source

The single external source of Aethryn's canon is the **Aethryn Coding Seed v0.1** pack:

| File | What it is |
|------|-----------|
| `PROMPT_FOR_CODING_AI.md` | the build brief (the prompt this campaign implements) |
| `AETHRYN_WORLD_BIBLE.md` | the narrative + world-structure bible (14 regions, Seven Crowns, factions, magic) |
| `aethryn_world_seed.json` | the structured source of truth (regions, anchors, adjacency, seas, factions, generation contract) |
| `GENERATION_CONTRACT.md` | the compact generator contract (area recipe, content ratios, review gate) |
| `AETHRYN_WORLD_MAP.jpeg` | the world map image |

It was received as `~/Downloads/aethryn seed/` (bundled as `Aethryn_Coding_Seed_v0.1.zip`). The pack
is **not vendored into this repo**: its prose uses long-dash glyphs this repo forbids fleet-wide, and
`seeds/aethryn/canon.yaml` is already the machine-checkable snapshot of its locked canon. Keep the
pack as the cited external source; keep `canon.yaml` as the on-disk, test-gated encoding of it.

## Doc hierarchy (which file is authoritative)

```
aethryn_world_seed.json + AETHRYN_WORLD_BIBLE.md   (external source, v0.1)
      -> seeds/aethryn/canon.yaml                  (machine-checkable snapshot; kernel/world/canon.py gates it)
      -> docs/aethryn_lore_bible.md                (the readable companion)
      -> docs/aethryn_seed_reconciliation.md       (this file: crosswalk + coverage)
```

**Legacy warning.** `docs/world_bible.md` and everything under `docs/world/` (continental_atlas,
faction_encyclopedia, global_history, magic_encyclopedia, bestiary, build_order, ...) are the
**earlier "Forge / Unforging" world design**. None of them mention Netharion or the divine strike.
Where they conflict with the Aethryn Coding Seed, the seed wins and they are superseded. Treat those
files as a legacy alternate, not current canon.

## Canon tier crosswalk

The seed labels every record C0 to C4. This repo's `kernel/world/canon.py` uses `CANON_STATUSES`.
They line up like this:

| Seed tier | Meaning | This repo's `canon_status` |
|-----------|---------|----------------------------|
| **C0** Fixed canon | must never be contradicted | `CANON_LOCKED` |
| **C1** Anchored canon | core fact fixed, details may expand | `CANON_LOCKED` (name/band frozen) |
| **C2** Provisional seed | supplied to start; may be revised | `CANON_WORKING` |
| **C3** Generated local canon | new local detail; must fit C0 to C2 | `GENERATED_LOCAL` |
| **C4** Rumor / belief | may be false, biased, or contradictory | `RUMOR` |

Conflict resolution is identical in both: C0 wins, then C1; C2 may be revised; C3 is regenerated or
edited; C4 is allowed to conflict because it is belief, not fact.

## Coverage matrix (built vs. gaps)

Checked against `seeds/aethryn/` and `kernel/world/` on the day this doc landed.

### Built and faithful to the source
- **14 regions**: names and threat bands **all match** the seed (Veridia 1-30 through The Voidscar
  250-300). `seeds/aethryn/canon.yaml`, gated by `check_canon`.
- **7 Seven Crowns**: map names, mythic titles, and **region assignments all match** the seed.
- **6 established facts** (advanced civilization, imitation, Netharion the first artificial god, the
  deliberate strike, the withdrawal, uneven survival) and **7 open questions** kept unresolved.
- **6 named seas** (Western Ocean, Northland Sea, Central Sea, Sundaram Sea, Southern Ocean, Eastern
  Ocean).
- **All 35 canonical anchors** present in `settlements.yaml` / `dungeons.yaml` by their canon names
  (Red Dune and Cinderfire were reconciled from the earlier `Red Dunes` / `Cragfire`).
- **The 8 world-scale faction seeds** (Veiled Covenant, Crownseekers, Netharian Concord, Wardens of
  the Scars, Ashforged Houses, Deep Archive, Tidebound League, Greenward Compact) live in
  `canon.yaml` as `world_factions` (CANON_WORKING / C2), validated by `canon.py`. The Surveyor's
  `faction_references` check (folded into `world validate`) catches any location that names an
  unknown faction. (Distinct from the legacy `kernel/world/factions.py`, which models the game's
  Orders and their standings, not these world powers.)
- **Collective-term tiers.** `canon.yaml`'s `collective_names` carries each of the six names for the
  Seven Crowns with its own tier and worldview: Seven Crowns and Seven Wounds are `CANON_LOCKED`
  (C1, neutral / common), the four ideological names are `RUMOR` (C4, belief), each with its `usage`.
  Validated by `canon.py` (`collective_names`).
- **The region adjacency graph.** `seeds/aethryn/world_graph.yaml` encodes every region's land
  neighbours and bordering seas from the seed's `adjacent_regions` / `water_edges`;
  `kernel/world/worldgraph.py` validates it against canon and computes reachability. All 14 regions
  are reachable from the spawn by land or sea. This powers `world find-unreachable`, `world inspect`,
  and `world graph`, and folds reachability into `world validate`.
- **The generation contract, as data.** `seeds/aethryn/generation_contract.yaml` encodes the seed's
  GENERATION_CONTRACT: the 16 `required_area_fields`, the historical layers, the minor-area archetype
  mix (35 / 20 / 20 / 15 / 10), the dungeon grammar, and the forbidden changes.
  `kernel/world/generation_contract.py` validates it and exposes the checks (`missing_fields` for one
  area, `distribution_gaps` for a batch). **The cave forge is contract-compliant**: every generated
  cave carries all 16 required fields (identity, historical layer, livelihood, conflict, world-clue,
  provenance, ...), composed deterministically, and its `_validation_report` fails if any is missing.
- **The generator half of the brief**: the deterministic cave forge (`kernel/world/caves.py`), the
  area bench (`kernel/world/area_store.py`), and the read-only validators (`kernel/world/survey.py`,
  the `world` CLI). Generated content is stamped `GENERATED_LOCAL` (C3) and may raise a forbidden
  topic only as a `RUMOR` (C4).

### Gaps (in the source, not yet in code)
- **Water edges as travel routes.** `world_graph.yaml` records each region's bordering seas and uses
  them for reachability, but the code does not yet model sea *routes* as travelable player links (a
  port-to-port journey), only as region adjacency.
- **Archetype ratio weighting.** The cave forge classifies each cave into an archetype and
  `generation_contract.distribution_gaps` can measure a batch against the 35 / 20 / 20 / 15 / 10
  mix, but the forge still picks a subtype uniformly, so a batch is not yet actively steered to hit
  the target mix. Weighting subtype selection to the ratios is a future refinement.
- **The magic / technology framework** (Crowncraft, Theomimetic arts, Scarcraft, and the four power
  channels) and the **historical-arc age names** (Age of Near Gods, Age of Plenty, the Imitation,
  the Starfall, ...) are C2 lore in the bible with no home in canon data yet.

## Forbidden changes (the guardrail the generators already honor)

The seed's non-negotiables, restated so the generators keep obeying them: never rename Aethryn, never
make the divine strike accidental, never make Netharion a natural-born god, never erase or replace a
map region, never relocate a Seven Crown without approval, and never resolve an open mystery as
objective truth. Generated content (C3) may build local detail on top; forbidden global canon may
surface only as a marked `RUMOR` (C4), which is exactly what the cave forge does today.
