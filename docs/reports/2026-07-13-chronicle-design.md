# Design for Sign-Off: The Chronicle (the ship's memory)

- **Date:** 2026-07-13 (day 194)
- **Status:** DESIGN - awaiting Josh's sign-off. No code written. This is a
  critical-junction proposal (it touches core architecture and adds a persistence layer),
  so per the human-keel doctrine it stops here for a keel decision.
- **Origin:** the keystone of the Lemonade board review
  (`2026-07-13-lemonade-board-review.md`, section 12).

## Problem (one sentence)

CodeForge has a `tick` (an engine of *now*, `handle_command`) but no engine of *memory*:
it computes and renders the present moment, then discards it, so it cannot answer "how did
we get here, is it getting better, and can we prove it?"

## Proposal

Build **the Chronicle**: a small, retained, append-only, hashed, linked record store that
the ship reads *back*. It is the symmetric twin of the tick. One core mechanism (an
append-only, content-addressed ledger) with **typed records**:

- **evidence** - a retained, hashed evidence bundle (what the security/ARC gates produce),
  keyed by commit, instead of git-ignoring it.
- **metric** - a metric point `{name, value, commit, stamp}` (the Six Sigma trend series).
- **incident** - a FRACAS record (the safety register; a `change_ledger` re-skin).
- **ai-eval** - a scored AI-output evaluation (the MLOps eval-regression memory).
- **edge** - a provenance edge `{from, relation, to}` linking blueprint to part to test to
  evidence to verdict to change to release (PROV-O `wasGeneratedBy` / `wasDerivedFrom` /
  `wasAttributedTo`).

ARC reads Chronicle records the same way it already reads `arc-evidence/` (via
`arc_ledger.read_latest`); `forge-audit` reads them for a trend/outcome axis.

## Why this is the keystone (what one build unlocks)

- Gives `change_ledger` / `release_gate` / an incident-register their missing persistence.
- Flips ARC's `change` / `patch` / `release` / `evidence` dimensions from honestly-MISSING
  to actually-filed - finishing the "Complete the Ten" ARC work deferred earlier this day.
- Hosts trend-series (Six Sigma) and eval-regression memory (MLOps) as record types, not
  bespoke systems.
- Retains evidence instead of git-ignoring it (records + safety).
- Is the research's #1 ask (provenance as core infrastructure) and #3 (cross-artifact
  integration) in one move.

## Architecture-law compliance

1. **State is canonical; text is a projection.** The Chronicle IS canonical state (a filed
   record store). Renderers/ARC read it; they never mutate it. A record, once written, is
   append-only and hashed - immutable by construction.
2. **The engine tick is the only door for game state.** The Chronicle is engineering-state,
   not world-state; it is written by gates/tools (like `arc_ledger`), read by ARC. It does
   not bypass `handle_command` for world mutation.
3. **Reproducible from the recorded commit.** Every record carries a commit + content hash.
4. **Fail loud.** A malformed record fails loud on read (as `arc_ledger.VerdictError` does).

## The smallest useful first slice (what I would build first, on approval)

**Slice 1 - the append-only hashed core + one record type (evidence), read by ARC.**

- `parts/chronicle.py`: a `Record` (kind, payload, commit, stamp, content-hash, optional
  prior-hash link), `append(record)`, `read(kind, filter)`, a loud validator, a stdlib-only
  JSONL store under a retained (NOT git-ignored) `chronicle/` dir, dated + hashed.
- Migrate the existing `arc_ledger` evidence to write through the Chronicle (evidence
  becomes a Chronicle record kind), and retain it (stop git-ignoring that one path) so ARC
  reads retained, cited evidence.
- Test twin: acceptance (append then read round-trips; hash chains; newest wins) + refusal
  (malformed record fails loud; a tampered hash is detected).
- Filed in the Classification Registry; a `chronicle` verb (read-only view) tick-reachable.

Then, in later approved slices: **metric** (trend series + `make trend`), **incident**
(FRACAS from `change_ledger`), **ai-eval** (point the bake-off at the LLM), **edge**
(provenance graph), and a **retention_schedule** governing disposition.

## Security (dogfooding the new Blueprint security schema)

- **Threat model:** the adversary is a tampered or fabricated record (a false "evidence"
  claiming a gate passed), or unbounded growth. The Chronicle is local, offline, written
  only by trusted in-repo gates/tools; there is no network trust boundary.
- **Trust boundaries:** records are written only through the validated `append()` gate;
  each record is content-hashed and optionally hash-chained to its predecessor, so tampering
  is detectable on read. The Chronicle never executes a record; it stores and returns data.
- **AuthN/AuthZ:** reads are a projection (not rank-gated); any future purge/disposition
  action is owner-gated and refuses to act under an active retention hold (Federal Rule #10).
- **Failure modes:** a malformed/partial record fails loud (never a silent pass); a broken
  hash chain is reported, not ignored; an absent store reads as empty, not an error;
  unbounded growth is bounded by the retention schedule (a later slice).
- **Data classification:** engineering metadata only (verdicts, metrics, hashes, commits);
  no secrets or PII (the existing `_redact` discipline applies to any AI-eval payload).

## Alternatives considered

- **Do nothing / keep git-ignoring evidence.** Rejected: leaves the board's #1 gap open and
  keeps ARC's change/patch/release permanently MISSING.
- **A real database (SQLite/Postgres).** Rejected for slice 1: the ship already has SQLite
  for world state; a git-tracked JSONL store keeps the Chronicle diffable, reproducible, and
  frameless-first. Revisit only if volume demands it (evidence supports, not intuition).
- **Five separate systems (trend store, incident DB, eval store, provenance graph).**
  Rejected: that is the duplication the ship's ethos warns against. One core, many record
  types is the harvest-not-rebuild pattern.

## Risks, rollback, cost

- **Risk:** a new persistence layer is architecture surface. Mitigated by making slice 1
  tiny (one record type, stdlib JSONL, read-only ARC integration) and reversible.
- **Rollback:** the Chronicle is additive; deleting `parts/chronicle.py` + the `chronicle/`
  dir reverts ARC to reading `arc-evidence/` as today. No world-state migration.
- **Cost:** slice 1 is a bounded part + test twin + one ARC read path, comparable to the
  `arc_ledger` slice already shipped this session.

## The keel question for Josh

This adds the ship's first retained engineering-memory layer and changes how ARC sources
evidence (from git-ignored to retained). That is a Frame-level decision (shared: AI
proposes, Josh approves). **Approve the slice-1 scope above, adjust it, or redirect** before
any code is written. A level-4 keel record should accompany the build.
