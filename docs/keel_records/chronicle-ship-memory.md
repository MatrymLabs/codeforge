# Keel Record: The Chronicle (the ship's memory)

*Human Keel Record (see [../human_keel_doctrine.md](../human_keel_doctrine.md)). This documents a
critical-junction design decision and its first build slice. Per the doctrine, AI proposes and
Josh approves; **AI does not assign ownership**. The level-4 ownership claim and the "what I
learned" reflection below are left for Josh to complete when he can defend the design to an
interviewer.*

- **Build:** the Chronicle, an append-only, content-hashed record store (`parts/chronicle.py`)
- **Ownership level claimed:** *(pending Josh's own claim; undeclared until he defends it)*

## Intent
Give CodeForge an engine of *memory* to match its engine of *now*. The tick (`handle_command`)
computes and renders the present, then discards it; the Chronicle retains a small, tamper-evident
record the ship can read back to answer "how did we get here, is it getting better, can we prove
it?" One core mechanism (a hash-chained ledger) with typed record kinds, so trend series, incident
registers, eval memory, and provenance are record types rather than four bespoke systems.

## Problem
The ship produces evidence (gate verdicts, benchmarks, security bundles) but git-ignores most of
it, so ARC's `change`/`patch`/`release`/`evidence` dimensions are honestly MISSING and there is no
retained answer to "is it getting better." Naively, this invites four separate stores. The problem
was to add retained engineering-memory as **one** small, honest, reversible mechanism.

## Constraints
- Append-only and tamper-evident: a past record cannot be silently edited (hash chain, fail loud).
- Retained, not git-ignored, and reproducible from the cited commit.
- Frameless / stdlib-first (JSONL), diffable; no database in slice 1 (the ship already has SQLite
  for world state; revisit only if volume demands, on evidence).
- Architecture laws honored: the Chronicle is canonical engineering-state, read-only projections
  never mutate it, and it never bypasses the tick for world state.
- Critical-junction rule: a new persistence layer stops for a keel decision before any code.

## Decision
Approved slice 1, then split its delivery for reviewability:
- **Slice 1a (this build):** the append-only hash-chained core + the `evidence` kind + a loud
  validator + a read-only `chronicle` verb, filed in the Classification Registry, with `arc_ledger`
  additively retaining its evidence verdict in the Chronicle (non-breaking).
- **Slice 1b (next PR):** ARC's `evidence` dimension reads the retained Chronicle record instead of
  the git-ignored `arc-evidence/` verdict.
Splitting keeps each PR small and reversible (the design's own "ship in reviewable slices" ethos);
it is strictly more conservative than the bundled scope and was surfaced to Josh.

## Alternatives considered
- **Keep git-ignoring evidence.** Rejected: leaves ARC's evidence dimension permanently MISSING and
  answers no trend question.
- **A real database (SQLite/Postgres) now.** Rejected for slice 1: a git-tracked JSONL store stays
  diffable, reproducible, and frameless-first; escalate only on measured volume.
- **Four separate stores (trend DB, incident DB, eval store, provenance graph).** Rejected: that is
  the duplication the ship's ethos warns against. One core mechanism, many record kinds.
- **Bundle the ARC read migration into one PR.** Rejected in favor of the 1a/1b split for a smaller
  review surface and a non-breaking first step.

## AI contribution
AI-assisted implementation of `parts/chronicle.py` (Record, `append`/`read`/`read_latest`, the
`_digest` hash chain, the loud validator, the `chronicle` verb and `render`), the test twin
(`tests/test_chronicle.py`, acceptance + hostile refusal incl. tamper and reordering), the
additive `arc_ledger.emit` retention, the registry filings, and this record. Design proposed in
`docs/reports/2026-07-13-chronicle-design.md`.

## Human modification (the keel)
Josh chose this build from the staged options, approved the slice-1 scope, and holds the keel
decisions: whether a retained engineering-memory layer belongs in the architecture, that evidence
should move from git-ignored to retained, and the acceptance bar. The 1a/1b split was proposed and
surfaced for his call.

## Tests / evidence
- `parts/chronicle.py` + `tests/test_chronicle.py` (17 tests: round-trip, hash-chain linking,
  read_latest, empty-store, render, and hostile refusals - tampered payload, reordered chain,
  malformed line, missing field, unknown kind - plus the emit-retention and engine-tick reachability
  tests). Green on `make check`.
- Registry filings `MOD-UM10-S01-N001-029-R0` + `CMD-UM10-S01-N001-023-R0`; `make readiness` CLEAN.
- Additive `arc_ledger.emit` retention verified by `test_emit_retains_its_evidence_verdict_in_the_chronicle`.
- Retained store scaffolded at `chronicle/` (git-tracked, with a README).

## What Josh learned
*(For Josh to complete - the doctrine requires a human act beyond approval before a level-4 claim:
explain the hash-chain integrity model, trace a record from `append` to the `chronicle` verb, or
name the failure mode the tamper test guards.)*

## Final decision
Josh's, at the merge junction of slice 1a and of this record. The level-4 ownership claim is his to
make on the Career Board when he can defend the design; AI leaves it undeclared here.

## Uncertainty / review point
Slice 1a intentionally leaves ARC still reading `arc-evidence/` (the Chronicle write is additive);
slice 1b flips the read. Revisit the JSONL-vs-database decision only if record volume is measured to
demand it. The retention schedule (bounding growth, honoring holds) is a later slice, not yet built.
