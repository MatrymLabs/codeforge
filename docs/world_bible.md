# The Forged World: the CodeForge Canonical World Bible

*The flagship Seed. The reference world that proves the engine. Aethryn is not another fantasy
setting; it is the living demonstration that CodeForge's engineering philosophy and its world
philosophy are the same philosophy, read twice.*

> **The dual reading (read this first).** Every system in this bible has two true faces. In the
> **fiction**, the Forge is the force that shapes reality and a Forger is one who has learned to
> reshape it. In the **engine**, the Forge is CodeForge and a Forger is a builder who authors
> content and parts. Ember is raw potential in the story and unshaped world-data in the code. A
> Seed is a forged world-in-potential and a `seeds/*.yaml` pack. A Blueprint is a smith's schema
> and a `parts/blueprint.py` artifact. The Great Chronicle is the world's memory and the
> `chronicle/` ledger. The Wardens who keep the Gates are the rank system and the operations
> roles. This correspondence is deliberate and load-bearing: **every mechanic exists because the
> world supports it, and every subsystem can become a reusable CodeForge component** precisely
> because the lore was designed to mirror the architecture. Where the two readings could drift,
> the world lore yields to the engine law (state is canonical; the world is data; the tick is the
> only door).

Naming: no world detail below is hard-coded in Python. Lore lives here and in `seeds/*.yaml`; the
engine stays genre-neutral (see `docs/vision_resync.md`, `docs/frameless_python.md`).

---

## 1. World Bible (the premise)

**Aethryn is a world that was made, and remembers being made.** It was not born; it was **Forged**
from **Ember**, the living substance of raw possibility. Nothing in Aethryn is eternal and nothing
is truly random: every mountain, river, beast, and law was shaped by a Forger, and a shape once
made can be unmade and reforged by one who knows how. This is the first law of the world and the
first law of the engine: **creation is more powerful than destruction, and knowledge changes what
is real.**

Ordinary people live inside the Forged World without ever touching the Forge. Adventurers begin as
such people. But scattered through Aethryn is the lost craft of **Forging** itself, and a rare few
recover it, piece by piece, and become **Forgers**: those who can pick up Ember and give it lasting
shape. A Forger is not a wizard casting a spell that fades. A Forger *builds*, and what they build
stays: a blade, a bridge, a law, a room, eventually a world. The endgame of Aethryn is not to
defeat a final enemy. It is to become a maker of worlds, and the world's oldest mystery is why the
first makers stopped.

The core tension: **the Unforging.** Long ago the greatest work of the First Forgers, the **First
Seed**, was sundered, and the knowledge of high Forging shattered across the world and the ages.
Aethryn today is the **Age of Rekindling**: the craft is being pieced back together, and every
player who learns to Forge is both a hero and a small, dangerous experiment in whether a broken
world should be given the power to remake itself again.

---

## 2. World Timeline (major historical eras)

1. **The Kindling.** The Forge burns; Ember pours; the first shapes cool into the **Anvil** (the
   world's surface) and the **Great Spiral** (its ascending heart). No people yet, only made things.
2. **The Age of the Emberwrights (the First Forgers).** The Emberwrights walk the cooling world and
   Forge the first living kinds, the first cities, the first laws. Craft is open; anyone may learn.
   This is the golden age the world half-remembers as impossibly bright.
3. **The Weaving of the First Seed.** The Emberwrights attempt their masterwork: a self-Forging
   world, a Seed that could grow and remake itself without them. It is the height of the craft and
   the beginning of the fall.
4. **The Unforging (the Sundering).** The First Seed breaks. Accounts differ on whether it was
   sabotage, hubris, or a flaw in the Seed itself. High Forging is scattered; the Emberwrights are
   lost or hidden; whole regions are **unmade** into the **Cinderdeep**. Reality becomes fragile.
5. **The Long Cinder (the dark age).** Forging is feared and forbidden. The **Wardens** arise to
   guard the surviving Gates and Seeds so no half-taught Forger can Unforge the world again. Most
   craft is lost; what remains is guarded, ritualized, gated.
6. **The Age of Rekindling (now, the play era).** The Gates begin to open. Ember flows freely enough
   that ordinary adventurers stumble into fragments of the old craft. Guilds, kingdoms, and Wardens
   race to gather the scattered knowledge. The world can be rebuilt, or Unforged again. This is
   where the players stand.

*(Every era is an expansion hook: the Kindling is a raid tier, the Emberwright age a legendary
questline, the Unforging a recurring world-event, the Cinderdeep an underworld continent.)*

---

## 3. Cosmology (the planes)

Aethryn is a layered work, not a sphere:

- **The Forge (the source).** Not a place you visit but the origin of all Ember and shape. Its
  radiance is **Forgelight**. To draw near it is to gain the power to make and the risk of being
  unmade. High-Forger endgame reaches toward it.
- **The Anvil (the material plane).** The living world's surface: continents, oceans, kingdoms,
  weather, day and night. Where nearly all play happens. Solid, persistent, walkable. The classic
  MUD overworld.
- **The Great Spiral (the ascending plane).** A vast forged structure of stacked **Coils** rising
  from the Anvil's heart, each Coil a band of the world closer to the Forge, each threshold a
  **Gate** kept by a **Warden**. Climbing the Spiral is the vertical endgame; the existing
  `spiral-ascent` Seed is its first coils.
- **The Cinderdeep (the lower plane).** What the Unforging unmade: caverns, drowned cities, and
  half-real regions where shapes never fully cooled. The underworld, dungeon frontier, and home of
  the **Unforged** (entropy made hostile).

Three substances cross the planes: **Ember** (raw potential, glowing), **Cinder** (spent Ember,
grey, the ash of unmaking), and **Forgelight** (refined creative fire, rare and coveted). The whole
metaphysics is one loop: Ember is shaped into world, world decays to Cinder, Forgers rekindle
Cinder back to Ember. Creation and entropy, forever, and the player leans it toward creation.

---

## 4. Geography

**The Anvil (surface).** A single supercontinent broken by inland seas, chosen so a MUD map can grow
outward for decades without a "the world ends here" wall. Named regions of the starting continent,
**Emberreach**:

- **The Kindlands** (starting region): temperate river-valleys where the first Rekindling forges
  relit. Home of the first capital and the tutorial coast.
- **The Wardenmarch**: fortified highlands where the Wardens hold the old Gates. Law-heavy, orderly.
- **The Ashwastes**: a desert of Cinder where a region was half-Unforged; salvage, danger, rare Ember.
- **The Deeproot Reaches**: primeval forest and swamp where wild Ember grows into strange life.
- **The Sundermere**: a drowned coast of ruins from the Unforging; ports, wrecks, and pirate-salvagers.
- **The Coilfoot Range**: mountains at the base of the Great Spiral, where the ascent begins.

**Roads and travel.** The **Ember-roads** (old paved Forgework) connect capitals; between them lie
wilderness, ruins, and hidden ways. Movement is room-to-room; roads are fast lanes, wilds are slow
and dangerous.

**Vertical and deep.** Above: the **Coils** of the Great Spiral (ascent zones). Below: the
**Cinderdeep** (dungeon continent). This gives horizontal exploration (the Anvil), vertical
progression (the Spiral), and a descending frontier (the Cinderdeep), so the map extends in three
directions forever.

**Features that must exist (classic MUD spread), and their lore hook:**
mountains (Forgework skeleton of the world) · forests (wild Ember growth) · swamps (Cinder seeping
up) · deserts (Unforged waste) · oceans (the cooling-seas, first-quenched) · underground (the
Cinderdeep) · ruins (Unforging scars) · capitals (relit Forge-cities) · ports (cooling-sea trade) ·
dungeons (broken Seeds and Warden vaults).

---

## 5. Political Structure

Power in Aethryn follows the one thing that matters: **who controls Forging, and how much they
trust others with it.** Three great answers, in tension:

- **The Warden Concord** (control): the order that survived the Long Cinder by locking the craft
  behind Gates. Law-first, cautious, gate-keeping. They believe the Unforging proves that Forging
  must be licensed, tested, and rank-gated. *(Engine reading: the Wardens are the rank system and
  the quality gates. Their whole politics is `authorization before capability`.)*
- **The Free Forges** (creation): guilds and city-republics who believe the craft belongs to
  everyone and that gate-keeping is how knowledge dies. Meritocratic, chaotic, generative.
- **The Kindled Crowns** (order): the classic feudal kingdoms who use Forging as statecraft, a
  managed resource for armies, walls, and roads. Pragmatic, hierarchical, stabilizing.

No faction is the villain. The world's live conflict is the unresolved argument between guarding the
craft, freeing the craft, and governing the craft, and player factions and world-events keep
re-litigating it. This is the political engine that can run for twenty years without resolution.

---

## 6. Cultures

Cultures are shaped by their **relationship to Ember**:

- **Reachfolk** (the Kindlands): open, optimistic river-valley people; the "everyman" starting
  culture; believe anyone can learn to Forge.
- **Wardenkin** (the Wardenmarch): disciplined, ritual, oath-bound; measure worth by what you can be
  trusted to make.
- **Ashborn** (the Ashwastes): survivors of an Unforging; fatalistic, resourceful, salvage-minded.
- **Deeprooted** (the Reaches): animist; treat wild Ember as sacred and Forging as negotiation with
  a living world.
- **Merewrights** (the Sundermere): seafaring salvagers and traders; cosmopolitan, mercantile.

Cultures are content, not mechanics: they flavor starting areas, dialogue, and reputation, and new
ones ship with new continents.

---

## 7. Factions

Beyond the three great powers, playable/allyable factions:

- **The Emberwright Rememberers**: scholars hunting the lost First-Forger craft (the main-story
  faction).
- **The Cinder Circle**: those who study the Unforged and the entropy-craft; feared, sometimes
  necessary.
- **The Salvage Guilds**: recover Forgework from ruins (the crafting/economy faction).
- **The Gate-Breakers**: radicals who want every Gate opened now, consequences be damned.
- **The Quiet Anvil**: a hidden order that believes some things should stay Unforged (the "should
  this power exist at all" conscience of the world).

Factions grant reputation, quests, access, and standing conflicts. Any can become a full expansion.

---

## 8. Guilds

Guilds are the player's institutional home and the mechanical spine of professions. They are
**Forge-Orders**, each a hall (a `guild hall` room-cluster) that teaches, ranks, and equips:

- **The Warcraft Orders** (combat jobs): the Vanguard, the Pathfinder, the Coilwright-martial.
- **The Making Orders** (crafting professions): Smithing, Enchanting, Inscription, Alchemy, Forging
  proper (the meta-craft).
- **The Gathering Orders** (gathering professions): Emberreaping, Mining, Foraging, Salvage.
- **The Knowing Orders** (support/knowledge): Chroniclers (lore + the Archive), Wardens
  (administration + gates), Cartographers (exploration).

Guild rank is earned, gates content, and doubles as the in-world face of the engine's rank ladder.
A guild hall is a reusable room-template; new guilds are new Seeds of a hall + a questline + a
profession.

---

## 9. Religions

Faith in Aethryn is faith about *making*:

- **The Church of the First Flame** (orthodox): reveres the Forge as creator; holds that to Forge is
  to worship, and to Unforge is the one sin. State religion of the Kindled Crowns.
- **The Cinder Mysteries** (heterodox): revere the loop; hold that unmaking is holy too, because
  without Cinder there is no new Ember. Persecuted, resilient.
- **The Silent Anvil** (mystic): worship the *potential* in unshaped Ember; believe the greatest act
  is restraint, to leave some Ember unforged. The world's conscience, again.
- **Ancestor-Forging** (folk): every culture keeps the names of its dead in Forgescript, believing a
  remembered maker is never fully unmade. *(Ties directly to the Great Chronicle: to be recorded is
  to persist.)*

Religions are content: temples, blessings (buffs), pilgrimages (quests), holy days (world events).

---

## 10. History (world mysteries)

The living questions that drive the main story and never fully close:

- **Why did the First Seed break?** Sabotage, flaw, or intent?
- **Where did the Emberwrights go?** Dead, ascended into the Forge, or hidden in an unreached Coil?
- **What is at the top of the Great Spiral?** The Forge itself, or another Anvil, worlds all the way
  up?
- **Is the Cinderdeep the world's grave or its compost?** Can the Unforged be rekindled, or only
  contained?
- **Should the craft be relearned at all?** The world already broke once under it.

These are designed to be *answered in pieces and re-opened by expansions*, so the mystery never
runs dry.

---

## 11. Economy

The economy is a **materials-and-making** economy, grounded so player crafting has real demand:

- **Ember** (the base resource, gathered) refines into **Emberstuff** (crafting material) and, rarely,
  **Forgelight** (the prestige material).
- **Cinder** is the byproduct/currency of the salvage economy.
- **Marks** (minted Forgework) are the common coin; **Warden Seals** and **Guild Tokens** are
  faction currencies gating faction goods.
- **Value flows from scarcity of shape, not scarcity of stuff:** raw Ember is common, but the
  *knowledge* to shape it well (a masterwork Blueprint, a rare recipe) is the real wealth. This
  keeps a knowledge economy alive alongside a goods economy.
- **Player trade, markets, auctions, and banks** are first-class (see Player Systems). Crafters are
  the backbone: nearly every non-legendary item can be player-made, so gathering and making sustain
  the market.

*(Engine reading: the Hardware Store is the in-world Making economy made literal. A masterwork
Blueprint that many games reuse is the most valuable thing a Forger can produce, in fiction and in
code.)*

---

## 12. MUD Architecture

Aethryn is built on classic MUD bones so it reads instantly to a MUD veteran and maps cleanly to the
engine's spatial model:

- **Room** (the atom): one location, described in text, holding items/NPCs/players and exits.
- **Area** (a hand-authored cluster of rooms: a town, a dungeon, a forest).
- **Zone** (a themed group of areas sharing spawns, weather, and a Warden of the March).
- **Region** (a continent-band: the Kindlands, a Coil, a Cinderdeep layer).
- **Exits**: normal, **secret** (found by exploration), **one-way** (falls, slides, Unforging
  drops), **portals** (Gate-fixed fast travel), and **transport** (roads, ships, Coil-lifts).
- **Persistent world state**: rooms remember what was done to them (a broken bridge stays broken
  until reforged); NPCs, weather, and day/night persist; player housing and guild halls persist.
- **Respawning**: mobs and resources respawn on Ember-tides; bosses on longer cycles; some things,
  once Unforged, do not return until a quest reforges them.
- **Named venues that must exist** (each a reusable room-template): capitals, ports, markets,
  libraries/archives, academies, research facilities, crafting halls, guild halls, player housing,
  world-boss lairs, hidden areas, ruins.

Architecture law (inherited from the engine, stated in-world): **the map is data, described in
`seeds/*.yaml`; the room text is a projection of room state and never mutates it; only validated
world logic changes what is real.** A builder who writes a room writes data, not code.

---

## 13. Combat Architecture

Combat in Aethryn is **a persistent state of the living world, never a separate screen.** When an
encounter begins, nothing about the world pauses or swaps out: the player stays exactly where they
are, other players can see the fight, help, or walk past, and the room keeps ticking. An encounter
is a *condition on a room and its participants*, entered when hostilities start and left only when
an ending condition fires:

**victory · defeat · escape · surrender · encounter reset · scripted event · administrative action ·
any other defined ending condition.**

The player never leaves the world; combat is *part of* the world. This is the exact opposite of a
menu-driven JRPG battle screen, and it is why combat can host bystanders, environmental hazards,
rescues, and reinforcements: it is happening *in the room*, not in a pocket dimension.

*(Engine reading: an encounter is world-state on the room/session, advanced by the same
`handle_command` tick that runs everything else. Combat is not a special mode; it is the tick,
applied to hostility.)*

---

## 14. Combat Tick System (cadence)

Aethryn combat is **continuous, driven by world ticks**, with the tactical feel of measured
turn-based play but the living cadence of a MUD/MMORPG, never a frozen menu. Each combat tick
advances, in a fixed order so outcomes are deterministic and reproducible:

1. **Weapon timing / auto-attacks** (each weapon strikes on its own speed).
2. **Cooldown recovery** (abilities tick toward ready).
3. **Resource regeneration** (Health, Mana, Stamina regen per their rules).
4. **Status effects, damage-over-time, healing-over-time** (burns, bleeds, mends).
5. **Environmental hazards and scripted encounter mechanics** (the room fights too).
6. **NPC AI decisions** (enemies keep choosing until the encounter ends).
7. **Resolution and ending-condition check.**

Between ticks, **players keep issuing commands**; a command queues and resolves on the tick, so
timing and cooldowns matter and spam does not. Abilities operate independently through cooldowns;
weapons swing on their own timers; enemies never "wait for your turn." The encounter stays alive.

Combat rewards, by design: **preparation, timing, positioning, resource management, job synergy,
teamwork, encounter knowledge, adaptation, and intelligent decisions** over reflexes. Slow enough to
think, live enough to feel real.

*(Engine reading: the combat tick is a scheduled, ordered, pure-function advance of encounter state
(mirroring `parts/bench.py`'s deterministic tick discipline and architecture law 1). Its order is
fixed so it is testable; a parity test can pin tick math the way restore-math is pinned today.)*

---

## 15. Command Philosophy (the command system)

Aethryn is **command-driven to its core**: the player speaks verbs to the world, and the same verb
grammar spans exploration, combat, making, and governing. Design tenets:

- **Verbs are the interface.** Short, guessable, classic MUD verbs; the tick routes on the verb.
- **One clear responsibility per verb**, explicit target grammar (`verb <noun>`, `verb <noun> with
  <noun>`), input validated loudly (a bad target fails with help, never a crash).
- **Namespaced by authority** (mirrors `parts/commands.py`): **CORE** verbs anyone uses, **`@`-verbs**
  for Wardens/staff (rank-gated), **Seed** verbs a world may add without colliding.
- **Accessibility and quality-of-life are first-class**, not add-ons: aliases, macros, autocomplete,
  history, configurable output, screen-reader-friendly text.

Command families (each a section of the First 100, below): movement, combat, communication, social,
inventory, equipment, trading, crafting, building, research, conversation, exploration, party, guild,
help, learning, accessibility, search, aliases, macros, autocomplete, history, configuration,
administration, builder tools.

---

## 16. Item Taxonomy

Everything an item can be, grounded in the Forge economy so each type has a maker and a market:

- **Weapons** (melee, ranged, focus/casting) · **Armor** (light/medium/heavy, by slot) ·
  **Accessories** (rings, seals, charms).
- **Relics** (minor Forgework with a bound effect) · **Artifacts** (major, often quest-locked,
  sometimes sentient First-Forger works).
- **Quest items · Consumables** (potions, rations, Ember-draughts) · **Currencies** (Marks, Cinder,
  Seals, Tokens).
- **Resources / crafting materials** (raw Ember, ores, reagents) · **Tools** (gathering + profession
  equipment: the modular forge wrench is canon).
- **Blueprints** (crafting schemas) · **Books · Recipes · Maps · Research notes** (the knowledge
  economy; readable, tradeable, gating).
- **Quality and progression axes** (orthogonal, so items have depth): **quality levels** (crude →
  masterwork), **upgradeable** (temper, reforge), **enchantments · sockets · sets**, **rarity**
  (common → rare → unique → legendary), and **randomized loot** rolled within honest bounds.

*(Engine reading: an item is validated data with a frozen `lowercase_snake_case` label and a
`display_name()` for render; a Blueprint item is the in-world twin of a `parts/blueprint.py` schema;
"masterwork" is a quality tier, not a hard-coded value.)*

---

## 17. Profession System

Professions are how a player *becomes a maker*, structured as **Orders** (guilds) with ranks and a
questline:

- **Combat roles** (from Jobs): frontline (Vanguard), skirmish (Pathfinder), support/control
  (Coilwright), each with resource identity and cooldown kit.
- **Crafting professions**: Smithing, Enchanting, Inscription, Alchemy, and the meta-craft
  **Forging** (making the tools and Blueprints other crafts use).
- **Gathering professions**: Emberreaping, Mining, Foraging, Salvage.
- **Knowledge professions**: Chronicling (the Archive), Wardenship (administration), Cartography
  (exploration).

A character has a **Job** (combat identity) and may learn **professions** (making/gathering/knowing)
in parallel. Advancement is by *doing and discovering*, not grinding alone: you rank up a profession
by making, researching, and completing Order quests. Professions interlock (a gatherer feeds a
crafter feeds a Forger feeds the world), giving the economy its spine.

*(Engine reading: Jobs are `seeds/*/jobs.yaml`; a profession is a Seed of a skill tree + recipes +
an Order hall + a questline. The meta-craft Forging is the in-world name for authoring reusable
parts, the Hardware Store.)*

---

## 18. Crafting System

Making is the beating heart of Aethryn, and the loop is designed to *never* be a black box:

1. **Gather** raw Ember and materials from the world (nodes, salvage, drops).
2. **Craft** from a **Blueprint** using a station (forge, bench, altar, lab), consuming materials
   and Stamina/Mana.
3. **Research** to *discover new Blueprints*: combine known ingredients, read Research notes,
   experiment. Discovery is a first-class verb, and failed experiments teach.
4. **Experiment and masterwork**: quality is rolled within a band set by skill, tools, and material
   quality; a masterwork is a rare high roll worth trading.
5. **Quality levels** (crude → fine → superior → masterwork → **relic-grade**) reward skill and
   material investment.
6. **Player trade and economy**: crafted goods flow to markets, auctions, and direct trade; rare
   resources and rare Blueprints hold their value.

The prestige act is **Blueprint discovery and masterwork Forging**: producing a schema so good that
other makers, and other worlds, want to reuse it. *(Engine reading: this is the Hardware Store, in
character. A Blueprint proven in the game and reused elsewhere is the literal engine goal, told as
lore.)*

---

## 19. Quest Architecture

Quests are layered so there is always something at the player's scale:

- **Main story** (the Rekindling): recover the First-Forger craft, uncover why the First Seed broke,
  and decide whether the world should be given that power again. Spans the whole level range and every
  expansion.
- **Regional stories** (per zone): the local face of the great argument (guard/free/govern the craft).
- **Guild and profession quests**: rank-up chains that teach a craft or a combat identity.
- **Exploration quests**: rewards for finding hidden rooms, secret exits, and lost ruins.
- **Hidden quests**: unmarked, triggered by curiosity (reading a book, reforging a broken thing).
- **Dynamic quests and world events**: procedurally seeded tasks and scheduled world-shaking events
  (an Unforging spreads; a Gate opens; a boss wakes) that many players answer together.
- **Player-driven content**: Forgers who reach high rank can *author* quests, rooms, and areas (the
  builder endgame), turning players into content-makers.

*(Engine reading: a quest is a `parts/workflow.py` state machine, exactly the vertical slice already
built (`parts/quest.py`). A dynamic quest is a workflow seeded with world state; player-authored
content is the builder tools writing Seed data.)*

---

## 20. Dungeon Philosophy

Dungeons in Aethryn are **broken places asking to be understood, not just cleared.** Each is a
sundered Forgework, a Warden vault, or a wound in the Cinderdeep, and the design rules are:

- **Every dungeon is a puzzle of the world, not a corridor of health bars.** Layout, mechanics, and
  bosses encode a piece of history or craft; understanding it *is* the reward.
- **Persistent and reactive**: a dungeon remembers what you did (a reforged bridge, a freed Warden)
  across visits.
- **Encounter knowledge matters** (combat philosophy): the second run is easier because you *learned*
  it, not because you out-leveled it.
- **Boss endings are diverse**: not every boss is a kill; some are freed, reforged, out-argued, or
  contained. Victory, defeat, escape, surrender, and scripted endings all apply (combat architecture).
- **Hidden depth**: secret exits, optional wings, and lore rewards for the thorough.

The **Great Spiral** is the megadungeon spine: an endless ascent of Coils and Gate-bosses (the
Wardens), where each Gate is a threshold you must be *proven ready* to pass. The **Cinderdeep** is
the descending frontier.

---

## 21. NPC Philosophy

NPCs make the world feel inhabited, in two honest tiers so the world lives without pretending every
mob is a person:

- **Persistent NPCs** (named, placed, remembered): questgivers, Wardens, shopkeepers, Order masters,
  the Coilwarden and their kin. They persist across restarts, hold state, and can be changed by the
  world (a merchant you saved sells cheaper).
- **Dynamic NPCs** (spawned, roles not names): guards, beasts, salvagers, Unforged. They respawn on
  Ember-tides, fill the world, and drive the economy of danger.
- **The training dummy that reassembles itself** is canon and thematic: it is a small self-Forging
  work, the world's gentle first lesson that things here are *made* and remake themselves.

NPC AI is command-shaped: an NPC in combat issues the same kinds of verbs a player would, choosing on
each tick until the encounter ends. Advanced NPCs (bosses, Wardens) run scripted mechanics.

*(Engine reading: NPCs are `seeds/*/npcs.yaml` data; combat AI is a decision function on the tick;
"AI-friendly" means an NPC's brain is a swappable seam, so a future Claude-backed NPC drops in behind
the same protocol the local AI uses today.)*

---

## 22. Administrative Hierarchy

Aethryn's staff roles are **in-world orders and real permission layers at once**, so operating the
game and living in the world are the same ladder. The rank spine is the engine's
(`player < wizard < owner`), dressed as the **Warden orders**, with operational roles mapped to
in-world offices:

| In-world order | Operational role | Authority |
|---|---|---|
| **Journeyman Forger** | Player | play, make, learn |
| **Hall Builder** | Builder / World Designer | author rooms, areas, Seeds (write world data) |
| **Loremaster** | Storyteller / Content Editor | quests, dialogue, lore, events |
| **Marshal** | Moderator / Game Master | enforce conduct, run live events |
| **Gate-Warden** | Quality Assurance | test worlds and gates before they open (the readiness gate) |
| **Forge-Wright** | Developer | change engine rules (code, not just data) |
| **Keeper of the Deep Anvil** | System Administrator / Security / LiveOps | run the servers, guard the keys, keep the world up |

Two laws hold this together, both inherited from the engine: **authorization before capability**
(rank is checked before any staff verb runs) and **the Warden's oath** (staff power is guarded,
audited, and never used to fake the world's state, the truth discipline). A Gate-Warden signs off a
world the way `make readiness` signs off the code: readiness, never certification.

---

## 23. Expansion Strategy

Aethryn is built to grow for twenty years without rewrites, because every unit of content is a
**Seed** and every system is a **replaceable part**:

- **New continents** ship as new Anvil-regions (Seed packs of areas); the supercontinent map has no
  edge-walls.
- **New Coils** extend the Great Spiral upward (new ascent tiers); **new Cinderdeep layers** extend
  it downward.
- **New races, jobs, professions, guilds** ship as Seeds of data + an Order hall + a questline; none
  require engine changes.
- **New combat systems / mechanics** are new rule-parts behind the same tick seam; the engine can host
  a different combat model without a rewrite.
- **New Seeds and future flagship products** reuse the *same engine* for entirely different genres:
  because lore is separated from rules, tomorrow's Seed can be science fiction and still run on
  Aethryn's engine.

The governing rule is the engine's **Scope-Control**: an expansion earns its place with a Seed, tests,
and lore that fits, or it does not ship. Growth is additive and gated, never a rewrite.

---

## 24. First Starting Area

**The Kindlands Coast, at the town of Cinderhearth-on-Reach.** A small relit river-town where a cold
Forge has just, in the player's first minutes, taken flame again. Design goals: teach the verbs, the
tick, making, and the world's premise, all diegetically.

- **The Waking Shore** (spawn): the player washes in with no memory of Forging; a dying ember on the
  sand relights at their touch. First lesson: *you can make things here.*
- **Cinderhearth Square**: the relit town forge, a shopkeeper, a Loremaster who explains the
  Rekindling, and the self-reassembling training dummy (first combat, safely).
- **The Old Reach Bridge** (broken): the first *reforge* puzzle: gather Ember, craft a plank from a
  crude Blueprint, repair the bridge, and watch the world stay changed. First lesson in persistence.
- **The Reachwood Edge**: gentle wilds with the first dynamic NPCs and gathering nodes.
- **The Cold Cellar** (mini-dungeon door): the tutorial dungeon entrance under the old forge.

By the time a player leaves the Kindlands Coast they have moved, fought a tick-based encounter,
gathered, crafted from a Blueprint, reforged a piece of the world, met a persistent NPC, and heard
the central mystery. *(This area is the canonical `first-forge`-lineage Seed, extended.)*

---

## 25. First Capital City

**Emberreach, City of the Relit Forge**, capital of the Kindlands and the hub of the Age of
Rekindling. A large, safe, service-dense city that teaches the mid-game and hosts the factions:

- **The Grand Forge** (city center): the great relit Forge; the Church of the First Flame; the main
  Loremaster.
- **The Orders' Row**: guild halls of the Making, Gathering, Warcraft, and Knowing Orders (train
  professions and jobs).
- **The Great Archive** (the Chronicle made a place): librarians, research facilities, and the city's
  memory; where Research notes and lore are studied and Blueprints discovered.
- **The Warden Gate**: the Concord's seat and the entrance to the Wardenmarch and the road to the
  Great Spiral.
- **The Market Quarter and Cooling-Sea Docks**: markets, auction house, bank, mail, and ships to
  other regions.
- **Player housing wards**: buy, build, and store; the first player-persistent property.

Emberreach is where a player picks their factions, joins an Order, banks and trades, and chooses
their road: outward on the Anvil, up the Spiral, or down into the Cinderdeep.

---

## 26. First Dungeon

**The Cold Cellar, beneath Cinderhearth's old forge**: the tutorial megadungeon-in-miniature, a
sundered Forgework that the Unforging left half-real. It teaches every dungeon principle at low
stakes:

- **A puzzle of the world**: the cellar is a broken making-hall; its rooms encode the steps of a
  simple Forge, out of order. Understanding the craft *is* how you pass.
- **Persistent and reactive**: reforge the cellar's central hearth and the whole dungeon (and the town
  above) warms and changes, permanently.
- **Encounter knowledge**: the guardian, a **Cinder-Wight** (a half-Unforged old smith), cannot be
  out-leveled at this tier; you win by learning its pattern and using the room's hazards.
- **A diverse boss ending**: the Cinder-Wight can be *killed*, or *reforged* (a harder path that
  frees the smith's spirit and grants a better reward and a lore thread), teaching that in Aethryn,
  making beats breaking.
- **Hidden depth**: a secret exit to an optional wing hints at the Cinderdeep below, and the wider
  world.

It is short, complete, and a true microcosm: every system the game will ever use appears here once.

---

## 27. First Story Arc

**"The Relighting."** The opening arc, spanning the Kindlands Coast and Emberreach:

1. **A spark returns.** The player relights the first ember and is marked as one who can Forge, drawing
   the notice of a Loremaster (Rememberers), a Marshal (Wardens), and a guild recruiter (Free Forges).
2. **Reforge the Reach.** Small acts of making (the bridge, the cellar hearth) prove the craft is real
   and that the world stays changed, and quietly show the three factions' reactions to a new Forger.
3. **The road to Emberreach.** Travel the Ember-road, meet the wider world, choose an Order and first
   factions.
4. **The Warden's test.** At Emberreach's Warden Gate, the player must be *proven ready* to be trusted
   with real Forging, the first gate, mirroring the engine's readiness gate. Pass, and the Spiral, the
   Anvil, and the Deep all open.
5. **The hook.** A fragment of First-Forger craft surfaces, and with it the arc's closing question that
   launches the whole main story: *the craft that broke the world can be relearned. Should it be?*

The arc delivers the premise as *play*, not exposition: the player has already reforged the world in
small ways and already felt the weight of being trusted with making.

---

## 28. First 100 Core Commands

The starting verb set, by family (all CORE unless marked). This is the command philosophy made
concrete; each verb is one clear responsibility with validated targets.

- **Movement (1-12):** `north` `south` `east` `west` `up` `down` (+ `n s e w u d`), `go <dir>`,
  `enter <portal>`, `climb`, `descend`, `recall`, `travel <dest>`.
- **Exploration (13-20):** `look`, `look <target>`, `examine <target>`, `search`, `read <text>`,
  `map`, `where`, `scan`.
- **Communication (21-28):** `say`, `tell <player> <msg>`, `whisper`, `yell`, `emote`, `ooc`,
  `reply`, `channel <name> <msg>`.
- **Social (29-34):** `who`, `finger <player>`, `follow <target>`, `group`, `wave`, `bow`.
- **Inventory + equipment (35-46):** `inventory` (`i`), `get <item>`, `drop <item>`, `give <item> to
  <player>`, `wear <item>`, `wield <item>`, `remove <item>`, `equip`, `unequip`, `swap <a> <b>`,
  `use <item>`, `compare <a> <b>`.
- **Combat (47-64):** `attack <target>`, `strike`, `slash`, `cast <spell> <target>`, `guard`,
  `parry`, `counter`, `taunt <target>`, `focus`, `target <target>`, `assist <ally>`, `rescue <ally>`,
  `retreat`, `flee`, `surrender`, `reload`, `bandage <target>`, `drink <potion>`.
- **Character + progression (65-74):** `score`, `stats`, `skills`, `cooldowns`, `affects`, `rest`,
  `train <skill>`, `learn <ability>`, `titles`, `achievements`.
- **Trading + economy (75-82):** `buy <item>`, `sell <item>`, `list`, `trade <player>`, `bank`,
  `deposit <amount>`, `withdraw <amount>`, `auction <item> <price>`.
- **Crafting + gathering (83-90):** `gather`, `mine`, `forage`, `salvage`, `craft <blueprint>`,
  `research <ingredients>`, `blueprints`, `recipes`.
- **Party + guild (91-94):** `party`, `raid`, `guild`, `guildhall`.
- **Help + accessibility + QoL (95-100):** `help <topic>`, `commands`, `alias <name> <cmd>`,
  `history`, `config <option> <value>`, `quit`.

*(Staff verbs live in the `@`-namespace and are not in the core 100: `@teleport`, `@grant`, `@build`,
`@forge`, `@dig`, `@load`, `@restore`, `@shutdown`, rank-gated to the Warden orders. Builder tools are
`@`-verbs that write Seed data, never engine code.)*

---

## 29. Future Expansion Hooks

Seams left open on purpose, each a future Seed or product:

- **The unreached Coils** of the Great Spiral: endless vertical endgame tiers, one raid per Gate.
- **The Cinderdeep continent**: a whole descending underworld, its own factions (the Unforged) and
  economy (salvage).
- **The other continents** of the Anvil: the map extends outward forever; each is an expansion.
- **The First-Forger craft**: high Forging as a prestige system, the literal power to author world
  data in-game (the builder endgame).
- **The Emberwright return**: the great mystery, resolvable as a world-event that reshapes the map.
- **New genres on the same engine**: because lore is separated from rules, a future flagship Seed can
  be science fiction, horror, or historical and still run on Aethryn's engine, the ultimate proof of
  the two-output platform.
- **AI-inhabited NPCs**: the NPC brain is a seam; a future Seed can drop a Claude-backed Warden or
  Loremaster behind the same protocol the local AI uses today.
- **Player-Forged worlds**: the endgame of the endgame, players who reach the top of the craft Forge
  their own Seeds, and the best of them become official worlds. The world that makes worlds.

---

## The through-line

Aethryn is the argument that CodeForge's two philosophies are one. *Creation is more powerful than
destruction* is a world law and a design law. *Knowledge changes reality* is a plot and a build
process. *Everything has been Forged, and everything can be reforged and reused* is the world's
metaphysics and the Hardware Store's promise. Players begin as ordinary adventurers and become
Forgers who reshape the world, which is exactly what a CodeForge builder does to the engine. The
flagship world proves the flagship engine, because they were designed as the same idea, told twice.

*This bible is design, not engine. It is realized as data in `seeds/*.yaml`; the engine that runs it
stays genre-neutral and reusable. See `docs/vision_resync.md` (the platform), `parts/quest.py` and
`parts/workflow.py` (quests as the reference vertical slice), and `chronicle/README.md` (the world's
memory made literal).*
