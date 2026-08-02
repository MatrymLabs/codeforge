# CodeForge Infrastructure Engineering Specification

*The operational backbone of a persistent, production-quality online MUD/MMORPG.*

This specification designs every backend service required to run CodeForge as a persistent online
world, scaling from a single developer to a distributed AAA deployment **without an architectural
rewrite**. It is deliberately not a gameplay design: it is the infrastructure the gameplay stands on.

It is written to CodeForge's truth discipline: every claim is labelled by its real status, so an
implementer (or an interviewer) always knows what is built versus what is designed.

## Status legend (read this first)

| Tag | Meaning |
|-----|---------|
| **EXISTS** | Built, tested, on `main` today. Cited to its module. |
| **PARTIAL** | The seam or a first slice exists; the full subsystem does not. |
| **DESIGNED** | Specified here; not yet built. |
| **DEFERRED** | Deliberately not built until scale demands it (with the trigger named). |

This document is the map, not the territory: where it cites a module, verify against the code before
relying on it, and where it says DESIGNED, expect no implementation yet. It aligns with, and does not
replace, the deeper existing docs it references: `architecture.md`, `architecture_c4.md`,
`concurrency_model.md`, `persistence_ports.md`, `seed_architecture.md`, the ADRs in `docs/adr/`, and
the honest capability picture in `aaa_benchmark_scorecard.md`.

---

## 1. Architectural principles (the laws the backbone obeys)

These are not aspirations; they are already enforced in code and every subsystem below inherits them.

1. **The server is authoritative; clients are presentation.** No gameplay state lives only on a
   client. A client renders projections (text, GMCP frames) of canonical server state and sends
   intents; it never owns truth. (EXISTS: `parts/gmcp.py` frames are read-only projections;
   mutations only through the tick.)
2. **State is canonical; text is a projection.** Renderers and broadcasts never mutate world state;
   only validated engine logic does. (EXISTS: architecture law 1.)
3. **The world is data.** Content lives in `seeds/*.yaml`, validated by loader gates in
   `kernel/world/seed.py`; it is never hard-coded in Python. (EXISTS.)
4. **The tick is the only door.** `handle_command(session, text) -> str` in `forge.py` is the single
   mutation entry point; every driver (TCP, web, future gateways) is a thin caller. (EXISTS.)
5. **Authorization before capability.** `@`-verbs check rank via `kernel/world/ranks.py` before any
   code runs; HTTP admin mutations require owner-account auth. (EXISTS.)
6. **Derive, don't store.** Records persist minimal canonical facts; stats/resources recompute on
   restore, pinned by a parity test. (EXISTS: `kernel/world/characters.py`.)
7. **Persistence is a port, not a framework leak.** Storage sits behind the `CharacterStore` Python
   contract with SQL and in-memory adapters. (EXISTS: `docs/persistence_ports.md`.)

---

## 2. Server architecture

### 2.1 Current shape (EXISTS) - a modular monolith with clean seams

CodeForge today is a **single-process modular monolith** with a threaded network front and several
independent "drivers" over one authoritative world. This is the correct Prototype/Alpha shape; §11
describes how it decomposes into services without rewriting the core.

| Subsystem | Status | Where it lives / how it works |
|-----------|--------|-------------------------------|
| **Game loop / tick** | EXISTS | `forge.handle_command(session, text) -> str`. Pure-function, command-driven (one command = one tick), synchronous under a global lock. There is no free-running frame loop; the "loop" is the stream of player commands plus the world beat. |
| **Tick / world beat** | EXISTS | A monotonic `beat` counter advanced inside the tick (`forge.py`: `tick_climate` / `tick_gather` / `_sands_beat`). Time-based systems (climate `climate.py`, afflictions/daze, aggression, respawn, self-closing doors) derive from the beat rather than wall-clock threads. |
| **Command dispatcher** | EXISTS | The command spine: `parts/commands.py` (`Command` / `CommandSet`), namespaced `CORE` / `ADMIN @` / `SEED`, longest-verb-first match, rank-gated, argument case preserved (architecture law 7). |
| **Event bus** | EXISTS | `kernel/world/events.py`: room-scoped `announce` / `announce_frame`, set-scoped `announce_to`, world-wide `broadcast`, and the typed GMCP push channel `push_gmcp` / `push_channel` (frames to a player set). Delivery is per-sink, dead sinks pruned. |
| **Session manager** | EXISTS | `kernel/world/session.py`: `SESSIONS: dict[player_id, Session]`, `roster()`. A `Session` is per-connection live state; identity is a lowercase label, renamed on login (`rename_echo` / `rename_gmcp`). |
| **Scheduler** | EXISTS | The beat is a cooperative scheduler for periodic world logic (respawns, reclose, climate); a general timed-job queue (`scheduler.py`, MOD-04.126, #594) rides the beat for one-shot/recurring jobs (e.g. the auction expiry sweep). |
| **Login / world / auth / character services** | PARTIAL | All exist as *modules in one process*: login dialogue in the gateway front desk, auth in `kernel/world/accounts.py`, character persistence behind the `CharacterStore` port. They are not yet separate *services* (§11). |
| **HTTP admin driver** | EXISTS | `adapters/api.py` (FastAPI): a separate driver that reads **canonical storage** (SQL + seeds), not live sessions, because separate processes share databases, not memory. Owner-auth on mutations. |
| **Read-only web Lens** | EXISTS | `parts/dashboard.py`: server-rendered HTML + JSON twin projecting real state (career board, QA gate, hardware store, perf run); frameless, fails honest. |
| **Message queue** | DEFERRED | Not needed in-process. Becomes the inter-service spine at Launch (§11). |
| **Plugin architecture** | DESIGNED | See §2.3. |
| **Hot reload** | DESIGNED | See §2.5. |

### 2.2 Service boundaries (the decomposition map)

The monolith is drawn so that each future service is *already a module boundary*. The seam to watch:
`api.py` reads canonical storage, not gateway memory - the **shared live-state bus** that lets a
second process see live players is now **built** (§11.3, Phase 4): presence rides it, so a live roster
is available cross-process; `api.py` can read `presence.online()` instead of only SQL. Room-scoped
world state across processes remains future (§11.4).

Target boundaries (module → future service):

- **Auth Service** ← `accounts.py` (credential verify, salted pbkdf2).
- **Character Service** ← `characters.py` + the `CharacterStore` port (load/save canonical facts).
- **World Server** ← `forge.py` tick + `kernel/world/*` (the authoritative simulation).
- **Session/Gateway** ← `gateway.py` / `web_gateway.py` (connection lifecycle, protocol).
- **Admin/Ops** ← `api.py` + `dashboard.py`.

### 2.3 Plugin architecture (DESIGNED)

Two extension mechanisms already exist and generalise into the plugin contract:
- **The command spine** - new verbs register as `Command` objects in a `CommandSet` with a namespace
  and rank; a "plugin" is a module that registers verbs + world data through the loader gates.
- **The Hardware Store shelf** (`kernel/shelf/*`) - reusable, tested parts with cards.

Spec: a plugin is a Python package that (a) declares its `Command`s and namespaces, (b) contributes
seed data through the validated loaders (never raw Python content), (c) registers event listeners on
the bus, and (d) declares a `CARD` + test twin. Plugins are **gated** (a feature flag / edition gate,
harvested pattern) so experimental surfaces never run in a public edition. Plugins observe and
register; they mutate world state only through the tick.

### 2.4 Scheduler (EXISTS, extends the beat)

A **timed-job registry** beside the beat (`scheduler.py`, #594): `(due_beat, job, every)` entries the
tick drains when due, one-shot or recurring. In use for the auction expiry sweep; a raising job is
dropped, not fatal. It is *deterministic and seedable* (beat-driven, no wall-clock in pure logic) so
tests stay reproducible, matching the beat discipline. Still to add: persisting due jobs (§4) so a
restart does not drop a scheduled close (today the sweep is re-armed at world assembly).

### 2.5 Hot reload strategy (DESIGNED)

Two tiers, both server-authoritative:
- **Seed/content reload (safe, first):** re-run the validated loaders (`seed.py`) to swap `WORLD`,
  `ITEMS` prototypes, `NPCS`, quests **under `TICK_LOCK`**, rejecting the swap if any loader gate
  fails (never load a broken world over a running one). Live sessions keep playing; only content
  refreshes. Data-driven design makes this the common case.
- **Code reload (harder, deferred):** module reimport is unsafe for a stateful monolith (dangling
  references, the "deploy ≠ restart" trap in `CLAUDE.md`). Prefer a **graceful rolling restart**
  (§10) over live code reload until the service split (§11) makes per-service restarts cheap.

---

## 3. Networking

### 3.1 Current (EXISTS)

- **Transport:** threaded TCP (`adapters/gateway.py`, `ThreadingTCPServer`, thread-per-connection under
  one `TICK_LOCK`) + an async web gateway (`parts/web_gateway.py`). `TCP_NODELAY` set (Nagle off) so
  each interactive line flushes without the ~40 ms delayed-ACK stall.
- **Protocol:** line-based text in, sanitized text out (control chars stripped). **Telnet** option
  negotiation (RFC 854/857) for password blackout (`IAC WILL/WONT ECHO`), codec in
  `kernel/shelf/telnet_codec.py`.
- **Structured channel:** **GMCP** (telnet option 201, `parts/gmcp.py`): offered on connect; a
  capable client enables it and receives `Char.Vitals/Room.Info/Target/Quest/Items/Skills/Resists/
  Party/Guild/Mail/Friends` frames and `Comm.Channel` chat, emit-on-change plus a live push channel.
  A raw `nc` never negotiates and stays plain text.
- **Connection lifecycle:** connect → offer GMCP + bulkhead admission → login front desk → seat
  (`bind_echo` + `bind_gmcp`) → play → teardown (save, leave party/trade/guild, `unbind_*`, drop
  session), all under the lock.
- **Rate limiting / flood protection:** a per-address login-failure ledger with a cooldown window
  (`gateway.py`), a concurrent-connection **bulkhead** (`kernel/shelf/bulkhead.py`, reject overflow
  fast), a max-line-bytes cap (a newline-less flood cannot be an unbounded read), and an idle
  timeout.
- **Reconnect/heartbeat:** the client owns reconnect with backoff + a circuit breaker
  (`codeforge-client`); the server drops idle sockets on timeout.

### 3.2 Gaps and design

- **Encryption (TLS/SSL): EXISTS.** A TLS listener (`ssl`-wrapped sockets, minimum TLS 1.2) is a
  config option via `CODEFORGE_TLS_CERT`/`CODEFORGE_TLS_KEY` (#600); the message layer is unchanged
  behind it. Plaintext remains the LAN default when no cert is set. (WSS for the web gateway is still
  DESIGNED.)
- **Message protocol / serialization:** text + GMCP (compact JSON) is the wire format today; it is
  sufficient through Launch. A binary packet format is DEFERRED until profiling shows JSON framing is
  a bottleneck (it will not be at MUD line rates).
- **Compression (MCCP): PARTIAL.** A decoder exists client-side but is not wired live; server-side
  MCCP2 is DESIGNED, low priority (JSON frames are small).
- **WebSocket/SSH transports: DEFERRED** (the swappable-shell seam exists; open on real need).
- **Anti-cheat philosophy:** the server is authoritative and the client sends *intents*, so
  client-side cheats cannot fabricate state - the strongest anti-cheat posture. Add server-side rate
  and sanity checks on intents (already partially present: input validation, rate limits) and an
  audit trail (§9) for economy/admin actions. Never trust a client-reported result.

---

## 4. Persistence

The heart of a persistent world. The rule: **if a player earned it, it exists until intentionally
removed.** The classification below is the contract.

### 4.1 The persistence matrix

| Data | Class | Status | Where / plan |
|------|-------|--------|--------------|
| Accounts (credentials) | **PERSIST** | EXISTS | `accounts` table; salted pbkdf2-sha256 (600k iters). |
| Characters (canonical facts: job, level, xp, location, rank, order, guild, coins, quest_state, allocated, professions, reputation, friends, equipped_gear) | **PERSIST** | EXISTS | `characters` table via the `CharacterStore` port; stats/resources **derive** on restore. |
| Per-job progression (jp/tp/level) | **PERSIST** | EXISTS | `job_progress` table. |
| Guilds (membership via columns + shared treasury) | **PERSIST** | EXISTS | `characters.guild/guild_rank` + `guilds` table. |
| Mail (async letters) | **PERSIST** | EXISTS | `mail` table. |
| Friends list | **PERSIST** | EXISTS | `characters.friends` column. |
| Equipped gear (prototype + rolled name/mods/rarity) | **PERSIST** | EXISTS | serialized on the character row; re-cloned on restore. |
| **Loose inventory (bags)** | **PERSIST** | **EXISTS (Keystone A, #590)** | A real `loose_items` table; item instances persist independent of a carrier (owner-keyed). Unblocked mail attachments, bank/guild item-vault, and the auction house. |
| Bank / vault storage | **PERSIST** | EXISTS | Items under a non-player owner (`vault:<player>`, `guildvault:<guild>`) on the items table (#591, #592). |
| Marketplace / auctions | **PERSIST** | EXISTS | `auction_listings` table; a listing is an escrowed item + price/expiry, closed by the scheduler (#595). |
| Currency | **PERSIST** | EXISTS | `characters.coins` (+ guild treasury). |
| Crafting progression | **PERSIST** | EXISTS | via professions on the character row. |
| Achievements / reputation | **PERSIST/DERIVE** | PARTIAL | reputation persists (`reputation` column); an achievements *system* is DESIGNED. |
| Ignore list, housing, player-created content | **PERSIST** | DESIGNED | New tables; ignore is cheap, housing/UGC larger. |
| Quest progress | **PERSIST** | EXISTS | `characters.quest_state` (compact serialized arc state). |
| World state - respawns, doors, weather, time, season | **DERIVE (from the beat)** | EXISTS | Recomputed from the persisted beat + seed, not stored per-object. Persist only the **beat** and deviations. |
| World state - dynamic events, faction control, ownership | **PERSIST** | DESIGNED | New world-state tables once these systems exist. |
| NPC state (hp, aggro, position) | **TRANSIENT** | EXISTS | Rebuilt from seed on boot; a felled boss reassembles. Persist only durable deviations (e.g. a killed unique on a lockout) when those systems land. |
| Live sessions / rosters | **TRANSIENT** | EXISTS | In-memory `SESSIONS`; rebuilt on reconnect. The cross-process roster now rides the shared bus (`presence`, §11.3); room-level session sharing is §11.4. |
| Admin/audit data | **PERSIST (append-only)** | EXISTS | Hash-chained audit log + bans table (§9, #596/#597). |

### 4.2 Save frequency, caching, recovery

- **Save frequency:** merge-save on meaningful transitions (logout, level, major inventory/economy
  change) rather than every tick - the current model (`save_character` writes canonical facts; the
  **merge-save law** never rewrites auth columns from a gameplay save). Add a **periodic autosave**
  sweep (every N beats) so a crash loses at most the last interval, and save-on-graceful-shutdown.
- **Caching:** live `Session` state and the loaded `WORLD`/`ITEMS`/`NPCS` are the in-memory cache of
  canonical seed + SQL. What may be cached: derived stats, computed panels (GMCP `_last_*`), read
  projections (the dashboard `Snapshot`). Invalidate on the mutation that sources them.
- **Recovery behavior:** on boot, load accounts/characters/guilds/mail from SQL and the world from
  validated seeds; the beat resumes from its persisted value; transient NPC/room state rebuilds from
  seed. A player reconnecting is restored from their canonical row (derive-don't-store guarantees a
  clean rebuild). No dual source of truth: SQL + seed are canonical, memory is a projection.

---

## 5. Database architecture

### 5.1 Current (EXISTS)

- **Engine:** SQLite via **SQLAlchemy 2.0** ORM, behind the `CharacterStore` **port** (SQL +
  in-memory adapters) so the framework never leaks into domain logic (`persistence_ports.md`).
- **Schema philosophy:** narrow canonical tables (8 today: `accounts`, `characters`, `job_progress`,
  `guilds`, `mail`, `loose_items`, `auction_listings`, `bans`); derive-don't-store keeps rows minimal.
  Labels are `lowercase_snake_case`, permanent (frozen identifiers - never restyled).
- **Migrations:** **Alembic** (`migrations/versions/*`), one revision per additive change, a
  step-test pins the count and the up/down chain.
- **Object identity:** characters keyed by name; items keyed by a minted instance id
  (`_mint_instance_id`) that already round-trips through save/load via `restore_instance` - the hook
  Keystone A builds on.

### 5.2 Recommendations (why each technology)

- **SQLite → PostgreSQL at the Public/Launch tier (DESIGNED).** SQLite is correct now: zero-ops,
  fast, transactional, perfect for single-process. The **port already isolates the swap** - a
  Postgres adapter behind `CharacterStore` (and its siblings) changes no domain code. Trigger: >1
  writer process, or concurrency past a single node. Postgres buys real concurrency, replication,
  and point-in-time recovery.
- **Indexing:** index every lookup key (recipient on `mail`, owner on the coming `items` table,
  character name). Keep indexes lean; measure before adding.
- **Versioning:** schema via Alembic; **data/record versioning** DESIGNED (a `schema_version` per
  serialized blob so an old save upgrades forward - the forgiving-restore pattern already drops
  unknown fields).
- **Backup / restore / DR:** PARTIAL. SQLite backup + a **restore test** EXISTS (#598): `restore_db`
  copies a snapshot over the live DB (disposing the cached engine first), and the test restores into a
  scratch DB and reads a character back - untested backups are not backups. Still DESIGNED: a
  *scheduled* snapshot + WAL archive, the Postgres tier (streaming replication + PITR + documented
  RPO/RTO), and dated + hashed evidence bundles.

---

## 6. World state persistence

Design principle: **derive from the beat + seed; persist only deviations and durable player-caused
changes.**

| Element | Persistence | Status |
|---------|-------------|--------|
| Room state (base) | Seed (canonical), rebuilt on boot | EXISTS |
| Doors (locked/open) | Derive from seed; persist a durable override only if a quest permanently reforges one | EXISTS (transient) / DESIGNED (override) |
| Containers | Ride Keystone A (a container is a location that owns items) | DESIGNED |
| Bosses / respawns / harvest nodes | Derive from the beat (respawn policies, `respawn.py`); persist a lockout/last-kill only when lockouts exist | EXISTS (transient) / DESIGNED (lockout) |
| Weather / time / seasons | Derive from the persisted beat (`climate.py`) | EXISTS |
| Dynamic events | Persist active event + expiry (uses the scheduler §2.4) | DESIGNED |
| Faction control / ownership | Persist as world-state rows | DESIGNED |
| Economy (currency in circulation, listings) | Persist (currency EXISTS; market rides Keystone A) | PARTIAL |

The **beat is the single persisted clock**: save it, and weather/season/night/respawn all reconstruct
deterministically - a huge persistence saving versus storing every object's timer.

---

## 7. Content storage (data-driven by law)

Architecture law 2: the world is data. Placement guide:

| Belongs in | What | Status |
|------------|------|--------|
| **YAML seeds** (`seeds/<world>/*.yaml`) | Rooms, NPCs, items, abilities, recipes, quests, settlements, doors, zones - the authored/validated world | EXISTS |
| **Generated data** | Procedural rooms/foes/loot from generators (`kernel/world/*` generators), emitted deterministically | EXISTS |
| **SQL database** | Mutable per-player and per-world runtime state (§4) | EXISTS |
| **Config** (env / `.env.example`, TOML) | Deployment knobs (DB path, scale, ports); secrets never committed | EXISTS |
| **Markdown** | Docs, ADRs, this spec | EXISTS |
| **Scripts / templates** | The Hardware Store parts, blueprints, seed compiler | EXISTS |
| **Assets** | Splash art (`splash.txt`); binary assets a future graphical client owns | PARTIAL |

Rule of thumb: **authored + validated → YAML; mutable + per-instance → DB; reusable logic → a shelf
part.** Never hard-code content in Python; a loader gate must validate it and fail loud.

---

## 8. Account system

- **Authentication (EXISTS):** salted pbkdf2-sha256 (600k iters), constant-time compare, plaintext
  never stored or logged, secrets never case-mangled (a hard law with regression tests).
- **Character selection / multiple characters (PARTIAL → DESIGNED):** accounts own characters
  (`characters.account`); a full "account → many characters → select at login" flow is DESIGNED
  (the schema supports it; the login dialogue is single-character today).
- **Permissions / roles (EXISTS):** rank-gated capability (`ranks.py`); owner-auth on HTTP admin.
- **Bans / moderation / audit (EXISTS):** a `bans` table (name, reason, moderator, #597) checked at
  the login gate (a banned hero is refused, outranking maintenance and even a wizard's rank), with
  `@ban`/`@unban`/`@bans` verbs that drop an online target and record to the audit log; plus the
  append-only audit log (§9).

---

## 9. Logging & observability

- **Structured logging (PARTIAL):** the observability shelf part (`kernel/shelf/observability.py`)
  exists; the gateway now emits structured JSON lifecycle events (`gateway_start`/`connection_open`/
  `connection_close`/`gateway_stop`, #601). Still to standardise: correlation ids per session/command
  fleet-wide.
- **Audit logs (EXISTS):** append-only, tamper-evident (hash-chained, matching the ship's
  `matrym-hashchain` capability, #596) for **admin actions, economy events, bans**. `@audit` tails it
  and `@audit verify` checks the chain end to end. These are evidence, not debug output - dated +
  hashed, retained per the ship's retention rules (never deleted on a
  calendar alone).
- **Domain logs (DESIGNED):** combat log, economy log (every coin/item faucet and sink - the data
  the scorecard flags is missing for sink/faucet tuning), login/session log.
- **Metrics / dashboards (PARTIAL):** the `dashboard.py` Lens projects real state; extend with live
  ops metrics (players online, tick latency, DB write rate, economy flow). Alerts + profiling hooks
  DESIGNED (the perf-run artifact already exists as a scored dimension).
- **Diagnostics (EXISTS):** `make doctor` reruns gates read-only and prescribes fixes; the readiness
  ritual and QualityGate make defects visible.

---

## 10. Operations

- **Startup (EXISTS):** `spark` (server) / `codeforge {serve,play,...}`; DB path anchored absolutely
  to the repo root so the same DB opens regardless of cwd (a closed heisenbug trap). Load SQL +
  validated seeds, resume the beat.
- **Shutdown (EXISTS):** the `@shutdown` verb calls the gateway's registered stop hook (dependency
  inversion; `forge` never imports the gateway). **Add save-on-shutdown** of all live sessions.
- **Graceful restart / rolling deployment (DESIGNED):** drain - refuse new connections, broadcast a
  maintenance notice, save all sessions, stop. At the service tier (§11), roll one service at a time.
  The **"deploy ≠ restart"** rule is doctrine: a running server is a snapshot of launch-time code;
  kill the ghost, restart from the repo root.
- **Maintenance mode (EXISTS):** a flag the login gate honours (sub-wizard logins turned away with the
  reason; admins bypass), toggled by `@maintenance` and broadcast (#589). A *scheduled* window via the
  scheduler (§2.4) is still DESIGNED.
- **Content deployment (EXISTS/DESIGNED):** content is data → deploy is a seed swap + a hot content
  reload (§2.5) or a restart; CI gates the seed before it ships.
- **Rollback (EXISTS/DESIGNED):** git revert for code/seeds; DB rollback via migration `downgrade` +
  the tested backup restore (§5.2). Every change is reversible - the optimization ethos requires a
  named rollback before a bold change.

---

## 11. Scalability (Prototype → AAA, without a rewrite)

The monolith is drawn to decompose along the module boundaries in §2.2. The evolution:

### 11.1 Prototype (now) - single process, SQLite
One world, threaded gateway under `TICK_LOCK`, SQLite, in-memory sessions. Correct for a solo dev and
a small private server. **This is where CodeForge is.**

### 11.2 Alpha/Public - same process, harden + Postgres option
TLS, autosave sweep, bans/moderation, audit logs, backups + restore test, Keystone A (durable items),
economy logs. Optionally swap SQLite→Postgres behind the port for a busier community server. No core
rewrite: the tick, spine, bus, and port are unchanged.

### 11.3 Launch - the shared bus (the one true seam) - BUILT
The single architectural investment that unlocks multi-process: **a shared live-state bus** so a
second process (a second gateway, the admin service) sees live rosters and can push to sessions it
does not own. **This is built** (Phase 4, #602-#605): a `MessageBus` seam (`kernel/world/bus.py`) with
an in-process default and a **stdlib socket broker** (`kernel/world/broker.py` + `socket_bus.py`) as
its network backing - no Redis dependency, and the seam keeps a Redis/queue adapter open behind the
same Protocol if scale ever demands it. The **event bus + push channel now publish onto it**, so
presence and membership-scoped delivery (party/guild/broadcast/chat) already cross processes. What
remains for full launch scale: room-scoped delivery and one authoritative shared world (§11.4). Once
those land:
- Multiple **gateway** processes behind a load balancer, one authoritative **world server**.
- The **auth/character** modules become callable services.
- The **broker** carries cross-service events (chat, party, presence) - it already carries the first.

### 11.4 Large community / AAA - distribute the world
Zone/shard the world across world-server processes (the zone/region model already partitions content;
`navigation.py` and the wildlands regions are the seam), interest-managed broadcasts, Postgres with
replication + read replicas, horizontal gateways. The domain logic (pure-function tick over a bounded
world) is **shard-friendly by construction** because it holds no cross-world global mutable state
beyond the bus.

**The guarantee:** every step reuses the tick, the spine, the event bus, and the storage port. The
only net-new backbone piece is the shared bus (§11.3); everything else is a config/adapter change.

---

## 12. Security

- **Auth security (EXISTS):** salted pbkdf2 600k, constant-time, no plaintext at rest or in logs.
- **Authorization (EXISTS):** rank-gate before capability; owner-auth on HTTP mutations.
- **Input validation (EXISTS):** loader gates fail loud on malformed seed data; text sanitized
  (control chars stripped) so chat can't hijack a terminal; case preserved for secrets.
- **Secrets management (EXISTS):** `.env` git-ignored (only `.env.example` tracked); `make secrets`
  (detect-secrets, baselined) gates commits; docs that name an env var carry an allowlist pragma.
- **Encryption (EXISTS):** TLS transport (§3.2), config-gated, minimum TLS 1.2 (#600).
- **Replay/abuse protection (PARTIAL):** rate limits + the login-fail ledger + the bulkhead exist;
  add per-intent rate/sanity checks and abuse detection (economy anomaly alerts) at Launch.
- **Administrative security (EXISTS/DESIGNED):** owner-auth today; add an audit trail (§9) and 2FA
  for admin accounts at the public tier.
- **Backup integrity (PARTIAL):** hash-chained audit logs (EXISTS, #596); a backup + restore-test path
  (EXISTS, #598); dated + hashed evidence bundles remain DESIGNED.
- **Federal posture (context):** readiness, never certification; AI output is not authority; see the
  ship's federal rules. This spec is technical controls (~30%); policy/process controls are human
  work no script performs.

---

## 13. Administration tooling

- **Live monitoring (PARTIAL):** the dashboard Lens; extend with players-online / tick-latency /
  economy-flow (§9).
- **Player & character lookup / edit (EXISTS/DESIGNED):** `api.py` reads canonical storage; owner-
  gated edit endpoints DESIGNED (validated, audited).
- **Item / NPC / world management (PARTIAL):** `@`-verbs (`@sg` item generation, rank-gated admin)
  exist in-world; a fuller world-edit surface DESIGNED behind owner-auth + audit.
- **Teleportation / economy inspection / ban management / diagnostics (EXISTS/DESIGNED):** admin
  verbs + `make doctor` today; ban management and economy inspection ride the bans table + economy
  log. **Never a raw shell** - the FailsafeRunner console pattern (controlled execution) is the rule.

---

## 14. Hardware Store integration

Every persistent system should be inspectable and reusable, not a hidden implementation detail. The
Hardware Store (`kernel/shelf/*`, catalogued with cards + test twins) already holds infrastructure
parts: the **bulkhead** (connection cap), **token-bucket** throttle, **circuit-breaker**,
**telnet-codec**, **observability**, **cohort** (transient group), **feature-flags**, **repository**
patterns. The doctrine for this spec:

- Every new backbone mechanism that is reusable is **harvested to a shelf part** with a card
  ("what data exists, where stored, how it flows, how to extend") and a test twin.
- The **Classification Registry** files every module + verb (completeness-gated), so the
  infrastructure is inventoried like a technical-order index - a creator can see what exists and how
  it composes.
- Storage is exposed as **reusable services** (the `CharacterStore` port is the model): a narrow
  Python contract, an adapter behind it, provable by tests. New persistence (items, bank, market)
  follows the same port shape so it is inspectable and swappable.

---

## 15. Implementation roadmap (phased)

Each phase is gated: `make check` green, branch → PR → CI → merge, evidence filed. Complexity is
S/M/L. This ordering respects dependencies - persistence foundations precede the features that need
them, and the shared bus precedes multi-process.

### Phase 0 - Harden the monolith (DONE)
- **Objective:** production-safe single process.
- **Items:** TLS transport; autosave sweep + save-on-shutdown; maintenance mode; structured logging
  baseline. **All shipped** (TLS #600, structured logging #601, autosave/shutdown #588, maintenance
  #589).
- **Dependencies:** none. **Complexity:** M. **Risks:** TLS handshake edge cases; autosave races
  (mitigate: save under `TICK_LOCK`).
- **Testing:** TLS connect test (fake cert); autosave round-trip; shutdown-saves-all.
- **Docs:** update this spec's status tags; a networking-security ADR.
- **DoD (met):** an internet-facing deploy loses no data on crash/restart and speaks encrypted
  transport.

### Phase 1 - Keystone A: durable items (DONE)
- **Objective:** loose inventory survives logout; the `items` table foundation. **Shipped #590.**
- **Items:** `items` table + migration; `loose_store` adapter (port-shaped); save/restore hooks in
  `characters.py`; reuse `restore_instance` + the gear roll-overlay.
- **Dependencies:** none (builds on existing item lifecycle). **Complexity:** M. **Risks:** a
  save/restore bug corrupts inventory - mitigate with a 2-player isolation test + affix round-trip
  test; keep equipped/loose partition explicit (`items_in(carrier) − session.equipped`).
- **Testing:** round-trip survival, 2-player bag isolation, rolled affix preserved, empty-bag no-op.
- **Docs:** a keel record (the design in this spec) + the persistence matrix flip to EXISTS.
- **DoD:** an item earned, logged out, and logged back in is still in the bag, identical.

### Phase 2 - Economy/social durability on the items table (DONE)
- **Objective:** the features Keystone A unblocks. **Items (all shipped):** bank/vault (items with a
  non-player owner, #591), guild item-bank (#592), mail attachments (#593), the scheduler (#594), and
  the auction house (listing = escrowed item + price/expiry + the scheduler close, #595).
- **Dependencies:** Phase 1. **Complexity:** L. **Risks:** economy exploits (dupe on trade/mail/AH)
 - mitigate with atomic transactions (the trade card's validate-all-then-apply is the pattern) and
  the economy audit log. **Testing:** atomicity/abort, no-dupe under concurrent claim, expiry close.
- **Docs:** economy-flow doc; sink/faucet accounting. **DoD:** items move async between players and
  survive restart with zero duplication, all logged.

### Phase 3 - Ops & observability (DONE)
- **Objective:** run it in the dark safely. **Items (all shipped):** audit log (hash-chained, #596),
  bans/moderation table (#597), backups + a restore test (#598), live metrics (#599, now including
  players-online off the Phase-4 roster).
- **Dependencies:** Phase 0. **Complexity:** M. **Risks:** log volume/perf (sample; async write).
- **Testing:** restore-from-backup smoke; audit append-only property test; ban gate refusal.
- **Docs:** an ops runbook. **DoD:** a restore test passes in CI and every admin/economy action is
  auditable.

### Phase 4 - The shared bus (multi-process enabler) (DONE)
- **Objective:** a second process sees live players. **Items (all shipped):** the MessageBus seam +
  in-process default (#602), presence on the bus (#602), the live-player metric (#603), the event/push
  channels routed through the bus (#604), and the stdlib socket broker + network adapter (#605).
- **Dependencies:** Phases 0-3. **Complexity:** L. **Risks:** the biggest architectural step - 
  ordering/at-least-once semantics, split-brain. Mitigate: the bus is a *seam behind the existing
  bus API*, mockable in tests (network never gates CI).
- **Testing (done):** a fake bus + a spy bus in tests; presence consistency; cross-process cohort
  delivery over `socketpair`; delivery survives a bus swap and a dropped subscriber.
- **Docs:** the §11.3 design + the keel records in #604/#605. **DoD (met for membership state):** two
  processes share one live roster and membership-scoped delivery (party/guild/broadcast/chat) reaches
  members on either process. **Deferred to Phase 5:** *room-scoped* delivery across processes and one
  shared authoritative world state (shared `SESSIONS`); that needs shared world state, not just the
  bus, so a player in one process does not yet see a player standing in the same room on the other.

### Phase 5 - Postgres + scale-out (DEFERRED until load demands)
- **Objective:** horizontal capacity. **Items:** a Postgres adapter behind the ports; connection
  pooling; read replicas; zone/shard the world. **Dependencies:** Phase 4. **Complexity:** L.
- **Risks:** distributed data consistency; do not start before the demo/portfolio needs it (scope
  discipline). **Testing:** adapter parity (same port tests pass on both backends); shard-boundary
  crossing. **Docs:** a scaling ADR + measured capacity. **DoD:** the same test suite passes on
  Postgres, and load spreads across nodes without a domain-code change.

---

## 16. Definition of complete (the whole backbone)

The infrastructure is "reference-implementation" complete when: the world persists across restarts,
crashes, updates, and logouts with no data loss; transport is encrypted; every earned item endures
until intentionally removed; every admin/economy action is audited; backups are tested by restore;
the same domain logic runs unchanged from one process to many behind the shared bus; and every
persistent subsystem is inspectable as a Hardware-Store-carded, port-shaped service. Each box is
checked only when **done and verified** (green gate + evidence), never aspirationally - readiness,
never certification.
