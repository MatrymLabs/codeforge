# CodeForge Vision Resync

*One coherent product vision for the whole repository. Written 2026-07-11 (commit `6cf3362`).
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
Deploy, Monitor, Improve). What is missing is the **connective tissue**: one path that runs the
loop end to end for a single part. Building that proof is the current priority, not a bigger
world generator.

## Capability status (honest labels)

- **Working:** engine tick; seed loader/validation; TCP + WebSocket gateways; salted-pbkdf2
  accounts; SQL persistence (SQLite/Postgres + Alembic); rooms/items/NPCs/doors/combat/jobs/
  progression/equipment; command spine + rank gating; event bus; classification registry;
  Blueprint model (typed); Hardware Store catalog (typed `Part`); classroom/assessment; the
  in-MUD workshop/terminal/console; the assurance + evidence stack; Docker + CI + a live demo.
  the full suite with branch coverage (the CI badge is the live count).
- **Prototype:** `cast` (plans a package as a dry-run, writes nothing); `foundry` (generate into
  a guarded sandbox, manual promotion); `evolution` lab; `hubble` diagnostic core; `stewardship`
  gates; `blueprint_ai` (Claude-drafted).
- **Planned:** typed WorldManifest family; a quest/workflow engine as a product; configurable
  statistics and rulesets; creator wizards; package export/detachment; practical adapters
  (one core, many adapters); the full Part Manifest; a demonstrated game<->practical translation.
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

1. **No connected manufacturing spine** - the vision's heart is unexecuted.
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
  through a non-game interface.
- One core, two adapters: the two-way translation thesis, demonstrated.

## Priority staircase (build order)

0. **Vision + repo alignment** (this doc). Done.
1. Manufacturing core: Blueprint `product_type`, Part Manifest, assembly evidence.
2. **First reusable vertical slice** (the Workflow Engine, above). Next.
3. Minimal World Package: one region + identity + commands + the quest system + admin + tests.
4. Package export: prove a package assembles, installs, and runs independently.
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
