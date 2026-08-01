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
| **Project source → structured model** | **PROTOTYPED** | `parts/seedlab/project_model.py` (this slice) |
| Repo / IDE / API / DB connectors | **VISION** | none exist |
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

## Next slices (roadmap, each an isolated vertical step)

1. A **file-backed source connector** (read a spec/repo manifest from disk, with provenance) —
   PROTOTYPED → INTEGRATED.
2. A **MUD `model` verb** + a Master-Client model panel over `render_model` (inspect the model live).
3. A **Seed identity + local runtime** (create/enter a Seed distinct from a game world).
4. One **real build/test action** and one **generated target** (a small original CLI/API), with
   provenance — the sideways proof the platform *generalizes* past the game, now that the game-Seed
   deployment itself is proven real.
