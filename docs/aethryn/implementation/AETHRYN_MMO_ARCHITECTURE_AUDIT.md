# Aethryn MMORPG Architecture Audit

Audit date: 2026-08-06

Audit commit: `0f6d8ed876876f92fd77eed7caa14b48b6ba5fd7`

Branch: `feat/aethryn-room-batches`

This is the repository-grounded audit baseline for the implementation that followed. The audit did not change canon, generate new world content, or modify the local database. The worktree was already dirty at audit start; the Phase 1 foundation is recorded separately below.

## Executive verdict

The repository contains a working Aethryn packet compiler, an adapter-first WorldIR foundation, and a substantial, tested single-process MUD engine. The new foundation is proven for active packet records and a structurally different fixture, but it is not yet a full-world MMORPG compiler or a production-capable live-service platform.

The strongest verified path is:

```text
Aethryn packet YAML
  -> packet validation
  -> deterministic record enrichment and room prose
  -> generated package with manifest, provenance, validation report, and digest
  -> CodeForge room batch materialization
  -> existing room loader and engine tick
```

The principal remaining architectural risk is parallel ownership outside the new foundation. Packet sidecar models, legacy Seed YAML loaders, runtime registries, SQL persistence, SeedLab platform, and command spine still own related concepts without complete shared coverage.

## Phase 1 implementation update

The compiler foundation is now implemented as an adapter-first slice. `aethryn_ir.py` normalizes packet records, `aethryn_schema.py` registers versioned content contracts, `aethryn_references.py` resolves declared references, `aethryn_diagnostics.py` provides the common diagnostic envelope, and `aethryn_passes.py` executes source loading, normalization, canon validation, and reference resolution in dependency order. Existing packet output remains CodeForge-compatible and now includes `world_ir.yaml`.

This closes the foundation capability for the current packet scope. It does not close incremental builds, semantic diffing, content migrations, hotfix packaging, full-world normalization, transaction authority, or production operations proof.

## Post-audit release-gate update

The import contract was repaired after the baseline was recorded. SeedLab contains explicit
integration bridges for the live world, archive database, Hardware Store, and Aethryn content
projection. Those bridge edges are now listed in `.importlinter` as named exceptions, while the
generic SeedLab core remains protected from unreviewed game imports. The current `lint-imports`
result is 4 contracts kept and 0 broken. This is a gate repair, not proof that the long-term
port-and-adapter migration is complete.

## Audit procedure and baseline

Instructions read:

- `AGENTS.md`
- `content/seeds/aethryn/AGENTS.md`
- `kernel/world/AGENTS.md`
- `tests/AGENTS.md`

Repository state at audit start:

- branch: `feat/aethryn-room-batches`
- commit: `0f6d8ed876876f92fd77eed7caa14b48b6ba5fd7`
- dirty worktree: 74 status entries were present before audit documents were added
- Python: 3.13.5
- host: aarch64 Ubuntu Raspberry Pi host
- database files present: `codeforge.db`, `characters.json`, `save.json`, two backup snapshots

Commands and observations:

| Command | Result | Evidence |
| --- | --- | --- |
| `make check` | BLOCKED | shell cannot find `ruff`; exit 127 at `Makefile:31` |
| `.venv/bin/ruff format --check .` | FAIL | repository contains unformatted files, including active dirty implementation files |
| `.venv/bin/ruff check .` | FAIL | 80 errors in the fresh run, including unused imports, import order, and line length |
| `.venv/bin/lint-imports` | FAIL | 1 broken contract; `kernel.seedlab` imports `kernel.world` through several paths |
| `FORGE_SEED=aethryn ... tools.world validate` | PASS | `world validate: CLEAN` |
| `FORGE_SEED=aethryn ... tools/validate_room_batches.py` | PASS | 11 batches, 1068 batch rooms, 28745 assembled world rooms |
| `FORGE_SEED=aethryn ... tools.world canon-check` | PASS | `canon-check: CLEAN` |
| `FORGE_SEED=aethryn ... tools.world map-concordance-check` | PASS | `map-concordance-check: CLEAN` |
| `... tools.world compile-packet <Veridia packet> --output /tmp/...` | PASS | output digest `e2838d4ab74504e152a10666575e928e029c17e14a2f274bdd766f6778d43668` |
| `... kernel.persistence_doctor` | WARN | schema and Alembic head ready, restore is not verified |

The complete pytest baseline command was `timeout --foreground 420s env PYTHONPATH=. .venv/bin/pytest -m 'not property and not fuzz' -q`. It exited 124 after approximately 64 percent progress, with failures and errors visible before termination. It did not produce a final summary, so the full suite is not a passing proof. The focused Aethryn compiler/runtime/content command completed with 64 passed in 83.25 seconds. The full mypy command checked 917 source files and exited 1 with 155 errors in 49 files.

## Current source-to-runtime flow

### Aethryn content path

`canon.yaml`, `world_graph.yaml`, and `generation_contract.yaml` are loaded by the Aethryn canon, graph, and contract modules. Existing Seed YAML is loaded by `kernel/world/seed.py`. Authored and generated room batches are folded into the room registry by `kernel/world/room_batches.py`. `kernel/world/world.py` assembles procedural fields, wildlands, caves, underground zones, delves, settlements, items, NPCs, and batches into the global runtime world. `forge.py` dispatches commands through the engine tick. Gateway adapters call the same session and tick path.

The newer packet path is independent of a full world assembly pass. `aethryn_validation.py` parses and validates a packet. `aethryn_compiler.py` enriches packet records, builds room presentation, writes package YAML, and publishes one room batch. `aethryn_runtime.py` reads selected generated records and projects read-only signals into room presentation. `aethryn_state.py` persists a small reversible state seam.

### Persistence path

`kernel/world/db.py` owns SQLAlchemy models and supports SQLite by default with a PostgreSQL URL seam. Alembic has 20 checked-in revisions, with the local database at revision `f8b1c2d3e4a5` according to the persistence doctor. Character and account adapters preserve older function surfaces. Item instances, quest state, guilds, mail, auctions, and other features use several additional stores and JSON fields.

### Operations path

The repository contains structured logs, Prometheus-style metrics, maintenance mode, backup helpers, a persistence doctor, a local deployment controller, SeedLab artifacts, and release gates. These are useful components, but their ownership is split between `kernel/world`, generic `kernel`, SeedLab, and adapters. A restore drill is explicitly not claimed by the persistence doctor.

## Duplicate or competing authorities

| Concept | Competing owners | Audit finding |
| --- | --- | --- |
| Room content | base Seed YAML, authored room batches, generated room batches, procedural field and wildland generators | No single normalized room record owns all metadata and references |
| Canon | `canon.yaml`, lore documents, packet validator, legacy prose registries | Current checks are useful but not a repository-wide source precedence service |
| Items | legacy Seed item prototypes, material culture catalog, runtime `items.py`, character JSON/SQL snapshots | The packet compiler flattens catalog data into Seed-shaped records |
| Quests | legacy `quest.py` workflows, packet quest records, Aethryn quest adapter, state JSON | Packet validation and runtime state are separate contracts |
| Events and state | climate/scheduler/events, Aethryn state sidecar, quest consequence store | Scope, migration, and conflict policies are not unified |
| Persistence | SQLAlchemy/Alembic, JSON save files, loose item stores, SeedLab SQL/file stores | Player and platform state have different migration and rollback controls |
| Commands | command spine, legacy `handle_command` branches, Aethryn builder CLI, `tools.world` | No one registry generates all help and structured/text capability contracts |
| Diagnostics | survey, Aethryn validation reports, persistence doctor, release gates, import linter | Diagnostic schemas and exit policy differ by subsystem |

## Domain findings

### Content compiler

Status: `VERIFIED_FUNCTIONAL` for validated Aethryn packets and the adapter-first compiler foundation; `VERIFIED_PARTIAL` for a unified MMORPG compiler.

The packet compiler has typed dataclasses, deterministic SHA-256 digests, room prose generation, versioned package manifests, provenance, validation reports, semantic record comparison, publication, file rollback, a deterministic package cache, and bounded hotfix packaging. Three active packets have clean manifests. The implementation is packet-oriented and writes CodeForge-compatible room batches.

Remaining compiler gaps are full-world source normalization, actual content and save migrations, dependency-aware per-record rebuilding, hotfix application and publication controls, and a generic profile/plugin boundary. The current cache is conservative package reuse, not a complete affected-record rebuild graph. Publication rollback still copies one room batch, not a complete runtime package plus world state.

### World content

Status: `VERIFIED_PARTIAL`.

Room hierarchy, exits, room prose, population records, economy and ecology records, quest pressures, items, crafting, merchants, loot, and state changes are represented in the Veridia packet and are validated for the implemented slice. The assembled Aethryn world also contains legacy and procedural content. The current evidence does not prove all 14 regions, all routes, all economy dependencies, all generated rooms, or all runtime records pass one cross-system graph.

### Account and character lifecycle

Status: `VERIFIED_FUNCTIONAL`, not production-ready.

The code has PBKDF2 password hashing, mixed-case password regression tests, account registration, character selection and persistence, gateway login flows, reconnect tests, bans, character recovery paths, and Alembic persistence. There is no demonstrated production account-recovery delivery path, multi-process session authority, verified combat logout policy, or tested restore of a live player database.

### Social systems

Status: `VERIFIED_FUNCTIONAL` for local party, guild, friends, chat, mail, ignore-related seams, and moderation basics; `VERIFIED_PARTIAL` for persistent multiplayer community operations.

Party, guild, guild vault, friends, world chat, mail, bans, and gateway communication have tests. The audit found no complete reporting, appeal, privacy, staff case workflow, or cross-process social authority proof. Block and ignore behavior across every channel is not established by the current proof set.

### Combat and encounters

Status: `VERIFIED_PARTIAL`.

The single-process engine has deterministic combat, NPC counterattacks, boss phase behavior, raid difficulty and bounty seams, loot, defeat and recovery, party progression sharing, and combat tests. It does not have a unified encounter identity model, contribution ledger covering support roles, robust encounter ownership/tagging rules, instance lifecycle, checkpoint migration, or concurrent encounter load evidence.

### Items, transactions, and economy

Status: `VERIFIED_PARTIAL`.

Trade has atomic confirmation tests, auction escrow and expiry tests, crafting, merchant flows, equipment, durability, mail attachments, guild vault, and coin persistence. The audit did not find one authoritative transaction service or a currency ledger with immutable faucet and sink records. Several flows mutate player coin and item ownership through feature-specific stores. Duplication tests exist for selected paths, but there is no whole-system reconciliation or idempotency contract covering reconnect and retry across all flows.

### Progression and balance

Status: `VERIFIED_PARTIAL`.

Player levels, job progress, professions, abilities, rewards, threat bands, and equipment budgets exist in separate modules. Tests cover many local formulas. A normalized balance intermediate model and deterministic whole-loop simulations for leveling, crafting profitability, currency inflation, group scaling, and endgame progression are not established.

### World state and live simulation

Status: `VERIFIED_PARTIAL`.

Climate, scheduler, events, roaming, Aethryn runtime signals, quest consequences, and a persistent reversible state file exist. The Aethryn runtime documentation explicitly says it does not yet simulate NPC movement, production quantities, shop depletion, or population runtime. State scope, migration, conflict policy, and rollback across character, party, instance, guild, zone, region, event, and global scopes are not unified.

### NPC and creature runtime

Status: `VERIFIED_PARTIAL`.

NPC records, schedules, roaming, creature populations, spawn pools, encounter groups, crowd abstractions, habitat checks, and combat behavior exist. The live adapter projects signals and does not yet provide a complete deterministic schedule and movement simulation with stuck recovery and runtime cost budgets.

### Clients and commands

Status: `VERIFIED_PARTIAL`.

Telnet, WebSocket, GMCP frames, room/vital/item/skill projections, login flows, text commands, command namespaces, and help indexing exist. The Aethryn builder commands are distinct from the gameplay command spine. There is no demonstrated complete parity matrix for every P0 system, and accessibility, narrow-client, screen-reader, and structured-client reviews are not a complete release gate.

### Server and concurrency

Status: `VERIFIED_PARTIAL`.

The gateway supports threaded TCP, WebSocket handling, connection caps, timeouts, TLS configuration, and a shared in-process world. Persistence is SQL-backed with a PostgreSQL URL seam. The authoritative world, session registry, event delivery, and several stores remain process-local or file-local. There is no measured capacity envelope, zone ownership model, horizontal scale model, cross-process encounter authority, or safe multi-instance world-state protocol.

### Operations, reliability, and security

Status: `VERIFIED_PARTIAL`.

Structured logs, metrics, maintenance mode, backups, a persistence doctor, security tests, deployment staging, release gates, and rollback components exist. The doctor reports restore as unverified. The audit found no completed restore drill, disaster recovery proof, production load/soak result, complete alerting policy, or full privilege and privacy review for a live service.

### Testing and release engineering

Status: `VERIFIED_PARTIAL`.

There are 473 test modules and broad unit/integration coverage, including Aethryn compiler, room prose, materialization, accounts, gateway, combat, trade, party, guild, auction, migrations, observability, deployment, and load harness tests. The baseline repository gate is red because the available source tree has formatting, lint, import-boundary, type, and test failures. The full test command timed out before producing a final count. Existing tests are not enough to prove the MMORPG claims above.

## Active legacy risks

- `kernel/world/authoring_prose.py` remains an active fallback source. It is useful as an adapter but can compete with packet prose and requires explicit precedence tests.
- Legacy Seed YAML and procedural generators remain active alongside generated packet batches.
- `forge.py` and `handle_command` retain legacy dispatch branches alongside the command spine.
- JSON save files remain present beside SQL persistence and must not silently become a second player authority.
- SeedLab imports into `kernel.world`, which the import boundary checker reports as broken. This is architectural coupling, not only style debt.
- Existing documentation claims focused readiness in places where the current audit finds only vertical-slice evidence.

## Critical dependency chain

```text
WorldIR
  -> schema registry and migrations
  -> source precedence and normalization
  -> reference resolver and diagnostics
  -> ordered compiler passes
  -> versioned package and semantic diff
  -> runtime adapters and world-state migration
  -> persistent account/session/character authority
  -> transactional inventory and economy
  -> multiplayer social and encounter authority
  -> client parity and accessibility
  -> metrics, backup/restore, load/soak, publish/rollback
```

The first implementation phase should be the compiler foundation: WorldIR, schema registry, reference resolver, diagnostics, and pass manager. It is the smallest architectural move that reduces duplicate authority without changing Aethryn canon or player ids.

## HUMAN_DECISION_REQUIRED

No locked-canon decision was required for this audit. The following product or security choices require owner approval before implementation:

1. cross-process and horizontal-scale authority model for the world;
2. duplicate-login and session takeover policy;
3. death, item, currency, and durability loss policy for a persistent beta;
4. whether auction, guild storage, mail, PvP, housing, naval travel, and public events are P0 or feature-flagged P1/P2;
5. production database provider, backup retention, privacy retention, and account recovery channel;
6. whether old JSON saves are migrated, read-only imported, or retired after verified export;
7. publication approval ownership for full runtime packages and hotfixes.

## Recommended first implementation phase

Build a reversible Compiler Foundation slice:

1. define WorldIR interfaces over existing packet and Seed records;
2. register current record types, schema versions, reference fields, and adapters;
3. normalize one Veridia packet and one minimal non-Aethryn fixture through the IR;
4. route canon, hierarchy, topology, prose, economy, ecology, and quest checks through structured diagnostics;
5. add an ordered pass manager that still emits the existing room batch package;
6. prove deterministic rebuild, stable ids, semantic diff, and staged rollback;
7. keep legacy loaders active behind explicit compatibility adapters until the proof matrix is green.

This phase is P0 compiler infrastructure. It does not generate more rooms or change canon.
