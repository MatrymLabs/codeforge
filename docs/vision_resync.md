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

The layer boundary is **conceptual today, not physical**: the engine is one coupled package
(`cast` reports `engine_strategy: "vendored-whole"`, honestly), so a generated world would still
carry the whole platform. Making Layer-2 modules optional is a major effort, deliberately deferred.

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
  `blueprint` verb); the connected manufacturing spine (`forge_line`, both directions).
- **Prototype:** `evolution` lab (the pipeline is tested end-to-end with a tick verb, but its
  runnable demo script needs a fix before it earns "working"); `hubble` diagnostic core (built +
  tested, not yet wired to a caller); `stewardship` gates (built + tested, currently dormant).
- **Planned:** typed WorldManifest family; configurable statistics and rulesets; creator wizards;
  the full Part Manifest; more practical adapters beyond the shipped one. (The Workflow Engine as a
  product, its game/practical adapters, a demonstrated game<->practical translation, and package
  export/detachment are ALREADY BUILT - see staircase steps 2 and 4 below, not planned.)
- **Deferred (relative to the spine):** repository split, plugin system, configurable-rules
  language, package-update model. Sound to want; not now.

## Scope discipline (what conflicts, honestly)

Nothing *conflicts*, but the repo carries **peripheral subsystems** that distract from a tight
manufacturing spine: three research/assurance layers (`evolution/`, `hubble/`, `stewardship/`)
atop the existing `veritas`/`frameup`/`qualitygate`/`integrity` assurance layer, plus federal
compliance awareness (`law`/`regulations`/`library`) and portfolio meta (`career`, `pioneer`).
Each is individually sound. They are classified **deferred relative to the vertical slice**, not
removed: the rule is "don't preserve merely because it exists," and equally "don't rewrite first."

## Highest architectural risks

1. ~~**No connected manufacturing spine** - the vision's heart is unexecuted.~~ **CLOSED:**
   `parts/forge_line.py` runs the loop end to end for one built part (read-and-verify). The deeper
   risk that remains is generating a *brand-new* part through the full loop, not the spine's absence.
2. **Monolithic engine** ("vendored-whole") - blocks Layer-2 modularity and package export.
3. **World is content-driven, not manifest/config-driven** - the "configuration-driven"
   requirement is unmet; rules and attributes are semi-hardcoded (`derived.py`: "PROTOTYPE
   BALANCE"; `progression.py`: "locked design").
4. **Game<->practical translation is unproven** - the defining thesis has zero working demos.
5. **Subsystem sprawl** dilutes focus.

## The first vertical slice: the Workflow Engine

The proof that makes the whole vision legible without finishing the platform:

> **One reusable workflow engine powers a regional quest inside the MUD and an
> employee-onboarding workflow through a practical interface. Both are assembled from a
> Blueprint, tested through the same pipeline, cataloged in the Hardware Store, and shown on
> GitHub.**

- **Reusable core:** a config-driven `WorkflowEngine` (states, guarded transitions, roles) built
  on the existing, already-tested pure FSM (`parts/statemachine.py`). Because the core exists,
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
   core (`parts/workflow`), the game `quest` adapter (MUD), and the practical `onboarding` adapter
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
