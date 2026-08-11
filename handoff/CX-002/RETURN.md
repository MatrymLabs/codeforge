# RETURN CX-002

```yaml
packet_id:    CX-002
title:        Leg 1E, a reward is granted exactly once and survives a restart
worked_by:    Claude Code
note:         Codex had not started. No ledger, no tests, no RETURN, his tree clean on main.
              Taken on founder instruction, not claimed off him mid-work.
status:       complete_awaiting_founder_merge
verdict:      the packet's question is answered NO, and the ledger now proves it
```

## The packet's question, answered first

> **If the same defeat is processed twice across a restart, a reconnect, or a retry, does the
> player get paid twice?**

**No.** Measured before writing a line of the ledger, on a live server:

```
kill a barrow-rat        XP 824 -> 844,  purse 2 -> 4 cinders
--- process killed, port confirmed clear, new process, same DB ---
reconnect                XP 844,         purse 4 cinders
```

So this is the packet's second branch: *"If the answer is already no, the deliverable is the
LEDGER AND ITS TEST proving it, not a repair."* Nothing was repaired. What existed was an
undocumented, untested property that happened to hold, and would have gone on holding only until
somebody added a replay path.

## What was built

`kernel/world/reward_ledger.py` (MOD-04.160), a durable record keyed on the packet's data
contract `(character, source, occurrence)`, plus `RewardGrantRow` in `db.py` and the guard at the
defeat seam in `combat.py`.

## The design decision the packet left open, and why it matters

The packet fixed the identity but not where `occurrence` comes from. The obvious answer is the
world beat, and **it is a trap that fails in the dangerous direction.**

`climate.now()` documents itself as *"a fresh boot starts at 0"* and is not persisted. Minting the
occurrence from the beat means that after a restart it rewinds, so a legitimate second kill reuses
an occurrence already on disk, the ledger refuses the claim, and the player is **robbed of a
payout they earned**. That is worse than paying twice: a double payment is a visible economy bug,
a refused payment looks like the game simply not working.

So the occurrence is minted from the durable record itself (`next_occurrence`), which is monotonic
across restarts by construction. Pinned by
`test_the_occurrence_does_not_rewind_when_a_fresh_process_starts`.

## Claim, not check-then-pay

Check-then-pay does not hold across processes: two can both read "not granted" and both pay. So
the claim IS the insert (`claim_grant`), and the table's primary key picks the winner atomically.
The loser is told to pay nothing. `record_grant` remains the plain idempotent write the packet's
tests specify.

One deliberate detail at the seam: a defeat that pays nothing must still **fell the foe**. Only
the awards sit behind the claim, never the death itself.

## Verification, this session

```
make check                                   exit 0, 5154 passed, 43 skipped
tests/test_reward_ledger.py                  24 passed
  - the packet's 7 contract tests, verbatim and unmodified
  - 17 added; no locked assertion weakened, deleted or rewritten
```

**The training dummy is still farmable.** Driven live on first-forge, three kills:

```
KILL 1  You strike the training dummy for 14. (critical!) It collapses -- then reassembles itself.
        You gain 30 XP.  You gain 30 JP.  You gain 30 TP.  You find 3 cinders. (purse: 3 cinders)
KILL 2  ... You find 3 cinders. (purse: 6 cinders)
KILL 3  ... You find 3 cinders. (purse: 9 cinders)

payouts recorded: 3 of 3 kills
```

**And still farmable ACROSS a restart**, which is the case a beat-based occurrence would have
broken:

```
--- server killed, port confirmed clear, new process, same DB ---
purse on reconnect      9 cinders
KILL 4                  You find 3 cinders. (purse: 12 cinders)

ledger:  ('farmer','npc:training_dummy',1) (…,2) (…,3) (…,4)
```

Occurrence **4**, not a reused 1. The record did not rewind.

## EXTRACTION

```yaml
store_search_result: |
  SEARCHED, both tiers, in ADR-0005 order.
  Certified Tier (hardware-store/catalog, 6 parts): no idempotency record. "idempotency",
  "exactly once", "dedup" all returned nothing; "ledger" hit budget-gate and "retry" hit
  circuit-breaker, neither of which is this capability.
  Working Shelf (codeforge/catalog/parts.yaml, 104 parts): 9 entries mention
  idempotency/exactly-once/dedup. One is a direct hit: `Idempotency Key Store`
  (id: idempotency-key, kernel/shelf/idempotency.py) - "Run an operation at most once per
  idempotency key and replay its stored result on retry."

parts_consumed: |
  NONE, and the reason is in the part's own card: "Traded away (v1): durability and
  cross-process atomicity, keeping a pure single-process core." Durability across a process
  boundary is this packet's entire requirement, so the part is the right SHAPE with the one
  guarantee removed that we needed. Consuming it would have satisfied consume-first on paper
  and failed the invariant.

extraction_signal: |
  STRONG, and it is the same capability twice. The shelf part's own `experimental` field
  already names this exact next step: "back it with a durable UNIQUE-indexed table + row lock
  or upsert for atomic check-run-store across processes". reward_ledger is that sentence,
  implemented. Two implementations of one idea now exist in the same repo, which is the pull
  rule's second occurrence. They should converge: either reward_ledger becomes the durable
  backend of the shelf part, or the shelf part is superseded by it. NOT done here:
  kernel/shelf/idempotency.py is outside this packet's allowlist, and rewriting a shelf part
  during a game packet is how a scoped change becomes an unscoped one.

pattern_shapes: |
  1. "The obvious id source rewinds." The beat trap here is the same shape as the fleet's
     recall UTC split-brain: a value that looks monotonic within one process and is not across
     a boundary. Worth a screen wherever an id is minted.
  2. "Check-then-act across processes." Resolved the same way here as a DB unique constraint
     resolves a double-submit. This is the third place in the fleet reaching for it
     (saas-starter, recall, now codeforge), which is a certification signal, not just reuse.
  3. "A guard that can rob the user." The failure mode worth naming: an exactly-once guard's
     dangerous direction is UNDER-paying, not over-paying, because under-paying is silent.
```

## DISSENT

**One, against my own packet.** CX-002's `EXTRACTION CONTEXT` asserted *"parts_to_consume: None
identified. The Store holds 6 parts, none of them an idempotency record."* That is true of the
Certified Tier and false of the reuse surface. The Working Shelf holds a direct hit. I wrote that
dispatch **after** writing ADR-0005, which exists precisely to stop one tier being mistaken for
the whole picture, and then made the error the ADR describes. Doctrine that has been written down
is not yet doctrine that has been absorbed. C-2 (make `packet_gate` refuse a dispatch whose
consume-first log shows only one tier) would have caught this before dispatch, and is still open.

**Two, on the packet's own test technique.** The verbatim contract test calls
`importlib.reload(reward_ledger)`, which replaces the module's classes with new objects. Any later
test in the file that caught `GrantIdentityError` by its imported name silently stopped matching
the error it had just provoked. The locked assertions are fine; the hazard is for anything added
after them. Recorded so the next packet that reaches for `reload` as a stand-in for "a fresh
process" knows what it costs.

## NOT DONE, deliberately

- `kernel/shelf/idempotency.py` convergence. Outside the allowlist. See the extraction signal.
- The in-memory race described in the dispatch. It works. Left alone as instructed.
- Any change to `items.py`, `forge.py` inventory rendering, or `abilities.py`. Out of scope.

## Rollback

`git revert` the merge commit. The ledger is new; `combat.py`'s only edit is the guard, and
removing it restores the previous behaviour exactly.
