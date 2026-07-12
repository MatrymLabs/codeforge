# Pattern family: Change and Patch Management

*Ninth family doc for the Hardware Store's pattern shelf. Research basis: the Software Evolution /
Patch Management directive and its "Executive Summary" (patch lifecycle: Intake -> Triage -> Build ->
Test -> CI/CD gate -> Canary -> Monitor -> Rollout -> Verify -> Rollback -> Closure; MTTP, deployment
success rate, rollback rate). This doc covers the change-ledger part, the first slice of the Software
Evolution Engine.*

## Provenance

- **Origin:** `original_composition`. The change-ledger is not a copy of any framework; it is
  **assembled from five parts already on the Hardware Store shelf** and adds only the change domain
  model and the gated lifecycle wiring. **No code was copied.**
- **Assembled from:** `repository` (storage), `workflow` (role-gated lifecycle) on the pure
  `statemachine` (legal moves), `validation` (intake policy), and `test-evidence` (the promotion
  gate). Composition, not reinvention: the load-bearing behavior is proven once in each part's twin.
- **License:** MIT · **owner:** MatrymLabs · **human review:** built and reviewed this session.

## The part: `change-ledger`

`parts/change_ledger.py` -- a `ChangeLedger`: `open` a `Change` (id, kind, severity, optional CVEs,
components, rollback plan) and `advance` it through a gated lifecycle:

```
identified -> triaged -> approved -> building -> testing -> canary -> deployed -> verified -> closed
                    \-> rejected              \-> rolled_back <-/          <-/
```

The **load-bearing rules**: intake is validated and **fails loud** on a bad kind/severity or a
duplicate id; `approve`/`reject` are gated to the `approver` role and `deploy`/`rollback` to the
`operator` role; and a change **cannot reach canary until its test evidence passes** (a `tests_passed`
guard reads the change's `EvidenceLedger`). An illegal move is an honest `Refusal`, never an exception.

**Invariants (tested, incl. property-based):** only a legal, allowed, guarded transition ever changes
a change's state; a `Refusal` never moves it; rollback stays reachable from canary and deployed; an
approval-required change cannot be approved by a non-approver; canary is blocked without passing
evidence.

## GAME-TO-PRACTICAL TRANSLATION

- **Game component:** a world-maintenance log (`parts/maintenance.py`).
- **Core behavior:** record a change and drive it through a gated, role-and-evidence lifecycle.
- **Game-specific presentation:** "World maintenance log:" with each entry's lifecycle state.
- **Reusable domain logic:** the whole `ChangeLedger` (game-free).
- **Practical applications:** patch trackers, release trains, dependency-update pipelines, change
  control boards.
- **Required abstraction:** a change record + a gated lifecycle + an evidence gate; already in the core.
- **Security implications:** a CVE fix must not reach canary before its tests pass; role gating keeps
  approval and deploy separate from build.
- **Testing implications:** legal-transitions-only, rollback-always-reachable, approval-role-gated,
  evidence-gated-canary.
- **Hardware Store candidate:** YES (stocked as `change-ledger`).

## Adapters (one core, two lives)

- **Game:** `parts/maintenance.py` -- the `maintenance` verb shows the world's own change log, its
  entries sitting at different lifecycle states. Tick-reachable.
- **Practical:** `parts/patch_tracker.py` -- a `PatchTracker` records dependency bumps and CVE fixes
  and drives them through the same gated lifecycle; a patch cannot reach canary before `pass_tests`.

## Evidence

- Tests: `tests/test_change_ledger.py` (unit + property), `tests/test_maintenance.py` (game + tick),
  `tests/test_patch_tracker.py` (practical + a one-core proof).
- Manifest: `docs/hardware/change-ledger.yaml`. Trace it: `make loop PART=change-ledger`.
- **Maturity: `beta`** -- demonstrated in two contexts and tested, but not `stable` (no persistence,
  no policy engine, no real canary/rollback telemetry yet).

## Deferred (needs Josh's approval)

A policy engine (require-approval-for-major, emergency bypass, allowed-version-changes), SBOM-as-patch
-evidence, real canary/rollback telemetry, and persistence (currently in-memory) are later slices of
the Software Evolution Engine. Persistence stays in-memory/JSON until the persistence-architecture
juncture is decided.
