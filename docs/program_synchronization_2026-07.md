> Superseded - the canonical mission lives in [docs/mission.md](mission.md) (mirrored from the fleet MISSION.md). Retained for context.

# CodeForge Program Synchronization (2026-07-27)

> **SUPERSEDED (2026-07-28).** This first synchronization has been refreshed after a nine-PR build
> wave: see `program_synchronization_2026-07-28.md` for the current audit and roadmap. Its roadmap
> below is largely executed (the Crafting Campaign is complete; live spawning, faction reputation,
> player statuses, and telegraphed boss specials all shipped). Kept for the record.

This document is the strategic synchronization the **Program Vision Reset** prompt asks for: audit,
summarize completed and active campaigns, identify architectural gaps and duplicate work, rank the
remaining work, and produce a roadmap. Per that prompt's own instruction -- *"Do not immediately
begin coding... Only after that roadmap is complete should implementation continue"* -- this is the
deliverable, and the roadmap at the end is the gate on further building.

It also serves as the **Phase I Current-State Report** for the Technology Forge prompt, and the
audit the Crafting prompt's PRIMARY RULE requires before crafting work resumes. All three prompts
share one rule -- *audit, recover, expand, reuse; do not duplicate; do not rewrite without evidence*
-- and this document honors it by pointing at existing artifacts rather than reproducing them.

---

## 1. Vision (affirmed, unchanged)

- **CodeForge** is an MMORPG development platform: creators design, build, operate, and share
  fully-realized MMORPGs without deep programming.
- **Aethryn** is the flagship -- a complete, production-quality MMORPG, not a demo. Every system
  must first make Aethryn a better game.
- **The Seed Platform** (compile a design spec into a whole MMORPG) is the engineering product
  extracted *after* Aethryn proves the design. It is **not** today's milestone.
- **Order of priority:** make Aethryn correct -> enjoyable/accessible -> stable -> scalable ->
  polished client -> preserve Seed extraction -> optimize only on evidence.

This matches the standing north star (see the fleet memory `fleet-northstar-2026-07-27`: *Vision B,
complete the game; two-phase -- finish Aethryn, then reverse-pack into the Seed Platform*). **No
strategic change is required; this prompt reaffirms the existing direction.**

---

## 2. Repository technology inventory (audit)

Frameless-Python-first, architecture-first (see `docs/adr/0003-framework-free-by-design.md`,
`docs/frameless_python.md`, `docs/framework_decision_matrix.md`). Frameworks are adopted only when
they earn their place (`docs/technology_intake.md`, the `make intake` gate).

**Runtime (`pyproject.toml`):** Python **3.13**; `pyyaml`, `sqlalchemy` (2.0), `fastapi`, `uvicorn`,
`websockets`, `pydantic`, `structlog`. Optional: `anthropic` (ai), `psycopg[binary]` (postgres).
**Dev/quality:** `ruff==0.16.0` (pinned), `mypy`, `pytest` + `pytest-cov` + `pytest-xdist`,
`pip-audit`, `bandit`, Hypothesis (property tests), coverage, pre-commit.

**Server / engine:** the tick is `handle_command(session, text) -> str` in `forge.py` (architecture
law 4). Threaded TCP telnet gateway with a login front desk (`adapters/gateway.py`, GMCP in
`parts/gmcp.py`); FastAPI admin surface (`adapters/api.py`); the world beat is the player's command (no
background threads) driving
`tick_zones` / `menace` / `tick_gather` / `tick_climate` / the hourglass delay-queue.

**Persistence:** SQLAlchemy 2.0 over SQLite (dev/default, absolute-path `codeforge.db`) and PostgreSQL
(prod, the CI `postgres` job proves parity); Alembic migrations; storage ports (membership,
character-store, job-progress) with in-memory + SQL adapters. See `docs/database.md`,
`docs/adr/0001-canonical-state.md`, `0002-derive-dont-store.md`, `0004-state-as-data.md`.

**Content:** the world is data -- `seeds/<world>/*.yaml` validated by loader gates in
`parts/world/seed.py`. **81** `parts/world/*.py` modules; aethryn boots ~53k rooms at demo scale,
~1,000,000 at `CODEFORGE_WILD_SCALE=19`.

**Clients (sibling repos):** `../codeforge-client` (terminal-first + native **PySide6/Qt** desktop,
asyncio + telnetlib3 + Textual, GMCP/MSDP), `../codeforge-console` (TS/web Creator Console).
`../codeforge-shelf` (harvested parts catalog), `../codeforge-evennia` (legacy clean-room study).

**CI (`.github/workflows/`):** `ci.yml` (check = ruff + mypy + pytest+coverage; docker; e2e;
postgres; terraform), `codeql.yml`, `docs.yml`, `publish-image.yml`, `scorecard.yml`. Docker image;
Render live demo. The full suite runs on `make check`, green on `main` (the CI badge is the live
source; exact test counts are not hardcoded in docs, per the truth gate).

**Existing decision records (recover, do not re-derive):** ADRs 0001-0009 (`docs/adr/`) cover
canonical state, derive-don't-store, framework-free, state-as-data, view-model, derived stats,
repo layout, subnet designations, deployment-as-code. Plus `docs/full_stack_forge_decision.md`,
`docs/full_stack_readiness_checklist.md`, `docs/observability.md`, `docs/performance*.md`,
`docs/architecture_c4.md`, `docs/database.md`, `docs/job_system.md`, `docs/character_system.md`.

---

## 3. Completed campaigns

**The engine (prior work).** Rooms/exits/items/doors/NPCs, account auth (salted pbkdf2-600k),
combat + statuses, 30-calling job ladder, ranks, seeds-are-games, the self-auditing stack
(Classification Registry, command spine, Safety+QA, PM panel, RepoIntegrityRitual, Career board,
Creator Workshop, Chronicle), security tooling, CI + demo.

**This session (2026-07-27), all merged green (#513-#533, 24 PRs):**
- **AAA content-density web (9 generators):** errands, zone storylines, signature relics, living
  rumors, dungeon inscriptions, the Forgeward Road spine, delve gear-sets, zone landmarks, named
  wardens. See memory `codeforge-content-density-campaign`.
- **Encounter depth:** boss enrage phases (`boss_phases.py`), additive to combat.
- **Quest-volume push:** cull + cull-by-kin, forage, delivery, dungeon-crawl -- **quests 205 ->
  1,682**, every one zone-scoped/distinct, modeled as N-step chains (no counter engine).
- **Content-generation campaign (all 5 slices of the prior prompt):** the Quest Archetype Library
  (`quest_archetypes.py`), the Zone Story Framework (`zone_story.py`, `region` verb), the Respawn
  Philosophy + `pick_room` primitive (`respawn.py`), the world-sim layer (`climate.py` season+weather
  `weather` verb; `factions.py` Order rivalries `factions` verb), and biome gather-herbs + salve
  recipes.

---

## 4. Active campaigns (memory anchors)

- **Complete the game (Aethryn AAA):** `codeforge-mission-complete-world`, `fleet-northstar-2026-07-27`.
- **Content density + quest volume:** `codeforge-content-density-campaign` (this session).
- **World generation / scale:** `codeforge-world-generation` (1M-room wildlands, O(1) NPC index).
- **Economy & world foundation:** `codeforge-economy-campaign` (ember-coin denominations).
- **Creator + Seed:** `codeforge-creator-and-seed-campaigns` (Seed Compiler #494, Creator Workshop
  #495) -- opportunistic, yields to game-completion.
- **Clients:** `codeforge-client-mk1`/`-parity`/`-transparent-aluminum`, `codeforge-qt-gui`.

---

## 5. Architectural gaps (evidence-based, ranked)

1. **Persistence for the new world-sim state (HIGH).** Factions ship as a *conflict model* only;
   **reputation-standing** (per-character numeric rep) needs a character column + migration. Climate's
   beat counter is runtime-only (resets on restart). Neither is wired to persistence yet -- honest,
   documented limitations, not hidden.
2. **Live dynamic spawning (HIGH for "alive world").** `respawn.pick_room` + the philosophy exist,
   but no live behavior draws from them yet. The opt-in item `spawn_pool` (wandering pickup) and
   rare-spawn rotation are the first uses -- the seam is laid, the wire is not.
3. **Crafting ecosystem depth (HIGH -- the Crafting prompt).** Today: `crafting.py` + `recipes.yaml`,
   ~2 base materials + 8 biome herbs -> salves, gather nodes, the maker Jobs. Missing: a **profession
   framework** (mining/logging/herbalism/skinning/smithing/alchemy/...), a **material library** tied
   to geography, **refinement chains** (raw -> refined -> component -> product), and **recipe
   acquisition** (train/discover/quest/faction). This is the largest coherent build gap.
4. **Structured internal event protocol (MEDIUM).** The tick returns text; GMCP/MSDP frames exist for
   the client, but there is no formal versioned event schema between server and clients/console.
   (Technology prompt Phase I-C/D.)
5. **Load/scale evidence (MEDIUM).** `docs/performance*.md` exist; there is no concurrency load
   profile (10/100/500/5000 concurrent) proving multi-player scale. Single-player determinism is
   strong; multi-occupant zone reset is a documented POC limitation (`zones._occupied`).
6. **Encounter variety (MEDIUM).** One boss mechanic (enrage). Phase-3/telegraphed specials/boss
   statuses remain (needs player-side DoT/daze handling first).

---

## 6. Duplicate-work findings (do NOT rebuild these)

- **The Technology Forge campaign re-asks decisions already recorded.** Python version, async model,
  DB (SQLAlchemy 2.0 + SQLite/Postgres + Alembic), packaging, testing/quality, observability, and the
  frameless posture are settled in ADRs 0001-0009 and `docs/framework_decision_matrix.md` /
  `full_stack_forge_decision.md`. **Action: reference and extend these; do not run a fresh
  benchmark-and-rewrite campaign.** Running it wholesale would violate the Vision Reset's own
  "Aethryn game-first, do not begin with a rewrite, do not install new deps until documented."
- **The Crafting prompt overlaps shipped work.** `crafting.py`, `recipes.yaml`, `gather.py`,
  `wildlands._BIOME_HERB` + `gatherable_materials`, the maker Jobs, and this session's herbs already
  exist. **Action: EXPAND these (professions + material library + refinement chains as data), never
  recreate the recipe/gather core.**
- **Clients already exist** (`codeforge-client` Qt/terminal, `codeforge-console` web). The Technology
  Forge "client decision matrix" is already answered: PySide6/Qt primary desktop + terminal, web
  console for creators. **Action: extend, don't re-select.**

---

## 7. Prioritized roadmap (dependency-ordered)

The gate: for each item ask *does it make Aethryn a better game, fit the CodeForge architecture, and
survive to the Seed Platform?* All below answer yes. Sequenced so each unblocks the next.

**Now (game-first, no new deps, expand canon):**
1. **Crafting Campaign, staged** -- the largest game gap and fully in-scope for "expand existing":
   - 1a. *Material library + refinement chains as data* -- extend `recipes.yaml` / a `materials.yaml`:
     ore->ingot, hide->leather, herb->reagent->potion. Reuse the herbs already shipped.
   - 1b. *Profession framework* -- gathering professions (mining/logging/herbalism/skinning/fishing)
     + crafting professions (smithing/leatherworking/alchemy), each a data-driven Job-adjacent track,
     composing with the existing 30-calling ladder and `gather`/`craft`.
   - 1c. *Monster materials* -- wire the bestiary to crafting (hide/scale/bone/essence drops feed
     recipes), building on `armory`/`relics` drop plumbing.
   - 1d. *Recipe acquisition* -- train/discover/quest/faction-gated recipes (uses `factions.stance`).
2. **Live dynamic spawning** -- wire `respawn.pick_room`: opt-in item `spawn_pool` drawn by the zone
   reset (the wandering pickup), then rare-spawn rotation. Unblocks weather/seasonal-gated spawns.
3. **Faction reputation-standing** -- a persisted per-character rep column (+ migration) over the
   shipped `factions` model; then faction-gated content and the faction-story archetype.

**Next (alive-world + polish):**
4. Encounter depth: boss phase-3 / telegraphed specials (needs player-side status handling).
5. Weather/seasonal-gated spawns + day/night, on the `climate` seam.
6. Structured event protocol: a versioned server<->client event schema (formalize GMCP/MSDP), so the
   Qt/web clients and console share one contract.

**Later (scale + platform, deferred by design):**
7. Concurrency load profiles + a multi-occupant zone-simulation model (region-based activation, so
   the 1M-room world keeps sleeping content cheap -- Technology prompt Phase VII/VIII).
8. Seed extraction (Phase 2): reverse-pack the proven Aethryn subsystems into the Seed Platform spec.

---

## 8. Deliverable mapping (Technology Forge / Crafting prompts)

| Requested deliverable | Status |
| --- | --- |
| Current-State Technology Audit | This doc, section 2 (+ existing ADRs/decision docs) |
| Python / Polyglot architecture schematic | `docs/architecture_c4.md`, `docs/framework_decision_matrix.md`, `docs/full_stack_forge_decision.md` |
| Server / Client component diagrams | `docs/architecture_c4.md`; clients in the sibling repos |
| Database & persistence plan | `docs/database.md`, ADRs 0001/0002/0004; gap in section 5.1 |
| Scheduler & simulation plan | the world-beat model (this doc, section 2); scale gap in section 5.5 |
| Security model | pbkdf2 auth, rank-gating, `make secrets`/bandit/pip-audit; `docs/adr` + security tooling |
| Observability plan | `docs/observability.md` |
| Toolkit decision matrix / ADRs | ADRs 0001-0009, `docs/framework_decision_matrix.md` (extend, don't redo) |
| Benchmark suite / load profiles | `docs/performance*.md` exist; concurrency profiles are the section-5.5 gap |
| Prioritized roadmap / migration plan | This doc, section 7 |
| Crafting: philosophy, professions, materials, chains | Section 5.3 + roadmap 1a-1d (staged build, gated by this roadmap) |
| Vertical slice | Aethryn already IS the playable vertical slice (login->world->combat->loot->job->quest->craft->persist) |

**Not produced, with rationale (honest, not skipped):** a fresh benchmark-and-rewrite campaign, new
dependency installs, microservice split, or client re-selection -- all explicitly forbidden by the
prompts themselves ("do not begin with a rewrite," "do not install new deps until documented," "do
not default to microservices," "do not duplicate existing capabilities") and already answered by the
existing ADRs. Running them now would contradict the Vision Reset's game-first order.

---

## 9. Recommendation

**No rewrite. No new dependencies. No strategic pivot.** The vision is already the operating
direction; the tech stack is already recorded in ADRs; the clients already exist. The single
highest-value next build is the **Crafting Campaign, staged (roadmap 1a-1d)** -- it is the largest
game gap, it is pure "expand existing canon," and its output (professions, materials tied to
geography, refinement chains) is exactly the kind of proven subsystem the Seed Platform will later
extract. Live dynamic spawning (2) and faction reputation (3) follow, each building on seams already
laid this session.

Implementation resumes against this roadmap.
