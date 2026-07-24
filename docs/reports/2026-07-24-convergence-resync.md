# Convergence Resync - 2026-07-24 (the AAA pivot)

**Trigger.** Josh raised the bar from "a tested vertical slice that proves the engine" to a
shipped, AAA-scale RPG: a runnable client executable ("if the client is not a .exe the network is
not complete"), Cyberpunk/Witcher-III levels of side content, ~30 jobs a player can modulate and
swap in and out, and deep items/weapons. This document reconciles that bar with the measured state
and records the strategic pivot it implies. It is a **keel record** (human_keel_doctrine): the
mission direction changed, by Josh's decision.

## 1. Measured state (2026-07-24, flagship = aethryn unless noted)

- **Client:** source-only Python package (`codeforge-mudclient`); a user needs Python 3.13 + a
  `pip install`. No PyInstaller/Nuitka/Briefcase, no build/release workflow, no binary. It is a TUI.
- **Jobs:** ~7 labels fleet-wide (3-4 per seed), mostly stat-block stubs; only first-forge's
  `engineer` is fully loaded. Primary-switch works and persists **per job** (FFXI-correct). Gaps:
  subjob lends **no** kit (combat reads the primary only, `abilities.py:54,77`); `resistances` are
  loaded but **never** applied in combat; `counter/movement/inherent/signature` are display-only.
- **Items:** 22 total, 9 equippable across 6 fixed slots, flat stat mods (real + tested). No rarity,
  no crafting, no consumables (no use-item verb), no loot tables; 1 shop in the whole game.
- **Side content:** 4 authored quests (all linear FSM arcs, no branching/choices/failure), 50
  dialogue lines (a modulo cycle - no trees), 45 hand rooms + ~46 procedural Spiral rooms, 32 NPCs.
- **Volume vs AAA:** roughly 1/100 - 1/1000 of Witcher-III side-content hours. Expected: the repo's
  thesis was *tested reusable parts*, not shipped game hours.

## 2. Design vs reality (the docs already promised this)

- `docs/job_system.md` (1463 lines) designs **20 jobs across 6 families**, each with 10 actives / 5
  passives / 5 reactions / 3 movements / a signature / a custom resource. Shipped: ~7 stubs.
- `docs/world_bible.md` (692 lines) designs a 20-year MMO - regions, cultures, factions, a full
  materials/making **economy**, gathering/crafting/knowledge **professions**, a layered quest web,
  dungeons, housing. Shipped: a tutorial-scale slice.
- The docs are honestly labelled "design, not shipped." The gap is real, not a false claim.

## 3. The blocking contradiction (what "resync" resolves)

The fleet `DEVELOPMENT_PLAN.md` marks codeforge **feature-frozen for the portfolio**, with
"distribution is the binding constraint" meaning **Josh's resume / applications**, not shipping a
game to players. Josh's direction **overrides that freeze**: build the designed game to AAA scale
and ship a runnable client to players. This is a keel-level mission change; recorded here as such.

Crucially, the pivot is **aligned with the ship's own Convergence Review** (2026-07-17,
`docs/reports/2026-07-17-convergence-review-repeat.md`): its systemic verdict was *"capable core,
orphaned last inch - no seat owns 'does the game actually play?', and the missing discipline is
game-design / balance economics."* Building the game to a real, playable, shippable scale is the
direct answer to that finding, not a departure from it.

## 4. The lever: engine systems + a content factory

AAA **content volume** cannot be hand-authored in a sprint (Witcher III is hundreds of quests /
thousands of items). Two honest tracks close the gap:

- **Track A - the missing engine systems** (bounded, buildable as slices, like every system shipped
  this session): subjob ability-lending, resistances-in-combat and the reaction/movement slots,
  crafting/recipes, consumables + a use-item verb, item rarity/tiers/affixes + loot tables,
  branching dialogue trees, non-linear/branching quests + faction consequences.
- **Track B - content at scale via generation** (the lever proven by `parts/world/spiral.py`,
  which built 25 Coils to L255 from a config): procedural/authored **content factories** - a job
  factory that realizes the 20-job design and beyond, an item factory (rarity + affixes + loot
  tables), a quest/encounter generator, more hand-authored zones and dialogue where hand-craft
  matters. Generation reaches volume; authored data supplies the set-pieces.

- **Track C - distribution**: a PyInstaller `--onefile` build of the client (a `mudclient.spec`
  forcing the lazy `telnetlib3`/`textual` imports), a `make dist` target, and a tagged cross-OS
  release workflow. A shipped client points at a hosted server via `--config`, not the dev
  `play.sh` sibling-spawn. Small-to-medium; unblocks "a player can run it."

## 5. Staged plan (ordered; each stage is branch -> check -> PR -> CI -> merge)

1. **Ship the client as a runnable executable** (Track C) - Josh's stated first gate.
2. **Jobs to real switchability** (Track A): wire subjob ability-lending + resistances-in-combat,
   then (Track B) a job factory realizing the `job_system.md` families toward 30, with movesets.
3. **Item depth** (Track A/B): rarity + affixes + loot tables, consumables + use-item, crafting.
4. **Side content depth** (Track A/B): branching dialogue trees, branching quests + faction
   consequences, a quest/encounter generator, more zones and a real economy (more shops/professions).

## 6. Honesty guardrails (unchanged)

No overclaiming: "designed" is not "shipped"; a generated Coil is filler-by-formula, not a
hand-crafted set-piece; balance is prototype until a game is actually played and tuned. The
Convergence Review's missing discipline - **game-design/balance economics** - is now on the plan,
not just the audit. AI proposes, the tests verify, Josh decides and keeps the keel.
