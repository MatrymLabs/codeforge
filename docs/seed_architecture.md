# Seed Architecture - the seed pack and the cast

*CodeForge is the forge. A **cast** is what leaves the forge.*

## Two layers, one idea - preserve both contracts

CodeForge has a historical **seed pack** contract and a newer platform **Seed** contract.
Keep the persisted pack identifiers compatible while the platform lifecycle is unified around
them:

| Term | What it is | Status |
|------|-----------|--------|
| **seed pack** | A game's **content** - `seeds/<name>/{rooms,items,npcs,jobs}.yaml` + `splash.txt`, loaded by the shared engine. `codeforge seeds` lists them; `--seed <name>` / `FORGE_SEED` selects one. | **Exists. Frozen** - the dir name, YAML keys, `--seed`/`FORGE_SEED`, and save-file references are persisted identifiers and never renamed. |
| **Seed** | The persistent MUD-based engineering environment that owns a Seed pack, project state, services, permissions, and lifecycle. | **Platform contract** - SeedLab currently prototypes the identity/lifecycle; the runtime bridge is incremental. |
| **cast** | A **standalone, installable project** poured from the forge: the engine + one chosen seed pack + config, detached into its own repo. "What leaves the forge." | **Net-new.** This document + `kernel/cast.py` are the Phase-1 scaffold. |

A seed pack is *content the Engine loads*. A Seed is *the persistent environment that operates
that content and creates Target Products*. A cast is *a project you can clone and run on
its own*. The generator **reads** a seed pack and **writes** a new cast elsewhere - it never
touches `seeds/`, `--seed`, or `FORGE_SEED`.

Product startup resolves Seeds in this order: explicit request, active project, persisted user
selection, `FORGE_SEED`, then bundled Aethryn. An unavailable configured Seed fails loudly rather
than silently changing the user's selection.

## The honest state of "modular"

The vision is a cast where you select modules (`combat=true, library=false`). **The engine
cannot do that yet.** `parts/` is a single, tightly-coupled package - you cannot drop
`combat` without breaking imports. So:

- **Phase 1 (now):** a cast vendors the **whole engine** + **one seed pack** + config. The
  manifest says `engine_strategy: "vendored-whole"` - never a false à-la-carte module list.
  *No claim without correspondence.*
- **Phase 2:** decouple `parts/` into importable subsystems with declared dependencies -
  the real prerequisite for meaningful module selection. Large; deferred by design.
- **Phase 3:** package the engine; casts depend on `codeforge-engine==<version>`.
- **Phase 4:** hybrid - a cast starts on the package and vendors on detach.

A seam already exists: `CODEFORGE_SEEDS_ROOT` and `CODEFORGE_DB` let an installed engine
point at an external world + data dir. That is the Phase-2/3 foundation, already built.

## The lifecycle

```
design template → plan cast (dry run) → generate → init registry/docs/tests
→ migration audit → detach validate → detach → standalone boot → package/publish
```

Phase 1 implements only the first step in software: **plan** (`kernel/cast.py`) - a dry run
that lists what it *would* copy and the manifest it *would* write, and **writes nothing**.

## What a cast copies - and never copies

**Copies:** the engine (`parts/` + `forge.py`), the chosen seed pack, and a fresh scaffold
(`pyproject.toml`, `README.md`, `seed.toml`, `cast_manifest.json`, `.gitignore`, `LICENSE`).

**Never copies** (grounded in `.gitignore` + the safety rules): `codeforge.db`, `save.json`,
`characters.json`, `accounts.json`, `*.kdbx`, `.env`, `.venv/`, `reports/`,
`security-evidence/`, `__pycache__/`, `coverage.xml`, the *other* seed packs, the flagship
branding (`README`/`CHANGELOG`/`CAPTAINS_LOG`/`DEVELOPMENT_PLAN`), and CodeForge-only dev
tooling. A cast should look like its own generated project, not a copy of the forge.

## Detachment (later phases)

A cast becomes its own project only after a green **detach validator**: no absolute
CodeForge paths, no dev-only imports, no secrets, tests pass, **standalone boot works**,
origin metadata preserved, README rewritten for the cast. Git init **only after green**.
Status machine: `not_detached → detach_ready → detached | blocked | human_review_required`.
Even detached, a cast **remembers its origin** (`generated_by`, `codeforge_commit`,
`template`, `generated_at`) in its manifest.

## Templates

A **seed template** is a blueprint for a kind of cast (`seed_templates/<id>/template_manifest.json`):
it names the starter seed pack, the engine strategy, default settings, and what to include.
Shipped: `blank_mud` (the minimal world that boots) and `fantasy_mud` (a themed world).

## Truthful status labels

`prototype · experimental · generated · detached · validated · not_validated · planned`.
A cast is never called "production-ready," and multiplayer/MMORPG scale is never claimed
unless tested.
