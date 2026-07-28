# CodeForge Architecture Modernization Review (2026-07-28)

*Response to the Architecture Modernization Campaign: reevaluate the entire technical stack without
language bias, as if starting today. Every recommendation is grounded in a fresh audit of the actual
repository (concurrency, persistence, generation, clients, build/deploy/CI), not in memory or
preference. The rule cuts both ways: **do not preserve Python out of habit, and do not replace it out
of novelty.** Only evidence decides.*

The eleven required outputs follow. The one-line verdict up front, because it is the point:

> **The modernization CodeForge needs is architectural, not linguistic.** The evidence shows Python is
> the correct core for this content-and-rules-heavy domain (microsecond hot paths, no CPU
> bottleneck, no pathfinding, generation is fast). The real ceilings are a single global lock, an
> in-process global-state model, a command-driven (not background) clock, synchronous DB I/O, and no
> world-state persistence. Fixing those is worth doing; rewriting gameplay in Rust/Go is not.

---

## 1. Current Architecture (audited, with evidence)

**Runtime / language.** Python 3.13, frameless-first. Runtime deps (7): `pyyaml, sqlalchemy, fastapi,
uvicorn, websockets, pydantic, structlog`; optional `anthropic` (ai), `psycopg` (postgres). No native
code anywhere in project source (no C/Rust/Cython/`.so`) except PyYAML's opportunistic libyaml
`CSafeLoader` with a pure-Python fallback.

**Concurrency & networking.** Single process. TCP gateway = thread-per-connection
(`socketserver.ThreadingTCPServer`), but **all game logic is serialized behind one module-global
`TICK_LOCK`** (`parts/gateway.py:41`), so `handle_command` runs strictly serially regardless of thread
or core count. Four drivers funnel through the one `handle_command` "door": TCP telnet
(`parts/gateway.py`), FastAPI WebSocket (`parts/web_gateway.py`, genuinely asyncio but reuses the same
sync `TICK_LOCK`), GMCP out-of-band state (`parts/gmcp.py`, diff-pushed), and a FastAPI admin HTTP
surface (`parts/api.py`, reads SQL only, not live sessions). Good hygiene: `TCP_NODELAY`, line caps,
IAC stripping, idle timeout, per-IP brute-force lockout, a 128-seat `Bulkhead`.

**Simulation / scheduling.** No background clock. The "world beat" is a synchronous suffix appended to
every player command (`forge.py:1985-1988`: `tick_burns + tick_afflictions + menace + tick_zones +
tick_gather + tick_climate + _sands_beat`). World time therefore advances per-command, not per
wall-clock: it runs twice as fast with two active players and freezes when everyone is idle. Timers
are integer beat-countdowns on a shared `Hourglass` (`parts/shelf/hourglass.py`, capped at 4096) plus
per-Session countdown dicts. No wall-clock timers, no per-entity threads — the whole sim is
deterministic and replayable from a command sequence.

**Persistence & serialization.** SQLAlchemy 2.0 declarative ORM, **synchronous only** (no async
driver), SQLite by default / Postgres opt-in via one `DATABASE_URL` seam. Clean hexagonal design:
narrow `Protocol` ports (`CharacterStore`, `AccountCredentialStore`, `MembershipStore`,
`JobProgressStore`) with lazy SQL adapters + in-memory doubles; the domain imports no framework.
Alembic (10 linear migrations). Serialization is stdlib `json` + hand-rolled `k:v` strings on the
save/restore path (no `msgspec`/`orjson`). Strong `derive-don't-store` (ADR-0002): small save files,
recomputed stats. **Only player characters persist** — rooms, NPCs, item instances, and in-flight
quest runs are in-memory globals rebuilt from YAML at boot; NPC deaths, dropped ground items, and
world mutations vanish on restart.

**Content generation & performance.** Pure-Python deterministic (index-based, no randomness)
generators expand compact YAML into `Room`/`Npc` dicts at boot (`wildlands.py`, `spiral.py`,
`bestiary.py`). No pathfinding exists (movement is a dict lookup; travel is fixed waystones). Real,
dated micro-benchmarks (`benchmarks/perf_journeys.py`, `reports/performance/`): command dispatch
**8.5 µs**, combat strike **10.3 µs**, cold startup **~159 ms** (Raspberry Pi 5). An O(1) NPC
room-index exists (`npcs.py:49-53`). Performance is **not** a CPU bottleneck today; the only measured
costs were YAML re-parsing and eager imports, both already optimized with before/after evidence.

**Clients.** `codeforge-client` — asyncio + telnetlib3 + Textual + PySide6/Qt (+ optional Anthropic
co-pilot), speaking Telnet/GMCP, shipped as PyInstaller binaries. `codeforge-console` — TypeScript +
React 19 + Next.js 16, a **read-only REST/JSON dashboard** (not a game client).

**Build / deploy / CI.** setuptools build; `uv.lock` present, `uv lock --check` in CI, pip-installed.
Three Dockerfiles; single-container **ephemeral** Render demo (tmp SQLite, resets each deploy);
Terraform (state checked in). Server CI is exemplary (ruff + mypy + pytest branch-coverage + bandit +
pip-audit blocking + detect-secrets + SBOM + CodeQL + Scorecard, SHA-pinned actions) and gated by two
dependency-governance ledgers (`dependency_ledger.toml`, `intake_ledger.toml`). Observability is
`structlog` JSON on the HTTP surface only — **no metrics/traces/error-tracking, and the game
gateways do not log through it.**

---

## 2. Ideal Architecture (evidence-led, language-neutral)

Designing from today, for the same goals (a scalable authoritative MMORPG server + creator platform +
Seed extraction), the ideal shape is a **modular-monolith Python core** with these differences from
today, each justified by an audited weakness:

- **An async server foundation** (asyncio, structured concurrency via AnyIO/TaskGroups, optional
  uvloop) replacing thread-per-connection + one global lock. Rationale: the lock is the throughput
  ceiling and forbids a background clock. *This is the single highest-leverage change.*
- **A background world tick** decoupled from player commands (a real cadence for NPCs, weather,
  respawns, auctions), so world time is wall-clock-uniform and the world lives when idle.
- **Room/region-sharded, indexed state** with a players-by-room index (NPCs already have one) so
  broadcast is O(occupants) not O(all sessions), and `zone_of`/zone sweeps are O(1)/O(active), not
  O(zones×rooms). Rationale: the per-command full-map sweeps and O(all-sessions) broadcast are the
  algorithmic ceilings for a large world/many players.
- **Async persistence** (SQLAlchemy async + asyncpg on Postgres) so DB latency never stalls the loop,
  plus **durable world-state persistence** (a world-snapshot store) so NPC/item/world mutations
  survive restart. Redis for ephemeral/session/pub-sub *only when* multi-process arrives.
- **A structured, versioned event protocol** (typed events serialized with `msgspec`, shared schema
  generated for the TS console/client) as the internal contract, with human text as one projection.
  Rationale: today the internal protocol is text + ad-hoc GMCP JSON; the clients hand-mirror types.
- **First-class observability** (OpenTelemetry traces + Prometheus metrics + error tracking) feeding
  the Creator Console's green/yellow/red health story.
- **Native code only at future, measured boundaries** (Rust via PyO3/maturin behind a narrow FFI) —
  candidates are spatial indexing, protocol codecs, or heavy NPC-AI pathfinding *if and when* a
  benchmark proves a hotspot. None exists today.

Everything else stays: Python for game rules/content/tools, SQLAlchemy/Alembic, FastAPI/uvicorn,
PySide6/Qt + Textual client, TS/React/Next console, the pytest/ruff/mypy/Hypothesis quality spine.

---

## 3. Gap Analysis (current → ideal, ranked by evidence)

| # | Gap | Evidence | Severity |
| --- | --- | --- | --- |
| G1 | Global `TICK_LOCK` + in-process global state: no multicore, no sharding, one slow command stalls all | `gateway.py:41`; module-global `WORLD/NPCS/ITEMS/SESSIONS` | **High** (scale ceiling) |
| G2 | No background clock; world ticks only on player commands | `forge.py:1985-1988`; `aggression.py`, `zones.py` | **High** (fidelity + scale) |
| G3 | Synchronous DB under a concurrent/async server | no async driver anywhere in `*_sql.py`, `db.py` | **High** (I/O ceiling) |
| G4 | No world-state persistence (only characters) | `ITEMS/NPCS` in-memory; `quest._RUNS` runtime | **High** (persistent-world gap) |
| G5 | Per-command O(zones) sweeps; `zone_of` O(zones×rooms); broadcast O(all sessions) | `zones.py:57-62,169-171`; `events.py:56,70,80` | Medium (large-world scale) |
| G6 | No structured internal event protocol; clients hand-mirror types | text tick + `gmcp.py`; console `lib/types.ts` mirrors Pydantic | Medium |
| G7 | Observability is HTTP-surface-only; no metrics/traces/alerting; game gateways unlogged | `parts/shelf/observability.py` | Medium (ops/Creator Console) |
| G8 | Client repo weaker than server: no lockfile, no CVE/bandit/secrets/CodeQL, unpinned actions, ships binaries | `codeforge-client` CI | Medium (supply-chain) |
| G9 | The "million-room / 22 s / 1.9 GB" scale claim is asserted from a manual run, only arithmetically unit-tested | `wildlands.py:36-37`; no gated boot benchmark | Medium (evidence integrity) |
| G10 | Ephemeral single-container demo; no persistent DB in the demo path, no reverse proxy/autoscale | `render.yaml:19-24` | Low (portfolio-acceptable) |

**Non-gaps (do not "fix"):** CPU performance (microsecond hot paths, real benchmarks), the hexagonal
persistence ports, `derive-don't-store`, the quality/security CI, dependency governance, and the
frameless discipline are all strengths to keep.

---

## 4. Recommended Technology Stack

**Keep (justified by evidence, not habit):**
- **Python 3.13** for game rules, content systems, commands, generation, tools. Evidence: no CPU
  bottleneck, content/rules-heavy domain, microsecond dispatch, developer productivity dominates.
  Replacing it would be optimizing for novelty.
- **SQLAlchemy 2.0 + Alembic**, SQLite (dev) / **PostgreSQL** (prod) — mature, already abstracted
  behind ports; the migration path is proven.
- **FastAPI + uvicorn + websockets** for the HTTP/WS surfaces; **Pydantic** at the HTTP edge only.
- **PySide6/Qt + Textual + telnetlib3** (desktop/terminal client); **TypeScript + React + Next.js**
  (web console). Both are sound, mainstream, accessible.
- **pytest + Hypothesis + Ruff + mypy + coverage**; **uv** lockfile; the bandit/pip-audit/detect-
  secrets/SBOM/CodeQL/Scorecard security spine; the dependency/intake ledgers.
- **structlog** (extend it, below).

**Evolve (same tech, better use):**
- Move the server foundation to **asyncio-native** (AnyIO structured concurrency, optional **uvloop**).
- Add the **async DB path** (SQLAlchemy async + **asyncpg**).
- Extend **structlog** into an **OpenTelemetry + Prometheus** observability layer.

**Introduce (each earns its place, see §6):** `uv` (as installer everywhere), `msgspec` (event
protocol), `Redis` (ephemeral/pub-sub at multi-process), and **design-time-only** `NetworkX` (world/
quest graph audits). Rust/PyO3 held for future measured hotspots.

---

## 5. Technologies to Remove

Honestly, **little** — the stack is already lean (7 runtime deps, all justified in the ledger). The
evidence-based removals are corrections, not amputations:

- **The thread-per-connection + global-`TICK_LOCK` model** is *retired*, not removed, once the async
  foundation lands (§7 Phase B). It is correct today; it is not the endgame.
- **Committed Terraform state** (`deploy/terraform/render/terraform.tfstate`) — remove from git; move
  to a remote/locked backend (state can hold sensitive attributes).
- **Nothing else qualifies.** No dead dependency, no redundant framework, no abandoned package was
  found. Pydantic is correctly confined to the HTTP edge; YAML is content-only; the two client
  protocols (Telnet/GMCP for the game, REST for the dashboard) are each appropriate to their client.

---

## 6. Technologies to Introduce (evidence + the repo's own dependency gate)

Each must pass the repo's `dependency_ledger.toml` gate (why · stdlib alternative · removable) and, for
a new class, an `intake_ledger.toml` record. Ranked by value-now.

1. **uv as the installer everywhere (dev tooling).** The lock already exists; adopt `uv` for install
   in Docker and add a lock + `uv` to `codeforge-client`. Benefit: reproducible builds, 10-100× faster
   CI installs. Risk: low; removable (falls back to pip). *Do now.*
2. **Client-repo hardening (no new runtime dep, CI/tooling).** Add a lockfile, pip-audit, bandit,
   detect-secrets, CodeQL, and SHA-pin actions to `codeforge-client` (it ships binaries to users).
   *Do now — highest security ROI.*
3. **msgspec (introduce with the event protocol).** A typed, fast (C-accelerated) schema for the
   versioned server↔client event contract; generate the TS types from it (kills the hand-mirror
   drift, G6). Benefit: correctness (typed contract) + serialization headroom. Removable behind the
   protocol boundary. *Do when the protocol is formalized (Phase B/C).*
4. **asyncpg + SQLAlchemy async (with the async foundation).** Non-blocking DB. *Phase B.*
5. **Redis (only at multi-process).** Ephemeral session store, pub/sub for cross-process broadcast,
   rate limiting. Do **not** put authoritative state in it. *Phase C, gated on real multi-process need.*
6. **OpenTelemetry + Prometheus (observability).** Traces/metrics feeding the Creator Console health
   states. *Phase B/C, with the deployed multi-user server.*
7. **NetworkX — design-time ONLY.** World reachability + quest-graph validation as an offline audit
   tool (extends `scripts/world_audit.py`); **never a runtime dependency.** Low, optional. *Opportunistic.*

**Explicitly NOT introduced now (novelty without evidence):** Rust/PyO3/C++ (no measured hotspot — the
hot path is µs and there is no pathfinding to accelerate), gRPC/QUIC/HTTP-3 (WebSocket + a typed event
schema meets the client need; gRPC/QUIC solve problems we do not have), Kafka/NATS/RabbitMQ/Celery
(the world-beat + in-process bus suffice until multi-process, and the prompt's own rule is "simplest
system that meets measured requirements"), Kubernetes (a modular monolith on one-to-few containers is
right; do not distribute to look scalable), NumPy/SciPy/OR-Tools/Shapely (no bulk-math or geometry
hot path). Tauri/Electron: the Qt client already covers desktop; revisit only if a browser game client
is prioritized.

---

## 7. Migration Plan (staged, reversible, evidence-gated)

Sequenced so nothing blocks the game-completion work and every phase is independently shippable. Each
phase ends green on `make check` and behind the existing gates.

- **Phase A — Now, low-risk wins (days).** `uv` install everywhere + client lockfile; client CI
  security parity (pip-audit/bandit/detect-secrets/CodeQL, SHA-pinned); move Terraform state to a
  remote backend; add a *gated boot benchmark* that actually boots at `CODEFORGE_WILD_SCALE=19` and
  records rooms/time/RSS (closes G9 — turn the scale claim into evidence). No architecture change.
- **Phase B — The async foundation + event protocol (weeks, the pivot).** Introduce an asyncio server
  core behind the existing `handle_command` door (the four-driver seam already isolates transport from
  engine, which makes this tractable). Add a **background tick** owned by one supervised task
  (structured concurrency; every long-running task gets an owner, lifecycle, cancellation, tests).
  Formalize the **msgspec event protocol** and generate TS types. Add OTel/Prometheus. Keep the
  threaded gateway working in parallel behind a flag until the async path is proven under load.
- **Phase C — State model for scale (weeks, gated on real need).** Players-by-room index + O(active)
  zone ticking; async DB (asyncpg); durable world-state snapshotting (NPC/item/world persistence,
  closing G4); Redis for ephemeral/pub-sub when a second process is genuinely required. Region-based
  simulation so the million-room world keeps sleeping content free.
- **Phase D — Later, evidence-gated.** Native (Rust/PyO3) *only* if a profiler names a hotspot;
  concurrency load profiles (10/100/500/5k) as gated benchmarks; then Seed extraction of the proven
  subsystems.

**Reversibility:** every phase keeps the current path working behind a flag until its replacement is
benchmarked; the hexagonal ports mean the DB and (new) event/transport layers are swappable without
touching the domain.

---

## 8. Dependency Graph (target)

```
                         ┌─────────────────────────────────────────┐
   players ──telnet/GMCP─┤  transport drivers (thin)               │
   players ──WebSocket───┤   gateway | web_gateway | gmcp | api     │
   creators ─REST/JSON───┤                                          │
                         └───────────────┬─────────────────────────┘
                                         │  handle_command (the one door)
                                         │  + msgspec typed events (versioned)
                         ┌───────────────▼─────────────────────────┐
                         │  ASYNC SERVER CORE (asyncio/AnyIO,       │
                         │  optional uvloop) + supervised           │
                         │  BACKGROUND WORLD TICK                   │
                         └──┬───────────────┬──────────────┬────────┘
             domain (pure Python)      observability     scheduling
     rooms│combat│jobs│quests│craft   OTel + Prometheus   background tick +
     professions│reputation│afflict         │             hourglass wheel
     boss_specials│spawning│economy          │
                         │                    │
        ┌────────────────▼────────────────────▼──────────┐
        │  persistence ports (Protocol) + adapters        │
        │  async SQLAlchemy → PostgreSQL (durable:         │
        │  accounts│characters│world-state snapshots)      │
        │  Redis (ephemeral: sessions│pub-sub│rate-limit)  │  ← Phase C only
        └──────────────────────────────────────────────────┘

 content: YAML seeds ──(boot)──> in-memory world ; NetworkX = design-time audit only
 clients: PySide6/Qt + Textual (game) ; React/Next TS console (creator) — types generated from msgspec schema
```

Runtime deps stay minimal; new items (`msgspec`, `asyncpg`, `redis`, `opentelemetry`) enter only at
their phase, each with a ledger row. Native (Rust) is a *future optional* isolated crate, not a core edge.

---

## 9. Performance Expectations

- **Today (measured, keep):** dispatch 8.5 µs, combat 10.3 µs, startup ~159 ms — no regression is
  acceptable; these are gated.
- **Phase B async core:** removes the global-lock ceiling. Expected: throughput scales from
  `1/(command time)` for the *whole server* toward per-core concurrency for I/O-bound commands;
  a slow command no longer stalls every player. *Must be proven with a concurrency load benchmark, not
  claimed* (the prompt's rule, and G9's lesson).
- **Background tick:** wall-clock-uniform world time; NPCs/weather/respawns live when idle. Cost is
  bounded by region-based activation (sleeping regions cost ~0).
- **Phase C indexing:** broadcast O(room occupants) and zone work O(active regions) instead of
  O(all sessions)/O(zones×rooms) — the enabler for large worlds + many players.
- **msgspec:** typed events with C-speed encode/decode; removes hand-mirrored client drift.
- **Native (Phase D):** only pursued behind a named hotspot with a before/after benchmark; expected
  benefit is narrow and local by design.

Every number above is an *expectation to be benchmarked*, per this project's own evidence standard.

---

## 10. Security Review

**Strong today (keep):** salted pbkdf2-sha256 (600k) passwords, never logged; the merge-save law
(gameplay saves never blank auth columns, test-pinned); rank-gated `@`-verbs; owner-Basic-auth HTTP
mutations; per-IP brute-force lockout; `Bulkhead` seat cap; line-length caps + IAC stripping; bandit +
pip-audit (blocking on runtime) + detect-secrets + SBOM + CodeQL + Scorecard; SHA-pinned server
actions; secrets never in git.

**To address with the modernization:**
- **Authoritative-server discipline must survive the event protocol.** As typed events replace text,
  keep every capability/creator check on the server (the prompt: never rely on client-side hiding);
  validate every inbound event, version-negotiate, and rate-limit per connection.
- **Async I/O safety:** with structured concurrency, every task needs cancellation + failure handling
  + timeouts (no anonymous background tasks) — this is a security property (resource exhaustion),
  not just correctness.
- **Client-repo parity (G8):** the binary-shipping `codeforge-client` currently lacks CVE/SAST/secret
  scanning and SHA-pinned actions — highest-priority security fix (Phase A).
- **Redis/Postgres at scale:** TLS + auth + network isolation; never place authoritative state in a
  cache; backup encryption + restore testing (currently SQLite-only online backup).
- **Terraform state** out of git (may contain sensitive attributes).

---

## 11. Implementation Roadmap

Priority order = player experience + stability + security first, big architecture staged behind the
game's content completeness (the async core is the pivot, but the current model is *correct* for the
demo, so it is not urgent — evidence, not novelty, sets the pace).

1. **Phase A (now):** `uv` everywhere + client lockfile; **client CI security parity + SHA-pin**
   (highest ROI); Terraform state to a remote backend; the **gated scale benchmark** (close G9). Also:
   close the one open feature thread (`feat/faction-gated`) so the tree is clean.
2. **Observability seam:** extend structlog toward OTel/Prometheus; wire the game gateways in; feed
   the Creator Console health states.
3. **Event protocol (msgspec):** formalize the versioned server↔client event schema; generate TS types.
   (This also delivers the prior roadmap's "structured event protocol" item.)
4. **Async server foundation + background tick (Phase B, the pivot):** behind the `handle_command`
   door, flag-guarded, benchmarked against the threaded path before switchover.
5. **State-for-scale (Phase C):** players-by-room index + O(active) ticking; async DB; durable
   world-state persistence; Redis only when multi-process is genuinely required; region-based sim.
6. **Native + load profiles (Phase D):** Rust/PyO3 only on a profiled hotspot; concurrency load
   benchmarks (10/100/500/5k); then Seed extraction of the proven subsystems.

---

## Final statement

Not optimizing for Python, and not for novelty. The audit's evidence is unambiguous: CodeForge's core
language is the right tool for a content-and-rules MMORPG domain, and its genuine ceilings are
architectural — the global lock, the command-driven clock, synchronous I/O, absent world persistence,
and un-indexed large-world operations. The confident recommendation is to **evolve the Python core**
(async foundation, background tick, async + durable persistence, a typed event protocol, real
observability, region-based scale) and to **introduce native or other languages only at future,
measured boundaries** — none of which exist today. Every step is staged, reversible, and gated by this
project's own evidence and dependency discipline.
