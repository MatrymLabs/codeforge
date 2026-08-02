# The Aethryn Lore Bible

*The concise, authoritative canon of Aethryn: only what is **established** (CANON_LOCKED) and
**working** (CANON_WORKING). Generated content and local authored lore build on top of this and may
never contradict it. The machine-checkable form of this canon is `seeds/aethryn/canon.yaml`, enforced
by `kernel/world/canon.py` (`check-canon`); this file is the readable companion.*

> **Source and reconciliation.** This canon derives from the external **Aethryn Coding Seed v0.1**
> pack (its world bible + `aethryn_world_seed.json`). For the tier crosswalk (the pack's C0 to C4
> labels vs. this repo's `canon_status` ladder) and an honest built-vs-gaps coverage matrix, see
> `docs/aethryn_seed_reconciliation.md`.

> **Note on an older draft.** `docs/world_bible.md` is an earlier, *different* design of Aethryn (a
> "Forge / Ember / Unforging" metaphysics). It is **superseded** by this Lore Bible, which matches the
> shipped seed (the fourteen regions, the Seven Crowns, Netharion). Treat `world_bible.md` as a legacy
> alternate; **this** file is the canon.

---

## The Premise (CANON_LOCKED)

Aethryn once held an extraordinarily advanced civilization to which **the gods were openly present**,
giving abundance, healing, protection, and knowledge. Divine intervention was so constant that
miracles became ordinary, and mortals began to study divine acts as **reproducible processes**.

Ancient technology grew so advanced it was **indistinguishable from magic**. Mortals learned to
imitate healing, biological creation, weather control, matter shaping, transportation, communication,
prophecy, memory preservation, and soul manipulation.

The old civilization created **Netharion, the first artificial god**: proof that divinity could be
*manufactured* rather than inherited or granted by the established gods.

The gods judged this an existential threat. They **deliberately fragmented a celestial body and aimed
its pieces at the great cities**, to end technological and divine parity, to destroy the records,
manufacturing, and institutions that reproduced divine power, and to hold surviving cultures below
the level where they could rebuild it. **The strike was intentional. The cities were intentionally
targeted.** Afterward, the gods **withdrew** from open participation in the world.

The modern world is at once a **wounded world** shaped by precise celestial impacts and a world
**living after its gods left**. Ancient technology survives unevenly (ruins, dormant infrastructure,
automated facilities, broken constructs, misunderstood relics, sacred machines, hazardous devices,
knowledge-fragments), and cultures differ in how much they understand, preserve, recover, or conceal.

## Questions the world keeps OPEN

These are **never answered** in generated content, only raised through contradictory rumours, beliefs,
damaged records, and faction interpretation:

- Whether the gods' fear was justified.
- Whether Netharion was benevolent, dangerous, or both, and whether Netharion survived.
- Whether all gods supported the destruction, and whether some still watch technological progress.
- Whether the old civilization was about to damage reality.
- Whether the gods acted to preserve creation, preserve their authority, or both.

---

## The Seven Crowns (CANON_LOCKED)

The old civilization's seven principal centres. Their **map names** are the public names; the
**mythic titles** supplement, never replace, them. A speaker's chosen collective name reveals their
worldview: *The Seven Crowns, The Seven Wounds, The Seven Blasphemies, The Murdered Crowns, The Seven
Lessons, The Seven Engines.*

| Map name | Mythic title | Region | Ancient function | Modern condition |
|---|---|---|---|---|
| **The Flamewrought Forge** | The Ember Crown | Ashen Wastes | manufacturing, material shaping, constructs, weapons, large-scale engineering, abundance-machinery | ruined industry, volcanic instability, machines running obsolete instructions, malformed products |
| **Netharion's Throne** | The God-Mirror | The Voidscar | the creation of Netharion; artificial divinity, soulcraft, belief-powered systems, constructed consciousness | the deepest wound; reality damaged, laws in conflict, Netharion's status uncertain |
| **The Spire Nexus** | The Skychain | Skyward Spires | aerial transit, long-distance transport, communication, celestial observation, route coordination | floating land, broken pathways, transit partly still active |
| **The Crystal Labyrinth** | The Memory Deep | The Deepreach | archives, preserved memories, artificial intelligences, records, predictive systems | underground and fragmented; contradictory records, passages that rearrange or deceive |
| **Korvash Crater** | The Measured Throne | Korvash Highlands | governance, law, resource coordination, administration, command | destroyed to a crater; remnants of command and authorization, possible oath/identity phenomena |
| **Heart of Xil'nath** | The Verdant Loom | Xil'nath Jungle | healing, agriculture, biological design, ecosystem management, engineered life | runaway growth, unstable abundance, artificial and natural ecosystems grown inseparable |
| **The Maelstrom Rise** | The Thousand Doors | The Shattered Isles | maritime transport, distribution, long-distance gates, global trade | shattered islands, unstable routes, storms, portals that may open to the wrong destination |

---

## The Fourteen Regions (CANON_LOCKED names + threat bands)

Threat bands are *recommended*, not walls: a player may enter early, but the world should make the
risk legible.

| Region | Threat band | Identity (short) |
|---|---|---|
| Veridia | 1 to 30 | green starter lands: farms, rivers, old roads |
| Duskwood Vale | 20 to 50 | dark forest, mist, swamps, obscured history |
| Caeloria | 30 to 60 | established kingdom, doctrine vs. ancient evidence |
| Eldryn Forest | 50 to 80 | ancient forest, deep ecological memory |
| Frostspire Peaks | 60 to 90 | tundra, glaciers, isolated strongholds |
| Zhaar Desert | 80 to 130 | desert, obsidian, buried cities, exposed remains |
| Xil'nath Jungle | 90 to 150 | jungle, runaway biological systems, engineered life |
| Thalorin | 100 to 140 | mountains, fortresses, mines, contested resources |
| Ashen Wastes | 120 to 170 | volcanic waste, industrial ruins, impact damage |
| Korvash Highlands | 150 to 200 | mountains, ruined command infrastructure |
| The Shattered Isles | 180 to 230 | archipelago, storms, broken gateways, piracy |
| Skyward Spires | 200 to 250 | floating islands, celestial machinery |
| The Deepreach | 100 to 250 | vast underground realm, archives, mines |
| The Voidscar | 250 to 300 | the deepest wound: unstable laws, artificial divinity, endgame |

**Named waters** (for travel + adjacency): The Western Ocean, The Northland Sea, The Central Sea,
The Eastern Ocean, The Sundaram Sea, The Southern Ocean.

---

## Canon authority ladder

Every world record carries a `canon_status`:

- **CANON_LOCKED**: never changed by generators (the name Aethryn, the regions, the divine strike,
  the targeted cities, the withdrawal, Netharion as the first artificial god, the Seven Crown functions).
- **CANON_WORKING**: revisable later without a destructive migration (mythic titles, local
  interpretations, provisional ruin functions, threat bands, working terms like "the Fall").
- **AUTHORED_LOCAL**: developer local lore that does not redefine global canon.
- **GENERATED_LOCAL**: deterministically generated caves, rooms, minor NPCs, encounters, rumours,
  treasures.
- **RUMOR**: in-world information that may be false, distorted, ideological, or incomplete.

## Narrative style (working guidance)

The world should feel *ancient, interconnected, and materially real*. Describe ancient technology
through **function, material, behaviour, and incomplete understanding**: a "holy fountain" may be a
damaged purification system; a "guardian spirit" an ancient construct; a "curse" radiation, biological
alteration, metaphysical damage, or something genuinely supernatural. **Do not explain every mystery.**
No faction is uniformly right or wrong; not every ruin is a military facility; not every cave hides a
world-changing secret.
