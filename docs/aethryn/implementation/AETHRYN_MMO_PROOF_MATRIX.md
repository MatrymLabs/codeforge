# Aethryn MMORPG Proof Matrix

Audit commit: `0f6d8ed876876f92fd77eed7caa14b48b6ba5fd7`

Status vocabulary follows the audit contract. A green local unit test is not a production proof unless the row says so.

## Baseline proof

| Proof | Exact command | Result |
| --- | --- | --- |
| Repository gate | `make check` | blocked at `ruff` not found on PATH, exit 127 |
| Formatter | `PYTHONPATH=. .venv/bin/ruff format --check .` | fail, unformatted files |
| Linter | `PYTHONPATH=. .venv/bin/ruff check .` | fail, 80 errors in captured run |
| Import boundary | `PYTHONPATH=. .venv/bin/lint-imports` | fail, one broken Seed Kernel boundary |
| Aethryn world | `FORGE_SEED=aethryn PYTHONPATH=. .venv/bin/python -m tools.world validate` | pass, CLEAN |
| Room batches | `FORGE_SEED=aethryn PYTHONPATH=. .venv/bin/python tools/validate_room_batches.py` | pass, 11 batches, 1068 batch rooms, 28745 assembled rooms |
| Canon | `FORGE_SEED=aethryn PYTHONPATH=. .venv/bin/python -m tools.world canon-check` | pass, CLEAN |
| Map concordance | `FORGE_SEED=aethryn PYTHONPATH=. .venv/bin/python -m tools.world map-concordance-check` | pass, CLEAN |
| Persistence doctor | `PYTHONPATH=. .venv/bin/python -c 'from kernel.persistence_doctor import inspect_persistence; print(inspect_persistence(repo_root=None).render())'` | warning, restore not verified |

| Full tests | `timeout --foreground 420s env PYTHONPATH=. .venv/bin/pytest -m 'not property and not fuzz' -q` | exit 124 after approximately 64 percent; failures and errors appeared, no final summary |
| Focused Aethryn | `env PYTHONPATH=. .venv/bin/pytest -q tests/test_aethryn_world_compiler.py tests/test_aethryn_runtime.py tests/test_aethryn_content.py tests/test_aethryn_room_prose.py tests/test_materialize_aethryn.py tests/test_aethryn_population.py tests/test_aethryn_quests.py tests/test_aethryn_actions.py` | pass, 64 passed in 83.25 seconds |
| Type check | `PYTHONPATH=. .venv/bin/mypy kernel adapters content tests forge.py --no-incremental` | fail, 155 errors in 49 files, 917 files checked |

## P0 proof rows

| Capability | Current status | Required proof before P0 completion |
| --- | --- | --- |
| Packet compiler | VERIFIED_FUNCTIONAL | deterministic rebuild of two worlds, stable output digest, package load, provenance, rollback |
| WorldIR | VERIFIED_FUNCTIONAL | packet normalization, stable-id comparison, deterministic source digest, and second-world fixture |
| Schema registry | VERIFIED_FUNCTIONAL | current content registry and duplicate-registration contract test |
| Reference resolver | VERIFIED_FUNCTIONAL | Veridia external references, second-world graph, and actionable broken-reference fixture |
| Compiler pass manager | VERIFIED_FUNCTIONAL | four real foundation passes, dependency ordering, targeted execution, and cycle rejection |
| Room content | VERIFIED_FUNCTIONAL | full published-world hierarchy, topology, prose, structured interaction, runtime reload |
| Account and character lifecycle | VERIFIED_FUNCTIONAL | two-client create/login/reconnect/invalidate, migration, archive/restore, security review |
| Atomic economy | VERIFIED_PARTIAL | concurrent trade, retry idempotency, merchant/craft/auction/mail reconciliation, duplicate exploit suite |
| Multiplayer combat | VERIFIED_PARTIAL | two-client support credit, encounter reset, disconnect, loot eligibility, concurrent load |
| Social systems | VERIFIED_PARTIAL | two-client chat/party/guild, block enforcement across channels, moderation audit |
| Command and client parity | VERIFIED_PARTIAL | generated registry/help, text and structured parity matrix, narrow/no-color/accessibility review |
| Persistence | VERIFIED_FUNCTIONAL | isolated backup hash, restore transcript, row comparison, migration and rollback proof |
| World state | VERIFIED_PARTIAL | scoped state schema, restart, package migration, consequence and conflict tests |
| Operations | VERIFIED_PARTIAL | metrics endpoint, crash recovery, restore drill, load and soak report, publish and rollback |
| Import boundary | DUPLICATE_OR_COMPETING | `lint-imports` clean with game adapter ports |

## Phase 1 implementation proof

| Proof | Exact command | Result |
| --- | --- | --- |
| Foundation tests | `PYTHONPATH=. .venv/bin/pytest -q tests/test_aethryn_compiler_foundation.py tests/test_aethryn_world_compiler.py` | pass, 24 passed in 7.00 seconds |
| Aethryn regression set | `PYTHONPATH=. .venv/bin/pytest -q tests/test_aethryn_world_compiler.py tests/test_aethryn_runtime.py tests/test_aethryn_content.py tests/test_aethryn_room_prose.py tests/test_materialize_aethryn.py tests/test_aethryn_population.py tests/test_aethryn_quests.py tests/test_aethryn_actions.py` | pass, 64 passed in 58.78 seconds |
| Phase 1 lint | `.venv/bin/ruff check` on changed compiler and test files | pass, all checks passed |
| Phase 1 formatting | `.venv/bin/ruff format --check` on changed compiler and test files | pass, 8 files already formatted |
| Phase 1 typing | `.venv/bin/mypy` on changed compiler modules | pass, 6 source files checked |
| Veridia compile | `PYTHONPATH=. .venv/bin/python -m tools.world compile-packet content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml --output /tmp/aethryn-phase1-build` | pass, emitted `world_ir.yaml` and output digest `6289ed8a0590c5acf6633e38e89735846e1f82e69b85c9a1c3c2657cbbb8f032` |
| World and canon gates | `world validate`, `validate_room_batches.py`, `canon-check`, `map-concordance-check` with `FORGE_SEED=aethryn` where applicable | pass, CLEAN; 11 batches, 1068 batch rooms, 28745 assembled rooms |
| Repository gate | `make check` | still blocked because `ruff` is not on PATH; the focused phase gates above pass |

## Phase 2 delivery proof

| Proof | Exact command | Result |
| --- | --- | --- |
| Delivery contracts | `PYTHONPATH=. .venv/bin/pytest -q tests/test_aethryn_delivery.py tests/test_aethryn_compiler_foundation.py tests/test_aethryn_world_compiler.py` | pass, 29 passed in 16.08 seconds |
| Delivery typing | `.venv/bin/mypy` on delivery, compiler, CLI, model, and delivery test files | pass, 6 source files checked |
| Delivery lint and format | `.venv/bin/ruff check` and `.venv/bin/ruff format --check` on delivery files | pass |
| CLI cache reuse | `world compile-packet ... --output <dir> --cache <dir>` twice | pass, identical output digest and cache entry |
| CLI semantic diff | `world diff <package-a> <package-b>` | pass, `semantic diff: CLEAN` for identical packages |
| Package integrity | `validate_package` through hotfix creation | pass, tampered or non-clean packages are refused |
| Hotfix contract | `world hotfix <base-package> <candidate-package> --output <dir>` | pass in delivery test; publication remains deliberately separate |

## Transaction foundation proof

| Proof | Exact command | Result |
| --- | --- | --- |
| Transaction contract | `PYTHONPATH=. .venv/bin/pytest -q tests/test_economy_transactions.py` | pass; includes SQL receipt replay |
| Transaction typing and lint | `.venv/bin/mypy` and `.venv/bin/ruff check` on transaction, database, migration, and test files | pass |
| Migration round trip | `PYTHONPATH=. .venv/bin/pytest -q tests/test_migrations.py` | pass; economy tables upgrade and downgrade cleanly |
| Full economy authority | Existing trade, shop, crafting, mail, auction, and loot paths through one durable mutation boundary | not yet proven; integration remains open |

## Vertical-slice evidence currently present

| Evidence | What it proves | What it does not prove |
| --- | --- | --- |
| Veridia packet tests | packet validation, deterministic compilation, room prose, state projection, rollback seam | full MMORPG runtime, multi-client combat, operations |
| Generated Veridia manifest | counts, input/output digests, provenance, clean validation | package migration, complete world dependency closure |
| Gateway tests | login, rate limits, TLS seam, GMCP, two-player local sharing | production session authority and scale |
| Trade and auction tests | selected atomicity and escrow behavior | one authoritative economy transaction layer |
| Deployment tests | local staged replacement and rollback controller | real database restore and live deployment |
| Load harness tests | harness calculations and report shape | tested capacity target or soak result |

## Release gate

The project must remain `not production-ready` while any of these are unproven:

- baseline lint, type, import, and test gates are red;
- full-world WorldIR and schema/reference coverage are not yet proven;
- player data restore has not been drilled;
- economy and combat are not authoritative across retries and clients;
- required P0 accessibility and multiplayer proofs are missing;
- load and soak limits are not measured;
- a production credential or external recovery dependency is unresolved.

## Phase 3 closure update

The two implementation limitations called out above are now closed at the source and command
boundaries:

| Proof | Exact command | Result |
| --- | --- | --- |
| Full-world corpus | `FORGE_SEED=aethryn PYTHONPATH=. .venv/bin/python -m tools.world full-world-check` | pass, `CLEAN`; 70 source files, 14 regions, 1,136 normalized source rooms, 204 items, 46 recipes, 42 legacy quests, 79 NPCs, 28 underground specs |
| Full-world determinism | `PYTHONPATH=. .venv/bin/pytest -q tests/test_aethryn_corpus.py` | pass; stable source and WorldIR digests |
| Unified economy boundary | `PYTHONPATH=. .venv/bin/pytest -q tests/test_economy_transactions.py tests/test_trade.py tests/test_shop.py tests/test_crafting.py tests/test_auction.py` | pass; multi-leg receipts cover trade, merchant, crafting, and auction flows |
| Currency authority | `PYTHONPATH=. .venv/bin/pytest -q tests/test_combat.py tests/test_durability.py tests/test_travel.py tests/test_guild.py` | pass; repair, travel, guild, combat faucet, bounty, and death toll use the durable ledger |
| Live identity/recovery | `PYTHONPATH=. .venv/bin/pytest -q tests/test_gateway_session_authority.py tests/test_persistence_doctor.py tests/test_hosted_recovery.py` | pass |

The remaining release-gate items are operational proof rather than missing Aethryn compiler or
economy implementation: the complete repository baseline still needs its unrelated lint/type/test
failures cleared, and production load/soak plus a real external restore drill still need evidence.
