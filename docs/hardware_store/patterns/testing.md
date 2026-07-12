# Pattern family: Testing and Evidence

*Seventh family doc for the Hardware Store's pattern shelf. Research basis: "Full-Stack Design
Patterns for CodeForge" (section 19, Testing Harnesses) and the Software Parts directive's family 14
(Testing and Evidence). This doc covers the test-evidence part.*

## Provenance

- **Origin:** `independently_implemented_pattern`. The test-evidence / quality-gate idea (evidence
  records include environment and commit; missing evidence cannot be reported as passed) is a
  documented practice. **No code was copied**; the behavior was reimplemented from first principles.
- **Independently implemented:** the ledger, the status model (runner ERROR distinct from a test
  FAILED), the missing-is-not-a-pass rule, and both adapters.
- **License:** MIT · **owner:** MatrymLabs · **human review:** built and reviewed this session.

## The part: `test-evidence`

`parts/test_evidence.py` -- an `EvidenceLedger`: `expect` the checks you require, `record` each
outcome (with the ledger's environment and commit), and ask `passed()`. The **load-bearing rules**: an
expected-but-unrecorded check is `MISSING` (a step that never ran can never be a pass), a runner
`ERROR` is **distinct** from a test `FAILED`, and `passed()` is true only when there is at least one
check and every one is `PASSED`. `MISSING` is derived, never recordable (recording it fails loud).

**Invariants (tested, incl. property-based):** every Evidence carries its environment and commit;
`passed()` is true iff every recorded check passed; a missing or errored check is never a pass; gaps
list everything not passed.

## GAME-TO-PRACTICAL TRANSLATION

- **Game component:** a world-readiness certificate (`parts/world_cert.py`).
- **Core behavior:** record check outcomes and report an honest overall verdict.
- **Game-specific presentation:** "EVIDENCE: PASS" with per-check rows.
- **Reusable domain logic:** the whole `EvidenceLedger` (game-free).
- **Practical applications:** CI release gates, regression sign-off, readiness checklists.
- **Required abstraction:** a ledger + a status model; already in the core.
- **Security implications:** a security gate must not report ready without the scan evidence.
- **Testing implications:** missing-is-not-a-pass; runner-error vs test-failure.
- **Hardware Store candidate:** YES (stocked as `test-evidence`).

## Adapters (one core, two lives)

- **Game:** `parts/world_cert.py` -- the `certify` verb records evidence for the world's readiness
  checks (NPCs and callings loaded) and reports whether it is certified. Tick-reachable.
- **Practical:** `parts/release_gate.py` -- a `ReleaseGate` expects lint/tests/coverage/security
  evidence and is ready only when all have PASSED; a step that never ran blocks the release.

## Evidence

- Tests: `tests/test_test_evidence.py` (unit + property), `tests/test_world_cert.py` (game + tick),
  `tests/test_release_gate.py` (practical + a one-core proof).
- Manifest: `docs/hardware/test-evidence.yaml`. Trace it: `make loop PART=test-evidence`.
- **Maturity: `beta`** -- demonstrated in two contexts and tested, but not `stable` (no timestamps,
  artifact hashes, or JUnit ingestion yet).

## Deferred (needs Josh's approval)

Timestamps, artifact hashes, and a JUnit/coverage ingester are later slices.
