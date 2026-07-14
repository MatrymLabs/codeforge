# Design for Sign-Off: Chronicle Retention (disposition, not deletion)

- **Date:** 2026-07-14 (day 195)
- **Status:** DESIGN - awaiting Josh's sign-off. No code written. This is a critical-junction
  proposal (it touches the Chronicle's core append-only guarantee and adds a governed
  disposition capability), so per the human-keel doctrine it stops here for a keel decision.
- **Origin:** the last unbuilt Chronicle record kind, deferred from the Chronicle design
  (`2026-07-13-chronicle-design.md`) as "a retention schedule governing disposition."

## Problem (one sentence)

The Chronicle grows without bound and has no honest, hold-aware way to age records out, but it
is **append-only and hash-chained**, so naively deleting an expired record would break the chain
and destroy the tamper-evidence the whole store exists to provide.

## The core tension (read this first)

Every Chronicle record carries a `content_hash` over its own fields **and the prior record's
hash**. That chain is the Chronicle's one real guarantee: edit or remove a past record and the
chain breaks loudly on read. Retention wants the opposite: remove records a schedule says are
past their life. These two cannot both be true for the same bytes. **The design question is not
"how do we delete safely" but "what does retention mean for an evidence ledger that must not
lie about its own past."**

Two federal rules from the ship's contract bind the answer:

- **Rule #10 - never delete a record because a calendar says so.** First check, in order:
  contract terms, FAR Subpart 4.7, NARA schedule, litigation hold, audit hold, CUI handling,
  tax/payroll retention. **Any hold wins.** A retention period is a *default for review*, never
  an auto-trigger.
- **Never claim certification.** This is records-*readiness* tooling; it never asserts a legal
  disposition authority.

## Proposal: disposition as an append-only overlay, not a delete

Retention is a **governance overlay that reads the Chronicle and appends to it** - it never
mutates or removes an existing record. Three pieces:

1. **A retention policy (data, not code).** A small table mapping a record `kind` (and optionally
   a subject prefix) to a default retention period and a category. Loaded and validated like the
   seed loader; a malformed row fails loud. The period is advisory: it makes a record *eligible
   for review*, nothing more.
2. **A hold registry.** Active holds (litigation, audit, contract, CUI, ...), each with a scope
   (all, a kind, a subject) and a reason. Any hold matching a record blocks its disposition,
   full stop (rule #10: any hold wins).
3. **A disposition action (owner-gated).** `dispose()` proposes the records that are BOTH past
   their retention period AND matched by no hold, and - only on an explicit, owner-authorized
   run - appends a **`disposition` record** (a new Chronicle kind) marking each as dispositioned
   `{target_hash, policy, category, decided_by, decided_utc}`. The original record stays in the
   ledger, hash-chain intact; reads simply treat a record with a later `disposition` marker as
   *inactive* (filtered by default, still present and provable).

**The store never shrinks, and it never lies.** "Disposition" here means "we recorded, under
authority and with no hold blocking, that this record has reached end-of-active-life" - itself a
dated, hashed, evidenced event. That is what a records system should do; physical destruction is
a separate, higher-bar action (see Alternatives).

## The smallest useful first slice (what I would build first, on approval)

**Slice R1 - the retention overlay, read-only + a dry-run, no destruction.**

- `parts/retention.py`: load + validate a retention policy and a hold registry (stdlib/YAML,
  fail-loud); `eligible(records, today)` returns records past retention; `held(record)` returns
  the blocking hold or None; `dispose(..., dry_run=True)` returns the disposition *plan* without
  writing anything.
- A `retention doctor` (mirrors `library doctor`): shows, honestly, what is eligible, what is
  held (and why), and what has already been dispositioned. It shouts, never hides.
- **No disposition record is written and nothing is removed in R1.** R1 is pure analysis: it
  makes retention *visible* and *auditable* first.

Then, in later separately-approved slices: **R2** the owner-gated real `dispose()` that appends
`disposition` markers (still no physical delete); **R3** growth metrics + a `retention` trend so
the need for physical compaction is *measured, not assumed*; **R4** (only if R3 shows real
pressure) a segmented cold-archive with a checkpoint hash - the sole path that ever moves bytes,
and only behind its own keel decision.

## Federal rule #10 alignment (the hold hierarchy is the point)

`dispose()` refuses to act on any record for which `held()` returns a hold, and the doctor
surfaces the hold and its reason. The retention *period* only ever moves a record from "active"
to "eligible for review" - a human (owner) decides, holds override, and the decision is recorded.
No calendar ever deletes anything on its own.

## Architecture-law compliance

1. **State is canonical; text is a projection.** The ledger stays canonical and immutable;
   retention *reads* it and *appends* governed markers. Renderers/doctor never mutate.
2. **Reproducible.** Every `disposition` marker carries the commit and a content hash, like every
   Chronicle record.
3. **Fail loud.** A malformed policy/hold row fails loud on load; a `dispose()` run under an
   active hold refuses loudly rather than acting.
4. **Authorization before capability.** Real disposition (R2+) is owner-gated, exactly as HTTP
   admin mutations are; R1 is read-only and needs no gate.

## Alternatives considered

- **A. Disposition overlay, never physically delete (RECOMMENDED for R1-R2).** Preserves the
  hash chain completely; matches the honest records model; hold-aware and reversible. Cost: the
  store does not physically shrink (bounds *logical* growth, not bytes). Best first move.
- **B. Compact-and-re-chain (physical delete + rebuild).** Actually reclaims bytes, but destroys
  tamper-continuity across the compaction boundary - you can no longer prove the removed records
  were not altered before removal. Would require a checkpoint record (hash of the removed
  segment) as a receipt. Rejected for now: it trades the Chronicle's core guarantee for storage
  the ship has not measured a need for. Revisit only under R4, on evidence.
- **C. Segment/rotate the ledger by period, archive whole segments.** Middle ground: bounds the
  active ledger's size, keeps segment-level checkpoint hashes. More machinery than R1 needs;
  folded into R4 if measurement demands it.
- **D. Do nothing.** Rejected: the design already named unbounded growth as a real risk, and an
  evidence store with no disposition story is not records-ready. But note R1 alone (visibility +
  dry-run) already closes most of the honesty gap without any destructive capability.

## Security

- **Threat model:** the adversary is a *premature or unauthorized disposition* (aging out
  evidence that a hold protects, or that an assessor still needs), and *tampering with a
  disposition marker* to hide that a record was retired. Growth-as-denial is a lesser concern.
- **Trust boundaries:** disposition markers are written only through the validated `dispose()`
  gate, owner-authorized, and are themselves hash-chained (a forged or altered marker breaks the
  chain on read). `dispose()` reads the hold registry first and refuses under any match.
- **AuthN/AuthZ:** R1 is read-only (no gate). R2+ disposition is owner-gated; there is no path
  that removes bytes without a hold check and an explicit owner action.
- **Failure modes:** malformed policy/hold fails loud; a hold match refuses loudly; an absent
  policy means "nothing is eligible" (safe default), never "dispose everything."
- **Data classification:** engineering metadata only; CUI handling is itself one of the holds
  that blocks disposition.

## Risks, rollback, cost

- **Risk:** adding a disposition capability to an immutable store is a real change to what the
  Chronicle *is*. Mitigated by R1 being **read-only** (visibility + dry-run) and R2 being
  append-only (markers, not deletes). No physical destruction without a later, separate keel
  decision (R4).
- **Rollback:** R1 is additive and inert (delete `parts/retention.py` and the policy files).
  R2 markers are append-only records; "un-dispositioning" is just not writing (or a later
  reinstatement marker). No data is ever lost to roll back *from*.
- **Cost:** R1 is a bounded part + test twin + a doctor view, comparable to a Chronicle slice.

## The keel question for Josh

Three decisions, in order of how much they cost you to answer:

1. **Does retention mean *disposition* (mark end-of-active-life, keep the bytes and the chain) or
   eventual *destruction* (reclaim bytes)?** My recommendation: disposition (A) now; destruction
   (B/C) only later, only on measured storage pressure (R3), and only behind its own keel call.
2. **Approve R1 (read-only visibility + dry-run) as the first slice?** It closes the honesty gap
   with zero destructive capability and is the safest possible first step.
3. **Who is "owner" for disposition (R2+)?** The same owner-account that gates HTTP admin, or a
   distinct records-officer role? (This can wait until R2.)

**Approve the R1 scope, adjust it, or redirect** before any code is written. A level-4 keel
record should accompany the eventual build, and physical-destruction slices (R4) each need their
own sign-off.
