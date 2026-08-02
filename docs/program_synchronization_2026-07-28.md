> Superseded - the canonical mission lives in [docs/mission.md](mission.md) (mirrored from the fleet MISSION.md). Retained for context.

# CodeForge Program Synchronization -- Refresh (2026-07-28)

This is the strategic re-synchronization the **Program Vision Reset** prompt asks for, run again after
a long build wave. It **supersedes** `docs/program_synchronization_2026-07.md` (the first sync, merged
in #534): same discipline -- *audit, summarize completed and active campaigns, find gaps and
duplicate work, rank the remaining work, produce a roadmap; do not begin with a rewrite; reuse before
rebuild* -- refreshed to the current state of the repository.

Per the prompt's own rule, this document is the deliverable and its roadmap (section 7) is the gate on
further building. It also re-serves as the **Technology Forge Phase-I current-state report** and the
**Crafting prompt's** required audit -- both of which are now largely *answered by shipped work*, not
just pointed at.

---

## 1. Vision (affirmed, unchanged)

- **CodeForge** is an MMORPG development platform; **Aethryn** is the flagship (a complete game, not a
  demo); the **Seed Platform** is extracted *after* Aethryn proves the design, not today's milestone.
- **Order of priority:** Aethryn correct -> enjoyable/accessible -> stable -> scalable -> polished
  client -> preserve Seed extraction -> optimize only on evidence.

No strategic change. This matches the standing north star (`fleet-northstar-2026-07-27`: complete the
game, then reverse-pack into the Seed Platform). The prompt reaffirms the existing direction.

---

## 2. What shipped since the first sync (#534) -- the completed wave

Nine feature PRs merged green to `main` (each: docs + validation + tests + registry filing +
`make check` green + full CI incl. codecov + an aethryn smoke test):

**The Crafting Campaign -- COMPLETE (1a-1d):**
- **#535 (1a)** material library + refinement chains as data (RAW -> REFINED -> COMPONENT -> PRODUCT;
  metal + alchemy chains). `docs/world/crafting_materials.md`.
- **#536 (1b)** the profession framework (`parts/world/professions.py`, MOD-04.102): 6 trades, skill
  by doing, persisted (`characters.professions` column). `docs/world/professions.md`.
- **#537 (1c)** monster materials -- bestiary drops hide/scale by body-class; leatherworking refines
  them into gear.
- **#538 (1d)** recipe acquisition -- recipes earned by profession level + sworn Order (`requires`
  gate; `crafting.locked_reason`), derive-don't-store.

**The alive-world / encounter wave:**
- **#539** live dynamic spawning -- wandering pickups (`spawn_pool` items, `zones._spawn_wanderers`,
  first use of `respawn.pick_room`).
- **#540** faction reputation (`parts/world/reputation.py`, MOD-04.103) -- per-character standing per
  Order, tiers, faction spillover, `standing` verb, persisted column.
- **#541** seasonal-gated spawns -- a wanderer's `seasons` gate over `climate`.
- **#542** player-side status effects (`parts/world/afflictions.py`, MOD-04.104) -- DoT + daze the
  player suffers, NPC `inflicts` spec.
- **#543** telegraphed boss specials (`parts/world/boss_specials.py`, MOD-04.105) -- a boss winds up
  (readable, no blow) then unleashes a heavy hit + guaranteed affliction; composes boss_phases +
  afflictions.

The engine baseline underneath is unchanged and green: the tick (`handle_command`), the frameless
Python-first stack (ADRs 0001-0009), SQLAlchemy 2.0 over SQLite/Postgres + Alembic, the self-auditing
stack (Classification Registry, Safety+QA, Ritual, Career board), CI + Render demo.

---

## 3. Active / in-flight

- **Faction-gated content (roadmap #2 follow-on) -- WIP, UNVERIFIED, on branch `feat/faction-gated`
  (commit 369a5eb).** Adds a recipe `requires.standing` (reputation-tier gate), a
  `grant_rep:<order>:<amount>` quest effect with `;`-chained effects, the aethryn Signet gated on
  Honored standing, and the opening quest earning Making standing. It was one cosmetic fix from a
  confirmed-green `make check` when this re-sync was called; **it needs a final gate run + PR before
  merge.** This is the single open thread.

Memory anchors for the broader campaigns: `codeforge-crafting-campaign`,
`codeforge-content-density-campaign`, `codeforge-world-generation`, `codeforge-economy-campaign`,
`fleet-northstar-2026-07-27`.

---

## 4. Duplicate-work findings (do NOT rebuild -- now mostly SHIPPED, not just deferred)

- **The Crafting prompt is now largely implemented, not pending.** Its Parts II-IX map to shipped
  work: profession system (#536), material library + refinement chains (#535), world distribution
  (biome gather nodes, pre-existing + #535), monster materials (#537), recipe acquisition (#538),
  resource-node seasonal/weather reinforcement (#541). **Action: EXPAND (more trades, more chains,
  more sources); do NOT re-architect the crafting core.**
- **The Technology Forge prompt is still answered by the existing ADRs.** Python version, async
  model, DB (SQLAlchemy 2.0 + SQLite/Postgres + Alembic), packaging, testing/quality, observability,
  the frameless posture, and the client decision (PySide6/Qt desktop + terminal, web console) are all
  recorded in ADRs 0001-0009 and `docs/framework_decision_matrix.md`. **Action: reference and extend;
  do NOT run a fresh benchmark-and-rewrite campaign** (the prompt itself forbids "begin with a
  rewrite" and "install new deps until documented").
- **Clients already exist** (`../codeforge-client` Qt/terminal, `../codeforge-console` web). Do not
  re-select or rebuild.

---

## 5. Architectural gaps (evidence-based, re-ranked after the wave)

Most of the first sync's gaps are now closed. What remains:

1. **World-sim persistence (MEDIUM, deferred by design).** The `climate` beat counter and the zone
   `_beats` are runtime-only (a restart rolls the season/timers back). Persisting them is *global*
   (not per-character) state, so it needs a new world-state store -- a persistence-model junction for
   cosmetic value (atmosphere, not lost progression). Documented, not hidden.
2. **Encounter variety beyond the first special (MEDIUM).** #543 shipped ONE telegraphed special
   shape; phase-3 thresholds, multiple/area telegraphs, and boss status-cleanses remain.
3. **Structured server<->client event protocol (MEDIUM, cross-repo).** The tick returns text;
   GMCP/MSDP frames exist but there is no versioned event schema shared by codeforge + the Qt/web
   clients. Larger, spans repos.
4. **Load / scale evidence (MEDIUM, deferred by design).** No concurrency load profiles
   (10/100/500/5k) proving multi-player scale; multi-occupant zone reset remains a documented POC
   limit (`zones._occupied`). The 1M-room world's sleeping-content cost is designed-for but
   un-benchmarked at concurrency.
5. **Afflictions/standing surfaced in a status view (LOW).** `render_afflictions` and the `standing`
   verb exist; afflictions still only announce per-beat rather than showing in a consolidated sheet.

---

## 6. Deliverable mapping (Technology Forge / Crafting prompts)

| Requested deliverable | Status |
| --- | --- |
| Current-State Technology Audit | This doc + the first sync + ADRs 0001-0009 |
| Python / Polyglot schematic; server/client diagrams | `docs/architecture_c4.md`, `docs/framework_decision_matrix.md`; clients in sibling repos |
| Database & persistence plan | `docs/database.md`, ADRs 0001/0002/0004; world-state gap in 5.1 |
| Scheduler & simulation plan | the world-beat model (tick_burns/menace/tick_zones/tick_gather/tick_climate/tick_afflictions + hourglass); scale gap in 5.4 |
| Security model / Observability | pbkdf2 auth, rank-gating, `make secrets`/bandit/pip-audit; `docs/observability.md` |
| Crafting: philosophy/professions/materials/chains/recipes/monster-mats/nodes | **SHIPPED** #535-#538, #541 + `docs/world/crafting_materials.md`, `professions.md` |
| Benchmark suite / load profiles | `docs/performance*.md` exist; concurrency profiles are the 5.4 gap |
| Vertical slice | Aethryn IS the playable vertical slice (login->world->combat->loot->job->quest->craft->profession->reputation->persist) |
| Prioritized roadmap | This doc, section 7 |

**Not produced, with rationale (unchanged):** a fresh benchmark-and-rewrite campaign, new dependency
installs, a microservice split, client re-selection, or global-climate persistence -- all either
forbidden by the prompts, already answered by ADRs, or low-value junctions.

---

## 7. Prioritized roadmap (dependency-ordered) -- the gate on further building

The three-question gate (better Aethryn? fits architecture? survives to the Seed Platform?) answers
yes for all below.

**Now -- close the open thread, then small high-value polish:**
1. **Verify + ship the faction-gated slice** (`feat/faction-gated`): run `make check`, fix anything
   red, PR -> CI green -> merge. This finishes the reputation loop (earn via quests, spend on
   rep-tier-gated recipes) and clears the one in-flight branch. *Smallest, highest-priority: an open
   loop should close before new work starts.*
2. **Encounter depth pass 2** -- a second boss-special shape (phase-3 threshold OR a
   telegraphed area/multi-target hit), over the `boss_specials` seam.
3. **Afflictions/standing in a status view** -- wire `render_afflictions` into the score sheet.

**Next -- alive-world + faction content (compose the shipped substrates):**
4. Weather-specific spawn gating (extend #541's season gate to weather).
5. Faction-story archetype -- a quest chain that earns/spends reputation, using `grant_rep` +
   rep-tier gates (once #1 lands).
6. Structured event protocol -- a versioned server<->client event schema (formalize GMCP/MSDP),
   shared with the Qt/web clients. Larger; scope as its own campaign.

**Later -- scale + platform (deferred by design):**
7. World-sim persistence (a world-state store) + concurrency load profiles + region-based activation
   (the 1M-room scale evidence, Technology prompt Phase VII/VIII).
8. Seed extraction (Phase 2) -- reverse-pack the now-proven Aethryn subsystems (crafting, professions,
   reputation, spawning, encounters) into the Seed Platform spec. This is the payoff of the whole
   wave: those systems are exactly the "proven in real gameplay" subsystems the Seed Platform
   generalises.

---

## 8. Recommendation

**No rewrite. No new dependencies. No strategic pivot.** The first sync's roadmap has been largely
executed: the Crafting Campaign is complete, the alive-world/encounter wave is in, and reputation +
faction gating is one verified merge from done. The single highest-priority action is to **close the
open thread -- verify and ship `feat/faction-gated`** -- then take the small polish items (encounter
pass 2, the status view) before opening the next campaign (faction-story content, then the event
protocol). Scale evidence and Seed extraction stay deferred by design until the game is content-rich.

Implementation resumes against this roadmap, starting with item 1.
