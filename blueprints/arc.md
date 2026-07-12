# ARC: the Assurance, Readiness, Control review system

*ARC is CodeForge's umbrella engineering-review system. It adds no new gate: it composes the ten review dimensions CodeForge already has into one honest Assurance/Readiness/Control verdict, so any meaningful change can flow through a single readiness check that reads filed evidence and never invents it. The ARC Chamber is its room; the world is the interface.*

- **id:** `arc`
- **status:** draft

## Requirements

1. Purpose: give every meaningful change one place to prove it is ready to advance, by composing existing reviews rather than duplicating them (search-for-reusable-parts-first).
2. Composition, not reinvention: ARC's ten dimensions each map to a gate that already exists (architecture=ADRs/frameup, testing=qualitygate/make check, documentation=integrity ritual/CARD checks, dependency=make deps + dependency_ledger, performance=performance gate/benchmarks, security=make security + security-evidence, change=change_ledger, patch=patch_tracker + make patch, evidence=test_evidence/EvidenceLedger, release=release_gate/make readiness).
3. Inputs: the already-filed verdicts and evidence of those gates (read-only). ARC is a reader/orchestrator; it must never mutate world state or a gate's records (architecture law 1).
4. Outputs: one ARC report with a per-dimension status and an overall verdict, in honest labels (ready | watchlist | blocked), never a compliance or certification claim (readiness language only).
5. Rules: a lower authority never overrides a higher one; a MISSING dimension is never counted as a pass (borrow the test-evidence rule); any blocked dimension blocks the overall verdict; every status cites the gate and artifact it came from.
6. State: ARC holds no canonical state of its own. Each run derives its verdict from the gates' current evidence, so the report is reproducible from the recorded commit.
7. Interfaces: an ARC part (parts/arc.py) with a pure compose(dimensions) -> ArcReport core, plus an `arc` / `arc status` verb that renders the ARC Chamber panel (tick-reachable).
8. Security: ARC reads evidence only; it runs no gate as a side effect, holds no secret, and exposes no mutation. Rank-gating follows the existing admin-verb convention if it is ever made owner-only.
9. Testing: a twin with acceptance (all-ready -> ready; one blocked -> blocked) AND refusal (a missing dimension is not a pass; an unknown dimension fails loud) cases, plus an engine-tick reachability test for the verb.
10. Failure modes to handle: a gate that has never run (MISSING, not pass), a gate whose evidence is stale, a dimension with no wired source yet (declared, not silently omitted), and a gate that errors (distinct from a fail).
11. Dependencies: only parts already on the shelf (change_ledger, patch_tracker, test_evidence, qualitygate, integrity, release_gate, plus Makefile gate outputs). No new runtime dependency; stdlib-first.
12. Acceptance criteria: ARC composes all ten dimensions from real sources; the verdict is honest and cited; missing/errored dimensions can never read as ready; make check stays green; the ARC Chamber verb is reachable through handle_command.
13. Definition of Done: parts/arc.py + test twin + tick test green; the `arc` verb wired and in HELP; filed in the Classification Registry; cataloged if it earns Hardware Store status; a change-management/evidence pattern reference; and this Blueprint moved to status validated once the slice is built and proven.

## Tasks

- [ ] Slice 1 (read-only compose): build parts/arc.py with a pure compose() over a list of dimensions, each dimension a (name, status, source) triple; render an `arc status` panel; wire the verb and a tick test. Sources start as the gates already emitting a verdict; unwired dimensions are declared MISSING, never hidden.
- [ ] Slice 2 (wire the real sources): feed each of the ten dimensions from its existing gate's output (change_ledger/patch_tracker/test_evidence/qualitygate/integrity/release_gate/make deps/security/performance), read-only.
- [ ] Slice 3 (the room): make the ARC Chamber a real place per the world-is-the-interface vision, so entering it shows the current ARC verdict.
- [ ] Slice 4 (flow): let a change record (change_ledger) carry an ARC verdict reference, so 'every meaningful change flows through ARC' becomes literally true, gated by Josh's approval since it touches the change lifecycle.
- [ ] Throughout: honest labels only (ready | watchlist | blocked), cite every source, never claim certification, and keep ARC a reader that mutates nothing.

## Stack

- **core:** pure compose(dimensions) -> ArcReport, framework-free (parts/arc.py)
- **sources:** existing gates, read-only (change_ledger, patch_tracker, test_evidence, qualitygate, integrity, release_gate, make deps/security/performance)
- **interface:** the `arc` / `arc status` verb (the ARC Chamber), tick-reachable
- **tests:** pytest twin (acceptance + refusal) + engine-tick reachability test
- **labels:** readiness language only (ready | watchlist | blocked), never certification
