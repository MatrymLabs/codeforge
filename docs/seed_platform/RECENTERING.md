# Seed Platform Recentering — the Seed as an engineering environment

Founder directive (`/home/josh/Projects/prompt`, 2026-08-01): **THE SEED IS THE MUD.** A Seed is
not just a game-data pack; it is a persistent, MUD-based *software-engineering environment* — a
workshop that connects a project source, models it, builds it, tests it, and generates a target,
then extracts reusable Hardware. This document is the honest baseline and the compatibility-safe
plan. Josh chose **full recenter (careful)**: proceed on the autonomous track, hard-gate the
destructive Seed-model rewrite on explicit approval.

## Corrected definitions

- **Seed** — a persistent MUD-based engineering environment created and operated by CodeForge
  through the Master Client. **Every Seed is a MUD; not every target it produces is a MUD.** The
  game world (Aethryn) is one *kind* of Seed / the proving-ground substrate, not the whole meaning.
- **CodeForge** — the platform that creates, deploys, and operates Seeds (today: proven as a game
  engine + self-auditing engineering stack; the general engineering runtime is being built).
- **Master Client** — creates and enters Seeds; renders engineering panels (today: a game client).
- **Hardware Store** — the catalog of reusable parts proven inside Seeds.

## Capability map — honestly labeled (No Vision Theater)

Labels: VISION · RESEARCH · SPECIFIED · PROTOTYPED · INTEGRATED · PROVEN · DEPLOYABLE · PRODUCTION_READY.

| Capability | Status | Evidence / note |
|---|---|---|
| MUD runtime + persistent world | **PROVEN** | the game engine (aethryn), end-to-end playable + gated |
| Seed = game-data pack | **PROVEN** | `parts/world/seed.py` ("a seed IS a game") — the definition being *widened*, not deleted |
| Target generation (games only) | **PROVEN** | `cast`/`forge` pours a standalone game from a seed + engine |
| **Real game-Seed deployment (Aethryn poured + booted at scale)** | **DEPLOYABLE** | `make deploy-proof` (`scripts/deploy_aethryn_seed.py`) pours the whole engine + the Aethryn world, boots the cast in a fresh subprocess, serves a play corpus, and records the world's room count — the honest proof the game Seed's deployment is real, not a stub. Public deploy is a separate, gated step. |
| Repo analysis / gate-running on a target | **PROTOTYPED** | `forge-audit` (separate repo, mock GitHub seam) |
| In-MUD building (game content, owner-only) | **PROTOTYPED** | `workshop`/`foundry` |
| **Project source → structured model** | **PROTOTYPED** | `parts/seedlab/project_model.py` |
| **Seed identity + lifecycle (as an addressable entity)** | **PROTOTYPED** | `parts/seedlab/kernel.py` (MOD-10.052) — create/start/stop/archive a Seed with owner authz, an audit trail, and file-backed persistence that survives restart; distinct from the `FORGE_SEED` game pack |
| **Functional Project Hub (enter + inspect a Seed)** | **PROTOTYPED** | `parts/seedlab/project_hub.py` (MOD-10.053) — a Seed location that renders identity/status/facets as a text `look` + its sub-verbs AND a versioned structured client contract, both from one source of truth; empty facets read "none yet (Stage N)" |
| **Local source connector (read-only, path-bounded)** | **PROTOTYPED** | `parts/seedlab/source_connector.py` (MOD-10.054) — register a local dir with provenance; list/search/read only approved files; refuses traversal, absolute paths, symlink escapes, and a secret denylist; feeds the Hub's `sources` facet |
| **Source → project model (persisted, honest)** | **PROTOTYPED** | `parts/seedlab/source_modeler.py` (MOD-10.055) + `model_store.py` (MOD-10.056) — extract a `ProjectModel` from a registered source (identity/entities/interfaces/provenance derived; everything else marked in `unknowns`), persist it (survives restart), and light up the Hub's `models` facet linked to source evidence |
| **Controlled build/test execution** | **PROTOTYPED** | `parts/seedlab/tool_runner.py` (MOD-10.057) — run an allowlisted, shell-free command inside an approved source with cwd boundary + timeout + output cap + secret redaction; refuse an unlisted profile; persist each run (`FileRunLog`, survives restart) into the Hub's `builds`/`tests` facets |
| **First generated target (a runnable CLI)** | **PROTOTYPED** | `parts/seedlab/cli_generator.py` (MOD-10.058) — generate a small, runnable Python CLI from a validated model (reproducible, sha256-checksummed, provenance-carrying); `validate_runs`/`validate_tests` prove it RUNS and its generated tests PASS via the Stage-5 runner. **Closes the First Platform Proof: source → model → generate → run → tests pass → artifact.** |
| Repo / IDE / API / DB connectors (remote) | **VISION** | remote repo/IDE/DB connectors not built; local FS connector is the first real one |
| Multi-AI-provider connector | **VISION** | internal AI helpers exist, not a provider connector |
| Reverse-engineering / walkthrough-to-world | **VISION** | — |
| Build/test/deploy of *generated user targets* | **VISION** | — |

**Honest one-liner:** the engineering-environment Seed is ~90% VISION. The recenter is a
multi-stream, multi-month build; this doc + the first slice are the ground floor, not the house.

## First slice (PROTOTYPED, shipped isolated)

`parts/seedlab/project_model.py` (MOD-10.051) proves the directive's step 9 — *the Seed consumes
real project input and extracts a model*:

- `ProjectSource` protocol (the connector seam; tests inject a fake, nothing touches the network).
- `Provenance` recorded for every source (the directive's legal/IP boundary; a gap reads `unknown`).
- `ProjectModel` — identity, entities, relationships, states, actions, inputs, outputs — with
  `extract_model` (fail-loud validation) and `render_model` (inspectable; the seam a future MUD
  `model` verb and a client panel both render).

It is **isolated in `parts/seedlab/`, not `parts/world/`** — the game Seed model is untouched.

## Compatibility & gates

- **The game Seed model is not rewritten.** The engineering Seed is built *alongside* it; the
  destructive Seed-model rewrite and any Seed-compatibility break are **gated on Josh's approval**
  (per the directive's own approval gates).
- Every new part carries its test twin + registry filing; `make check` (real exit) gates each batch.

## Slice 2 (DEPLOYABLE, shipped): the game Seed's deployment is real

Founder correction (Josh, 2026-08-01): *"the game deployment of the seed is real … the game shows
the scale I want the seed capable of creating."* Before generalizing sideways to a toy non-game
target, prove the platform can really **deploy the thing it already builds, at the game's scale.**

`make deploy-proof` (`scripts/deploy_aethryn_seed.py`) does exactly that with the real cast
machinery (no stub): plan the flagship `kindlands_saga` template → `generate_cast` pours the whole
engine + the Aethryn world → `validate_cast` boots the poured cast in a fresh subprocess and runs a
play corpus (`look`, `score`, `inventory`, `help`) → a second subprocess boot records the world's
room count. It files dated evidence to `reports/deploy/` (gitignored, reproducible from commit) and
labels the result **DEPLOYABLE** only when the cast booted AND served. This is the game the platform
is proven capable of creating — the scale bar Aethryn sets.

## Slice 3 (PROTOTYPED, shipped): the Seed Kernel — identity + lifecycle

This begins the full **CODEFORGE AND SEED PLATFORM PRODUCTION DIRECTIVE** (`/home/josh/Projects/
Codeforge prompt`) at its Stage 1. The inventory was blunt: there was *no* Seed as an entity — a
"Seed" was one global game-data pack chosen by `FORGE_SEED`, with no identity record, no lifecycle,
no restart recovery. `parts/seedlab/kernel.py` (MOD-10.052) builds the first brick:

- `SeedIdentity` / `SeedRecord` — a Seed's immutable facts + its mutable lifecycle state and audit
  trail (frozen; the Kernel evolves a Seed by persisting a replaced record).
- `SeedKernel` — `create` / `get` / `list` / `start` / `stop` / `archive` / `status`, with a legal-
  transition guard, **owner authorization on every mutation** (least privilege — the Seed is a
  control plane), and an audit event appended per act.
- `SeedStore` — the persistence seam: `FileSeedStore` (one JSON file per Seed, atomic write) makes
  **identity survive restart** (a fresh Kernel over the same directory recovers every Seed);
  `InMemorySeedStore` for tests. Clock + id-minter are injected, so there is no hidden state.
- A CLI (`python3 -m parts.seedlab.kernel create|list|status|start|stop|archive`) makes the
  lifecycle real and inspectable from the shell.

Isolated in `parts/seedlab/`: no `parts/world/` import, no `FORGE_SEED`, no game coupling. **Honest
scope:** "runtime start" is the lifecycle state machine + a persisted session, *not yet* a spawned
per-Seed server process (the game deploy case is proven separately by Slice 2). Persistence is
file-backed by choice — a DB-backed Seed-identity table is an additive migration deferred to Josh.

## Slice 4 (PROTOTYPED, shipped): the functional Project Hub (Stage 2)

`parts/seedlab/project_hub.py` (MOD-10.053) gives a Seed a place you can ENTER and inspect. It
composes the Kernel and projects one Seed's persisted state two ways from a single source of truth:

- `render` / `command` — the universal text fallback: the MUD `look` and its sub-verbs (`show
  status`, `list <sources|models|builds|tests|targets>`, `show risks`, `show history`).
- `contract` — the versioned (`seedlab.project_hub/1`) structured dict the Master Client consumes.
- `ProjectState` — the real contract shape for the engineering facets (sources/models/builds/tests/
  targets/risks/decisions). Empty until later stages fill it, and the Hub says so plainly ("none yet
  (Stage N)") rather than implying a capability that does not run.

Proven to render both the empty and the populated case; no game coupling.

## Slice 5 (PROTOTYPED, shipped): the local source connector (Stage 3)

`parts/seedlab/source_connector.py` (MOD-10.054) is the first real project-source connector and the
control plane's read-only front door. `LocalSource` registers a directory with `Provenance`, then
lets a Seed inspect it safely: `list_files` / `read` / `search` expose only **approved** files;
`identify` classifies manifests/tests/docs; `metadata` reads git branch+commit from `.git/` files
(no subprocess). Two safety rails, both refusal-tested: a **path boundary** (`..`, absolute paths,
and symlink escapes are refused — `resolve()` collapses them and the bounds-check rejects) and a
**secret denylist** (`.env`, keys, vaults, `.git`, `secrets*` are never listed, searched, or read).
A registered source's `source_label` feeds the Project Hub's `sources` facet — the first facet to go
from "none yet" to real data (integration-tested).

## Slice 6 (PROTOTYPED, shipped): source → persisted project model (Stage 4)

`parts/seedlab/source_modeler.py` (MOD-10.055) turns a registered `LocalSource` into a `ProjectModel`
without overclaiming: it derives **identity** (a manifest name, else the dir name), **entities** and
**interfaces** (inferred from the file layout + declared entry points), and carries **provenance**
straight from the source — then lists everything it could *not* determine (relationships, states,
actions, inputs, outputs, and the basis of each inference) in **`unknowns`**. The directive's rule is
honored literally: never claim complete automated understanding. `ProjectModel` gained `interfaces`,
`unknowns`, and `to_dict`/`from_dict`. `parts/seedlab/model_store.py` (MOD-10.056) persists models
(file-backed, one JSON per seed/model, survives restart) and labels them for the Hub's `models`
facet, each linked back to its source. Full flow integration-tested: register → model → persist →
the Hub's `models` facet and structured contract both show it.

## Slice 7 (PROTOTYPED, shipped): controlled build/test execution (Stage 5)

`parts/seedlab/tool_runner.py` (MOD-10.057) is the controlled-execution primitive. `run_tool` runs an
**allowlisted** command (a fixed, shell-free argv — an unlisted profile is refused and never executes)
inside the connected source (`cwd` bound to its resolved root), under a **timeout** and **output cap**,
with captured output **secret-redacted** (key blocks, `token=`/`password=` values). A non-zero exit is
the result, not a crash. Each run is a `ToolRunResult` persisted by a `FileRunLog` (append-only JSONL
per Seed, survives restart) and labelled into the Hub's `builds`/`tests` facets. It reuses the
FailsafeRunner pattern but binds cwd to the source. **Honest scope:** this executes code from the
approved source; the fences bound it, and stronger isolation (containers/namespaces) is the future
hardening the directive names as "sandboxing where practical."

## Slice 8 (PROTOTYPED, shipped): the first generated target — a runnable CLI (Stage 6)

`parts/seedlab/cli_generator.py` (MOD-10.058) is the recenter's payoff. `generate_cli` turns a
validated `ProjectModel` into a small but genuinely runnable Python CLI (a package with an argparse
`main`, a generated test, a `conftest.py`, a `pyproject.toml` with a console-script, a README).
Output is **reproducible** (no timestamps in the emitted code → identical files + checksums for the
same model), each file is **sha256-checksummed**, and the artifact carries the model's **provenance**.
`validate_runs` and `validate_tests` prove the target actually RUNS (`--version`) and its own
generated tests PASS — by executing it through the Stage-5 `tool_runner`, so the slice closes on
itself. `rollback` cleans up.

**The First Platform Proof is closed end to end:** create a Seed (Kernel) → enter + inspect it (Hub)
→ connect a real source (Connector) → extract a persisted, honest model (Modeler + Model Store) →
run it under control (Tool Runner) → **generate a working non-game target and prove it runs + tests
pass** (CLI Generator). All isolated in `parts/seedlab/`, the game untouched, every claim labeled.

## Next slices (roadmap, each an isolated vertical step)

1. A **MUD `model`/`seed` verb** + a Master-Client panel over `render_status`/`contract`/`render_model`
   (enter and inspect a Seed, its model, and its runs live in the running MUD, not just the CLI).
2. **Hardware extraction** (Stage 7): harvest the connector, model schema, model store, and runner as
   Hardware Store candidates once the vertical slice is proven end to end.
