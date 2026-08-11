# DISPATCH CX-002

```yaml
packet_id:            CX-002
title:                Leg 1E, a reward is granted exactly once and survives a restart
stream:               engine
owner:                Codex
reviewer:             Claude Code (re-runs every command independently)
merges:               founder
size:                 medium
flight:               M1 Aethryn Green
leg:                  1E

file_allowlist:
  - kernel/world/reward_ledger.py           # NEW. the grant record. yours to write
  - tests/test_reward_ledger.py             # NEW. contract tests, verbatim from this packet
  - kernel/world/combat.py                  # the grant path only, where a defeat pays out
  - kernel/world/db.py                      # persistence for the ledger, if you need a table
  - registry/designations/modules.json      # the completeness gate WILL demand the new module
  - handoff/CX-002/RETURN.md                # NEW. you are explicitly authorised to create this

contract_tests:       tests/test_reward_ledger.py
contract_test_policy: |
  ASSERTION-LOCKED. Given verbatim below. Create it exactly as written. You may ADD tests; you may
  NOT weaken, delete or rewrite an assertion. If an assertion is wrong, STOP and say so in the
  RETURN with your reasoning. Do not edit it into agreement with your implementation.

return_artifact:      handoff/CX-002/RETURN.md
return_authorisation: |
  EXPLICITLY AUTHORISED. Create it. Required, not optional. Its extraction block may not be blank
  ("none observed" is a valid answer; silence is not).
```

## What is already true, so you do not rebuild it

I drove this leg before writing the packet. Two things ALREADY hold and are not your job:

`CMD` Taking an item twice is refused:

```
> get draught      You take a healing draught.
> get draught      You don't see that here.
```

`CMD` Two players landing simultaneous killing blows produce exactly ONE payout. Racer's blow
collapsed the dummy and took the coin; Rival's landed on the reassembled foe and earned nothing:

```
racer:  You strike the training dummy for 7. It collapses -- then reassembles itself.
        You gain 30 XP. ... You find 3 cinders. (purse: 3 cinders)
rival:  The training dummy collapses -- then reassembles itself.
        You strike the training dummy for 7. (13/20)
```

So the in-memory race is handled. **Do not "fix" it.**

## The gap that is yours

Exactly-once is currently a property of the LIVE object graph, not of anything durable. Nothing on
disk records that a given defeat already paid out. That is fine until a process boundary is
crossed, and the flight's own destination crosses one: leg 1G restarts the services and replays
the slice.

**The question this packet answers: if the same defeat is processed twice across a restart, a
reconnect, or a retry, does the player get paid twice?** Answer it with evidence either way. If
the answer is already no, the deliverable is the LEDGER AND ITS TEST proving it, not a repair.

## Invariant

**A reward is granted at most once per grant identity, and that fact outlives the process.**

Not "the code path only runs once". A retry, a reconnect, or a restart must not be able to pay the
same grant twice, and the record of what was paid must be durable.

Corollary: the ledger is a RECORD, not a lock. It must not become a second source of truth about
what a player owns. The purse remains authoritative; the ledger only answers "was this grant
already applied".

## The data contract, decided here

A grant identity is `(character, source, occurrence)`:

- `character` the recipient
- `source` what paid out, e.g. `npc:training_dummy`
- `occurrence` a monotonic id for THIS payout, so a farmable foe can legitimately pay again

A repeat kill of a respawning dummy is a NEW occurrence and MUST still pay. This is the trap in
the packet: the naive fix (one row per character+source) silently breaks the training dummy, which
is farmable by design. The contract tests pin that.

## The contract tests, verbatim

Create `tests/test_reward_ledger.py` with exactly this content.

```python
"""Test twin for kernel/world/reward_ledger.py -- a reward is paid at most once per grant.

Acceptance: a fresh grant is payable; a repeat OCCURRENCE of the same source is payable, because
a farmable foe legitimately pays again; the ledger records what it paid.

Refusal (fail loud): the SAME grant identity is never payable twice, not after a retry, not after
a reconnect, and not after the process restarts. The record outlives the process.

The trap this file exists to catch: keying the ledger on (character, source) alone makes the
training dummy pay once per lifetime. It is farmable by design. The occurrence is part of identity.
"""

from __future__ import annotations

from kernel.world.reward_ledger import already_granted, record_grant


def test_a_fresh_grant_is_payable() -> None:
    assert not already_granted("hero", "npc:training_dummy", 1)


def test_recording_a_grant_makes_it_unpayable_again() -> None:
    record_grant("hero", "npc:training_dummy", 1)
    assert already_granted("hero", "npc:training_dummy", 1)


def test_a_later_occurrence_of_the_same_source_is_payable() -> None:
    """A farmable foe pays every time it is killed. This is the trap."""
    record_grant("hero", "npc:training_dummy", 1)
    assert not already_granted("hero", "npc:training_dummy", 2)


def test_two_characters_do_not_share_a_grant() -> None:
    record_grant("hero", "npc:training_dummy", 1)
    assert not already_granted("rival", "npc:training_dummy", 1)


def test_two_sources_do_not_share_an_occurrence() -> None:
    record_grant("hero", "npc:training_dummy", 1)
    assert not already_granted("hero", "npc:cinder_wight", 1)


def test_recording_the_same_grant_twice_is_not_an_error() -> None:
    """Idempotent WRITE. A retry that re-records must not raise, or the retry becomes the bug."""
    record_grant("hero", "npc:training_dummy", 1)
    record_grant("hero", "npc:training_dummy", 1)
    assert already_granted("hero", "npc:training_dummy", 1)


def test_the_record_outlives_the_process() -> None:
    """The whole point. In-memory exactly-once is not exactly-once across a restart.

    Reload the module's durable view the way a fresh process would and assert the grant is still
    known. If the ledger is in-memory only, this test cannot pass, which is the intended pressure.
    """
    import importlib

    from kernel.world import reward_ledger

    record_grant("hero", "npc:training_dummy", 99)
    importlib.reload(reward_ledger)
    assert reward_ledger.already_granted("hero", "npc:training_dummy", 99)
```

## Definition of done

```bash
cd /home/josh/Projects/MatrymLabs/codeforge
export PATH="$PWD/.venv/bin:$PATH"
make check
```

- `tests/test_reward_ledger.py` passes as given, unmodified.
- The defeat payout consults the ledger, so a replayed defeat pays once.
- **The training dummy is still farmable.** Drive it: kill it three times, confirm three payouts.
  Paste the transcript in the RETURN. A ledger that breaks the dummy is a worse bug than the one
  it fixes.
- `make check` green.

## Out of scope

- `kernel/world/items.py` and `forge.py`'s inventory rendering. That is CC-004, mine, in flight.
- `kernel/world/abilities.py`. That is CC-003, mine, landed.
- The in-memory race described above. It works; leave it.

## Rollback

`git revert` the merge commit. The ledger is new and nothing else reads it.

## EXTRACTION CONTEXT

```yaml
store_search_result: |
  NOT YET SEARCHED. Run the consume-first search for "idempotency" and "exactly once"
  BEFORE writing the ledger, and log it. You reported earlier that "graph traversal"
  and "bidirectional edge validation" returned nothing catalogued; this is a
  different capability and needs its own logged search.

parts_to_consume: |
  None identified. The Store holds 6 parts, none of them an idempotency record.

watch_for: |
  An idempotency key over (actor, source, occurrence) is a shape the fleet has met
  before: saas-starter and recall both guard repeated operations, and the directive
  names idempotency for item transfer, currency, reward claims, progression, and
  deployment state. If this ledger would work unchanged for any of those, that is
  `generalizable`, and if you have written this shape before in this fleet it is
  `recurrence`. Either is worth more than a clean report.
```
