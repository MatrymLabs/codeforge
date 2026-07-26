# Build Order, Room Standards & Implementation Charter

*The bridge from the world design to the world in play. The universe is designed first; the seeds
follow. This document is how the [Continental Atlas](continental_atlas.md) becomes `seeds/aethryn/`
YAML, room by room, region by region — and the standard every room must meet to be worth building.
It folds in the Transportation, Quest, Exploration, Endgame, and Expansion deliverables, because in a
MUD those are all decisions about **rooms, exits, and what lives in them.***

The world is data. A region is built as a seed pack (rooms · npcs · items · doors · zones ·
abilities · quests), validated at boot by the loader gates, extended by generators where volume is
needed (the Great Spiral, the bounty board). The flagship **`aethryn`** seed is the first, playable
slice of this universe — Emberreach's cradle — and the pattern for every Reach that follows.

---

## MUD Room Construction Standards (Deliverable #22)

**Every room is intentionally handcrafted. A room the player forgets is a room not worth building.**
Every room must carry:

1. **Purpose** — why this room exists in the world and in the play flow (a threshold, a landmark, a
   fight, a rest, a secret). No filler corridors: even a passage is *about* something.
2. **Atmosphere & visual identity** — a distinct sensory read in two-to-four sentences. A player should
   know which room they are in with the name hidden. Light, sound, temperature, the state of the
   Forgework, what the last age left here.
3. **Environmental storytelling** — the room *shows* its history without exposition: a scoured wall, a
   stair to nowhere, an ember that will not go out, a door barred from the wrong side. The lore is in
   the description, not in a lecture.
4. **Exits that mean something** — every exit is a real choice; a dead-end is a *destination* (a
   landmark, a secret, a boss), never an accident. Roads are fast lanes; wilds are slow and dangerous;
   verticality (up/down) carries the Spiral and the Cinderdeep.
5. **Connections** — its NPCs, its quest hooks, its resources, its dangers, and its ties to the rooms
   around it. A room belongs to a **zone** (an area with identity and, where it fits, a reset policy).
6. **Hidden detail** — the reward for curiosity: something a careful player finds that a hurried one
   misses. Not every room, but every *region* is dense with them.

**The density test** (Content Density, from the prompt) — every *major* location must answer: *why was
this built · who built it · who holds it now · why come here · what happened here · what stories
emerge · what secrets remain.* If a landmark cannot answer these, it is not finished.

**The mechanical shape** (how it lands in `rooms.yaml`): `name`, a multi-line `desc` that carries
atmosphere + environmental storytelling, and `exits` that resolve within the seed (cross-checked at
boot). Foes, items, and NPCs are placed by label into the room. Level-band the region so the challenge
curve holds. This is the standard the flagship seed already meets and every new region must.

---

## Zone-by-Zone Build Order (Deliverable #23)

Prioritized for implementation. The rule: **build outward from a complete, playable core.** A player
must always have a whole game from wherever the build has reached; never ship a gap papered over.

**Phase 0 — the Cradle (DONE, the flagship `aethryn` seed).** Emberreach's Kindlands: the Waking Shore
spawn, Cinderhearth town, the Cold Cellar, the Ember-road to Emberreach City, the Cinderdeep mouth to
its bottom, the Reachwood, the Cooling-Sea port, the local Ashwaste, and the Great Spiral's procedural
climb to the Sovereign. A complete cradle-to-crown game, L1-255. *This is the proof and the pattern.*

**Phase 1 — deepen the Cradle (ongoing).** Fill Emberreach to AAA density: more Kindlands villages,
the Wardenmarch holds, more capital districts and NPCs with dialogue, more side quests, more of the
local biomes. The world survey's gaps are closed; density is the endless work here.

**Phase 2 — the first sea-crossing: the Quenchmere.** The trade-crossroads Reach is the natural second
continent, because *every* other Reach is reached across its water — build the ferry/ship travel and
Tidewharf, and the whole world becomes reachable. L10-40. (Emberreach's Cooling-Sea shore is the
on-ramp.)

**Phase 3 — the living wild: the Verdance.** The ecology-and-exploration Reach; L20-45. Builds out the
bestiary framework into full food-chain ecosystems — the content that proves the "believable
ecosystems" pillar.

**Phase 4 — the grey and the frozen: the Cinderwaste and the Rimefall.** The salvage Reach (L15-40)
and the museum-of-the-golden-age Reach (L30-50). These carry the setting's two hardest moral
questions (unmaking is holy / touch nothing) into whole landscapes.

**Phase 5 — the molten edge and the sky: the Kollforge and the Sundered Sky.** The high-level surface
Reaches (L40-60, L50-70) and the on-ramp to the vertical endgame. The Sundered Sky's Highgate is the
door to the Great Spiral proper.

**Phase 6 — the deep and the height: the Cinderdeep expansion and the upper Spiral.** The two vertical
frontiers grow without end — the deep downward, the Spiral upward toward the Forge, the First Seed, and
the endgame choice.

Each phase is a seed-pack shipped one region at a time, each region built to the room standard, each
one leaving a *complete* game behind it. Regions can be re-ordered by what the world needs, but the
**complete-core rule** never bends.

---

## Transportation Guide (Deliverable #13, folded)

Travel is exits, and each mode is lore + a mechanic + a restriction:

- **Room-to-room** (the base) — walk the world; the default, slow, dangerous in the wilds.
- **Ember-roads** — permanent Forgework highways between capitals; the fast lanes of the Anvil.
- **Ships & ferries** — the only way across the cooling-seas; the Quenchmere's lifeblood; costed,
  risked (pirates, storms), and the gate to the other Reaches.
- **Gates** — Warden-kept thresholds between distant Forgeworks; rank-gated (you must be *trusted*),
  the endgame of fast travel and the Wardens' whole power base.
- **Way-shrines & mage-portals** — personal, costly, restricted; the recovered fragments of the lost
  True Translation.
- **Vertical ways** — the Coilfoot and the Coils (up), the Cinderdeep mouths (down); progression, not
  convenience.
- **Mounts & sky-craft** — the Verdance's beast-bonds, the Sundered Sky's wind-craft; regional, flavored,
  earned.

Every mode has a **cost, a restriction, and a risk**, so travel is a choice with stakes, never a menu.

---

## Quest Bible (Deliverable #16, folded)

Layered quest structures, all authored as world-events (they self-play from real deeds — enter a room,
fell a foe, take an item — with a fallback verb, per the seed's quest engine):

- **The Main Campaign** — the Emberwright Rememberers' spine: gather the scattered craft, climb the
  Spiral, hunt the Seed-Shards, face the endgame choice. Answered in pieces, re-opened by expansions.
- **Regional Stories** — one per Reach: the local crisis a whole continent turns on (the Relighting of
  the coast, the Ashwastes' Colossus, the Cooling-Sea's drowned lanes, the Rimefall's waking Court).
- **Faction & Guild Campaigns** — rise in a power and re-litigate the world's argument from the inside.
- **Companion Stories** — memorable NPCs who travel with you and have their own arcs.
- **Contracts, Hunts & Mysteries** — the bounty board (generated, at volume) plus handcrafted
  monster-contracts, treasure hunts, and investigations that reward the curious.
- **Hidden & Legendary Chains** — the long, secret questlines behind the world's relics and mysteries;
  the reward for the players who read the world instead of rushing it.

The quest architecture is **discovery, not delivery**: an arc advances because you *did* something in
the world, not because you clicked "accept."

---

## Exploration Guide (Deliverable #19, folded)

**Reward curiosity.** Every region contains hidden rooms, secret passages, environmental puzzles,
ancient journals, lost Forgework, treasure caches, legendary hunts, unique encounters, lore
discoveries, and rare resources — placed so that the player who *reads* the world is paid for it. The
density test is the guarantee: a Reach is not done until curiosity is dense enough that no two players
find the same secrets first.

---

## Endgame Content Roadmap (Deliverable #20, folded)

The endgame is not a final boss; it is a **destination and a choice**:

- **The Great Spiral** — the vertical climb to the Forge, an elemental gauntlet of themed Coils to the
  Sovereign at the ceiling and beyond, toward the raw Kindling where the world's laws go soft.
- **The Cinderdeep** — the descending frontier, deepening without floor toward the purest Unforged.
- **Ancient Rituals & Raids** — multi-Forger works: relight a dead capital, seal a Reach's Unforging,
  open a sealed Coil — magic that takes a guild.
- **The Seed-Shard Hunt** — gather the fragments of the First Seed across every Reach and age.
- **The Choice** — having relearned how to make a world: *reforge the First Seed, or leave it broken?*
  The Silent Anvil's question, made the player's, and the thing the whole campaign is built to earn.

## Expansion Roadmap (Deliverable #21, folded)

The world is built to grow forever: **each Reach is an expansion**, **each era is a content tier** (the
Kindling a raid, the Emberwright age a legendary chain, the Unforging a recurring world-event, the
Long Cinder a dungeon-age), **each faction a questline**, and the two vertical planes grow endlessly up
and down. New Reaches ship new cultures, ecosystems, jobs, and relics; the world's central argument
(guard, free, or govern the craft) travels with them and never resolves. The map does not end — by
design.

---

## The through-line

Build the world first; the systems follow. Build outward from a complete core; never ship a gap.
Every room handcrafted; every region dense enough to reward the curious; every Reach capable of
supporting its own RPG. The technology exists only to bring this universe to life — and the flagship
seed is the proof that it can.
