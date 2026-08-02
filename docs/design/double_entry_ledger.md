# Design doc: a double-entry ledger for CodeForge

*A reimplementation of the publicly documented architecture of TigerBeetle (a purpose-built
double-entry accounting database) and Stripe's idempotency-key model, built to study
correctness-under-retry for money movement. It is not affiliated with or endorsed by either
project. No code was copied; the schema and semantics are reconstructed from public documentation.*

Status: **implemented** (the part and its tests ship; product integration is deferred, below)
Author: Josh (architecture + acceptance); AI-assisted implementation, human-reviewed and tested
Part: `kernel/ledger.py` (MOD-10.048) · Consumes: `kernel/shelf/idempotency.py` (MOD-05.069)

## Context and problem

CodeForge's game economy is **single-entry**: a character's coins are one persisted integer
(`parts/world/coinage.py`), mutated by a delta at each sink or source
(`parts/world/character_store.py`). Single-entry is simple and it is what the game needs today, but
it has a structural weakness a hiring manager recognizes instantly: **nothing enforces that money is
conserved.** A bug that adds coins on one side without subtracting on the other silently mints
currency; a crash between the two halves of a trade silently destroys it. The books can drift, and
there is no invariant that says they cannot.

This is the single most legible correctness problem in software: money that must be conserved,
under retries and partial failures. It is worth building the right structure for it as a
self-contained, testable part, whether or not it ever replaces the game's simple economy.

## Goals

1. **Conservation by construction.** Across the whole ledger, total debits always equal total
   credits, after any sequence of transfers. Not "checked and hopefully true" - *true because a
   transfer cannot post one side without the equal other side.*
2. **An immutable audit trail.** Every posting is an append-only record; corrections are new,
   compensating transfers, never edits.
3. **Retry-safety (exactly-once effect).** A network retry, a double-click, or an at-least-once
   redelivery must never apply a transfer twice.
4. **Fail-loud validation before any mutation.** A refused transfer leaves the ledger exactly as it
   was - no half-applied state.
5. **Reusable and inspectable** through the Hardware Store, independent of the game.

## Non-goals

- **Durability / persistence.** The v1 part is in-memory. Wiring it to a transactional store is
  designed here but deliberately out of scope for the part (see 100x scale).
- **Replacing the game economy.** The part does not touch `coinage.py`. Integration is a separate,
  human-approved decision (below).
- **Multi-currency, FX, interest, account hierarchies.** Out of scope for the smallest useful version.
- **Being a bank.** This models *value conservation*, not regulatory financial services.

## The design

Two record types and one invariant.

- **Account** - an id, two running totals (`debits_posted`, `credits_posted`), and optional guard
  flags. The ledger is neutral about account *type*: it tracks both sides and lets the caller
  interpret the sign of `balance = debits_posted - credits_posted` (an asset account reads that
  directly; a liability reads its negation). This neutrality is TigerBeetle's model and it is why
  the same ledger serves a game wallet, an AP subledger, or a benefit-disbursement account.
- **Transfer** - an immutable (frozen) record: `amount` moved from a debit account to a credit
  account, under a unique transfer id. Posted transfers are history; they never change.
- **The invariant** - `post_transfer` adds `amount` to the debit account's debits **and** the same
  `amount` to the credit account's credits, in one operation. There is no code path that moves one
  side without the other. Therefore `sum(debits) == sum(credits)` is a structural property, not a
  runtime hope. `assert_balanced()` exists only as a defensive check for tests and reconciliation.

Amounts are **non-negative integers in the smallest unit** (never floats - money is not a float, a
detail that separates a real ledger from a toy). This composes directly with the game's integer
coinage (cinder minor units).

### Exactly-once: two mechanisms, two jobs

The catalog conflates them, so this design keeps them distinct:

- **Unique transfer id** (TigerBeetle) - the durable identity of a *posting*. Re-posting the same id
  is refused. This protects the ledger's own integrity.
- **Idempotency key** (Stripe) - the *client's* retry token. `post_transfer(..., idempotency_key=k)`
  runs the post at most once for `k` and replays the original transfer on retry, without moving any
  balance again. A key reused for a *different* request (a changed fingerprint) is refused. This
  protects the client from its own retries.

They compose: the idempotency key stops the retry before it reaches the ledger; the unique transfer
id is the backstop if a caller retries without a key.

## Alternatives considered

1. **Keep single-entry balance mutation (status quo).** *Rejected as the correctness model, retained
   as the game's current economy.* Simplest, but no conservation invariant; every sink/source is an
   independent chance to mint or destroy currency. Acceptable for a game where the stakes are low;
   unacceptable as a portfolio demonstration of financial-grade correctness.
2. **Adopt TigerBeetle itself.** *Rejected for now.* It is the right tool at scale (1M transfers/sec,
   a purpose-built database), but it is a separate process and a heavy dependency for a single-process
   game engine that is deliberately frameless. Studying its published model and reimplementing the
   invariant in-process is the better fit and the better learning. Revisit if the economy ever needs
   real throughput and durability.
3. **A Postgres subledger now** (a `transfers` table with a UNIQUE id, two balance updates and the
   insert in one transaction). *Deferred, not rejected* - this is exactly the 100x design below. It is
   the right durable implementation, but building it now would couple the part to the database and a
   migration before there is a consumer that needs durability. The in-memory core proves the model
   first; the same public contract fronts the durable store later.
4. **Event-sourcing (the balance is a fold over an event log).** *Rejected as over-engineering here.*
   The append-only transfer log already *is* the event log for this domain; a separate
   event-sourcing framework adds machinery without a need the ledger doesn't already meet.

## Consequences

**Positive:** a conservation invariant that cannot drift; an immutable, reconcilable audit trail;
retry-safety; a reusable finance part with cross-domain reach (game, payments, gov disbursement);
and a genuinely legible portfolio artifact with a property-based correctness proof.

**Negative (named honestly):**
- **Two sources of truth if integrated naively.** If the ledger becomes an audit *mirror* of the
  single-entry economy, the coin scalar and the ledger can disagree; something must reconcile them,
  or the ledger must become *the* source of truth (a bigger change). This is the real cost and the
  reason integration is gated.
- **In-memory v1 is not durable.** A restart loses the ledger. It is correct, not persistent - stated
  plainly, not hidden.
- **No cross-process atomicity.** The single-process, single-threaded model needs no lock; a networked
  deployment does, and that is not in the part.
- **More ceremony than single-entry.** Every movement is two postings and a transfer id. That is the
  price of the invariant; for a low-stakes game it may be more than the game needs, which is exactly
  why integration is a judgment call, not automatic.

## Failure modes

- **The deliberately-induced double-spend.** A client posts a transfer, never hears back, and retries.
  *Mitigation:* the idempotency key replays the original transfer; money moves once. Pinned by
  `test_idempotent_retry_does_not_double_spend` and the Hypothesis property
  `test_idempotent_retries_apply_exactly_once` (any number of retries -> exactly one application).
- **Overdraft.** A guarded wallet (`debits_must_not_exceed_credits`) is spent past its balance.
  *Mitigation:* refused before any balance moves; pinned by `test_overdraft_on_guarded_account_refused`.
- **A partial post on crash** (the classic single-entry failure). *In v1:* the two postings happen in
  one synchronous call with no `await` between them, so there is no interleaving point; the risk
  appears only with a durable store, where *the answer is a database transaction* (below).
- **Out-of-band corruption.** A bug mutates a posted total directly. *Mitigation:* `assert_balanced()`
  as a reconciliation check catches it; pinned by `test_assert_balanced_catches_a_corrupted_book`.

## Security and the PCI scope boundary

This ledger moves an abstract integer quantity. It stores **no** cardholder data, no PAN, no
credentials - so it is **outside PCI-DSS scope** by construction. That boundary is deliberate and
worth stating: a real payments deployment keeps the ledger (amounts, account ids, transfer ids) in
scope for integrity and audit, but pushes card data to a tokenizing processor (e.g. Stripe) so the
ledger never touches it. Amounts are integers (no float rounding to exploit); transfer ids and
idempotency keys are opaque strings; all validation is fail-loud before mutation.

## Testing strategy

- **Unit** (`tests/test_ledger.py`, runs in `make check`): happy path, the double posting, the
  append-only log, balance math, the idempotent retry, and every refusal (unknown account,
  non-positive/non-integer amount, self-transfer, duplicate id, overdraft, blank ids, immutability).
- **Property** (`tests/test_ledger_properties.py`, `make property`, Hypothesis): across hundreds of
  generated transfer sequences - including refused ones - `total_debits() == total_credits()` holds
  after *every* step; and a transfer replayed under one key any number of times applies exactly once.
  This is the correctness-under-adversity evidence a double-entry ledger exists to provide.

## What I would do differently at 100x scale

- **A transactional store is the durability answer.** The transfer log becomes an `INSERT` with a
  UNIQUE constraint on the transfer id; the two balance updates and the insert commit in **one
  database transaction**, so a crash can never leave a half-posted transfer (the partial-post failure
  mode disappears). The idempotency key becomes a UNIQUE-indexed row; check-run-store becomes an
  upsert or a `SELECT ... FOR UPDATE`, making it atomic across processes.
- **Hot-account contention.** A single "house" account every transfer touches becomes the bottleneck
  (row-lock contention). The fix is TigerBeetle's: batch transfers, and/or shard the hot account into
  sub-accounts reconciled periodically.
- **Two-phase transfers.** Real ledgers need pending/void (authorize then capture). TigerBeetle's
  `pending` transfer flag is the model; add it when a consumer needs holds.
- **A reconciliation job.** A scheduled `assert_balanced()` over the durable store, filing a Chronicle
  incident on any drift - defense in depth even though the invariant is structural.
- **Throughput.** If the game economy ever needed real volume, this is where adopting TigerBeetle
  itself (alternative 2) stops being over-engineering and becomes the right call.

## Integration decision (a keel junction - deferred for Josh)

The part is **not** wired into the game's canonical economy. Three options, none taken without Josh:

1. **Audit mirror** - the ledger shadows every coin movement as a second, provable record; the coin
   scalar stays the source of truth. Lowest risk; cost is the reconciliation burden (a second source
   of truth).
2. **System of record** - the ledger *becomes* the economy; `coinage.py` derives balances from it.
   Highest value, but it is a **persistence-model change and a data migration** - an explicit approval
   gate under the project's architecture rules.
3. **Standalone portfolio vessel** - keep the ledger as a self-contained demonstration + this design
   doc, and leave the game economy as-is. Lowest risk, still full portfolio value.

Recommendation: ship as (3) now (done); offer (1) as the next reversible slice if Josh wants the
ledger exercised against real game events. (2) waits for an explicit decision.

## Provenance

Original implementation. The double-entry account/transfer schema and the
`debits_must_not_exceed_credits` account guard are the publicly documented TigerBeetle model; the
idempotency-key retry semantics are the publicly documented Stripe model (`Idempotency-Key` header,
response keyed by (account, key), mismatched body under a reused key rejected). No code was copied.
This is a reimplementation built to study those patterns, not affiliated with or endorsed by
TigerBeetle or Stripe.
