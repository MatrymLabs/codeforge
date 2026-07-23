# CodeForge Vision Resync

*THE canonical product vision for the whole repository: the single source of truth for what
CodeForge is. Where any other doc (v3_vision_review, the maturity scorecard, proving_ground/VISION)
differs on what the product IS, this governs; those are reviews or sub-visions, not competing canon.
Written 2026-07-11 (commit `6cf3362`).
Every capability is labelled honestly per the Vision Truth Rule: **working · prototype ·
planned · experimental · deferred**. Nothing planned is described as working.*

## The thesis in one line

**CodeForge is a software manufacturing platform with two outputs: an installable multiplayer
World Package, and a Software Hardware Store of reusable parts proven in the game and translated
to real software.** The engine and its first world run today; the manufacturing *spine* that
connects the stations is being assembled one vertical slice at a time.

## The three layers

| Layer | What it is | Examples (today) |
|---|---|---|
| **1. Manufacturing platform** | The flagship: dev tools + control that turn ideas into products | `blueprint`, `registry`, `cast`, `foundry`, `veritas`, `frameup`, `pm`, `reporting`, `dashboard`, `cli` |
| **2. World Package** (runtime) | The generated/assembled deployable world | `accounts`, `world`, `rooms`/`items`/`npcs`, `commands`, `combat`, `jobs`, `progression`, `gateway`(TCP), `web_gateway`(WS), `classroom`, `assessment` |
| **3. Hardware Store** | Reusable parts usable by the platform, packages, and outside apps | `statemachine`, `resources`, `reporting`, `config`, `registry`; catalog in `hardware`/`store` |

The layer boundary was conceptual for most of the repo's life; **Layer 3 is now physical**. Every
reusable, engine-agnostic core -- 27 across six families (resilience, FSM, data, wire, input
hardening, observability, config, infra) -- lives in its own package, `parts/shelf/`, with the
dependency arrow pointing one way: engine -> shelf, never the reverse. The remaining cataloged parts
import engine modules (`session`, `verdicts`, `hardware`, ...), so they are correctly Layer 1/2, not
relocatable Layer-3 cores. Full Layer-2 optionality (a world carrying only what it runs) is already
proven functionally by `cast`'s vendored-selective pour; a further physical split of the
platform/world engine itself is a separate, larger question, not required by the two-outputs thesis.

## The manufacturing loop (the heart of CodeForge)

```
Idea -> Intake -> Requirements -> Search Existing Parts -> Blueprint -> Select Modules
-> Configure -> Assemble -> Generate/Implement -> Test -> Simulate -> Diagnose -> Repair
-> Document -> Catalog -> Package -> Deploy -> Monitor -> Improve
```

**Most stations already exist** (Blueprint, Search, Test, Diagnose, Catalog, Package-plan,
Deploy, Monitor, Improve). The **connective tissue** now exists too: `parts/forge_line.py` (the
`line` runner) runs the loop end to end for a single built part, station by station, and reports a
verdict at each stop (read-and-verify only; the ASSEMBLE stop is a dry-run). Generating a *brand-new*
part through the full loop is the deeper next slice; the spine itself is executed.

## Capability status (honest labels)

- **Working:** engine tick; seed loader/validation; TCP + WebSocket gateways; salted-pbkdf2
  accounts; SQL persistence (SQLite/Postgres + Alembic); rooms/items/NPCs/doors/combat/jobs/
  progression/equipment; command spine + rank gating; event bus; classification registry;
  Blueprint model (typed); Hardware Store catalog (typed `Part`); classroom/assessment; the
  in-MUD workshop/terminal/console; the assurance + evidence stack; Docker + CI + a live demo.
  the full suite with branch coverage (the CI badge is the live count).
  `cast` (generates + boots + validates + selectively vendors a standalone game; `make forge`
  live-proven, green test twin; the one unproven-in-CI edge is fresh-venv dependency isolation);
  `foundry` (propose -> approve -> generate into the git-ignored `workspace/` sandbox; the
  `@forge`/`@arch` owner verbs + `forge_line.forge_new` are real callers, tested);
  `blueprint_ai` (Claude-drafted Blueprints on a mockable, offline-tested seam behind the
  `blueprint` verb); `evolution` lab (evaluator-guided SELECTION over candidate blueprints -- hard
  gates then weighted objectives, human_decision_required, nothing auto-promoted; the `evolution`
  tick verb + a runnable `make evolution` demo; NOT autonomous search); the connected manufacturing
  spine (`forge_line`, both directions).
- **Prototype:** `hubble` diagnostic core (built + tested, not yet wired to a caller);
  `stewardship` gates (built + tested, currently dormant).
- **Planned:** typed WorldManifest family; configurable statistics and rulesets; creator wizards;
  the full Part Manifest; more practical adapters beyond the shipped one. (The Workflow Engine as a
  product, its game/practical adapters, a demonstrated game<->practical translation, and package
  export/detachment are ALREADY BUILT - see staircase steps 2 and 4 below, not planned.)
- **Done (this campaign):** the physical Hardware Store extraction -- all 27 engine-agnostic
  reusable cores now live in `parts/shelf/` (six families, six merged stages), each behind a green
  gate, one-way engine -> shelf dependency. Layer 3 is physical.
- **Deferred (relative to the spine):** a physical Layer-1/2 engine split (functional optionality is
  already proven via vendored-selective), plugin system, configurable-rules language, package-update
  model. Sound to want; not now.

## Scope discipline (what conflicts, honestly)

Nothing *conflicts*, but the repo carries **peripheral subsystems** that distract from a tight
manufacturing spine: three research/assurance layers (`evolution/`, `hubble/`, `stewardship/`)
atop the existing `veritas`/`frameup`/`qualitygate`/`integrity` assurance layer, plus federal
compliance awareness (`law`/`regulations`/`library`) and portfolio meta (`career`, `pioneer`).
Each is individually sound. They are classified **deferred relative to the vertical slice**, not
removed: the rule is "don't preserve merely because it exists," and equally "don't rewrite first."

## Highest architectural risks

1. ~~**No connected manufacturing spine** - the vision's heart is unexecuted.~~ **CLOSED:**
   `parts/forge_line.py` runs the loop end to end in both directions -- `run_line` inspects a built
   part station by station, and `forge_new` generates a brand-new part's scaffold through the loop
   into the git-ignored sandbox. The heart executes.
2. **Monolithic engine** ("vendored-whole") - **the Hardware Store is now physically separated:**
   `cast`/`forge` pour a *vendored-selective* package (proven), AND every engine-agnostic reusable
   core is physically extracted into `parts/shelf/` (27 cores, six families, one-way dependency).
   What remains one package is the platform/world engine itself (Layer 1/2), which vendored-selective
   already makes optional functionally; a physical Layer-1/2 split is deferred as a separate question.
3. ~~**World is content-driven, not manifest/config-driven**~~ **MOSTLY ADDRESSED:** a typed
   `WorldManifest` gives a seed a declared identity, and a typed stat `Ruleset` makes the derived
   combat balance configurable -- a world's `world.yaml` `rules:` block now reaches live combat
   (`parts/derived` applies the booted world's ruleset); a `progression:` block makes the XP/JP
   level curves configurable; and a `gains:` block makes the per-level HP/MP growth configurable
   (both via `parts/progression`, applying the booted world's tracks + gains). A world now declares
   its identity, combat balance, level curves, and growth as validated data. The only balance still
   hardcoded is the equipment/status modifier stack -- a separate system, not a config gap.
4. ~~**Game<->practical translation is unproven**~~ **PROVEN:** the Workflow Engine (below) powers a
   MUD quest AND a CLI onboarding workflow from one core, and every Hardware Store part carries a
   game adapter + a practical adapter, each tested. The defining thesis has working demos.
5. **Subsystem sprawl** dilutes focus (a design observation, not a defect -- each peripheral
   subsystem is individually sound and deferred relative to the spine, per the scope note above).

## The first vertical slice: the Workflow Engine

The proof that makes the whole vision legible without finishing the platform:

> **One reusable workflow engine powers a regional quest inside the MUD and an
> employee-onboarding workflow through a practical interface. Both are assembled from a
> Blueprint, tested through the same pipeline, cataloged in the Hardware Store, and shown on
> GitHub.**

- **Reusable core:** a config-driven `WorkflowEngine` (states, guarded transitions, roles) built
  on the existing, already-tested pure FSM (`parts/shelf/statemachine.py`). Because the core exists,
  the slice is genuinely finishable.
- **Game adapter:** a **Quest** (regional quest progression) via MUD commands. This also fills a
  real gap: the World Package has **no quests today**.
- **Practical adapter:** an **onboarding / approval checklist** driven by the *same* engine
  through a non-game interface - now shipped as the **`codeforge onboard`** CLI (`parts/onboarding`),
  the practical cousin of the MUD `quest` verb.
- One core, two adapters, two interfaces (MUD + CLI): the two-way translation thesis, demonstrated
  and runnable end to end.

## Priority staircase (build order)

0. **Vision + repo alignment** (this doc). Done.
1. Manufacturing core: Blueprint `product_type`, Part Manifest, assembly evidence. Done.
2. **First reusable vertical slice** (the Workflow Engine, above). **Done** - one `WorkflowEngine`
   core (`parts/shelf/workflow`), the game `quest` adapter (MUD), and the practical `onboarding` adapter
   now runnable through the **`codeforge onboard`** CLI; cataloged in the Hardware Store
   (`docs/hardware/workflow_engine.*`), `loop trace workflow-engine` = PASS.
3. **Minimal World Package: one region + identity + commands + the quest system + admin + tests. Next.**
4. Package export. **In progress:** `make cast` POURS a standalone project (engine vendored whole
   + seed pack + scaffold + a manifest that declares the engine's real deps), VALIDATES it
   (`validate_cast` smoke-boots + one tick -> `validated`), and `make cast-install-check`
   (`install_check`) proves DEPENDENCY ISOLATION - a clean venv, only the cast's declared deps,
   and it boots (`isolation_proven`). And detachment is under way: `make coupling` (D1) maps the
   runtime module closure, and `make cast-selective` (D2, `pour_selective`) vendors ONLY the target
   surfaces' closure (`vendored-selective`) and PROVES the cut with a broad harness - every surface
   command must run. Verified live across surface tiers: **solo+save** carries 70 of 128 modules
   (16 commands clean); **+admin** (the owner @-verb tier) carries 74 (21 commands clean, incl. the
   @-verbs) and has an end-to-end regression test (`test_pour_selective_validates_an_admin_cast`);
   **+multiplayer** carries 78 and its `parts/web/` data dir (the import-based server tier: gateway +
   web_gateway import in the cut) and now also has an end-to-end regression test
   (`test_pour_selective_validates_a_multiplayer_cast`, via an injected `import_tracer` seam). So a
   package *assembles*, *runs*, *runs in isolation*, and is *selectively detached with an end-to-end
   proof for every one of the four surface tiers*. The remaining keel call is D3: true
   plugin-boundary decoupling.
5+. Creator wizards, full-stack interface, Hardware Store expansion, advanced modularity,
   production operations. Each gated by the Scope-Control Rule.

## Decisions that need Josh (approval gates)

Renaming the public product; repository strategy/split; permanent web framework or protocol;
package-update model; the plugin system; persistence architecture; the configurable-rules
language; the Seed/World-Package definition; the flagship positioning. Continue independently for
inspection, mapping, schemas, interfaces, fixtures, documentation, nonbreaking tests, and
prototype adapters.

## Final doctrine

CodeForge is the machine. The World Package is one product. The Hardware Store supplies the
parts. The Blueprint defines what to build. The game proves the parts can live; the practical
adapter proves they can work; the tests prove they can be trusted; the exported package proves
CodeForge can manufacture something independent. Build the spine. Prove one part. Assemble one
small world. Export one package. Then expand the forge.
