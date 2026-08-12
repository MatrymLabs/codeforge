# DISPATCH CX-009

```yaml
packet_id:            CX-009
status:               LANDED
title:                The save the player loses is the one nothing verifies
stream:               engine
owner:                Codex
reviewer:             Claude Code (re-runs every command independently)
merges:               founder
size:                 medium
flight:               M2 Engine Real
leg:                  2D
queue_position:       1 of 1 stamped. Your queue is otherwise EMPTY; this is the top of the ladder.

goal: >
  Checksum the durable character record and refuse a record whose checksum does not match, rather
  than reading corruption back as truth. The Seed BACKUP path already verifies its bytes; the
  character SAVE path does not, and that asymmetry is the finding.

named_consumers:
  - codeforge   kernel/world/characters.py   the character record players actually lose
  - ARPG        the same persistence layer under Engine-2D, per D1 (persistence is CORE)

prior_research: >
  rd/RESEARCH_REGISTER.md, PATTERN STUDY 2026-08-12, RD-2026-0119. SNES-era SRAM discipline:
  battery-backed saves carried additive or XOR checksums and were treated as EMPTY when the
  checksum failed. Nintendo-developed carts checksummed SRAM at reset. Learned from documented
  facts; attestation on file that no disassembly was read.

  The pattern is 1991 and the reason is not the storage medium. A save you cannot verify is a save
  you cannot trust, and SQLite does not change that.

preconditions: >
  CHECK: file kernel/world/character_store.py contains class CharacterRecord
  CHECK: file kernel/world/character_store_sql.py contains class SqlCharacterStore
  CHECK: file kernel/world/db.py contains class CharacterRow
  CHECK: file kernel/world/save_integrity.py absent
  CHECK: file Makefile contains db-migrate
  CHECK: file migrations/versions/a2b8f1e6c04d_add_character_coins.py exists
  CHECK: file kernel/world/schema_guard.py contains require_current_schema
  CHECK: file kernel/world/membership_sql.py contains set_account
  CHECK: file kernel/world/character_store_sql.py contains _apply_gameplay

  AMENDED 2026-08-12 after Codex correctly blocked on a false third precondition. Two remain, and
  they are the two the finding actually rests on:
    kernel/world/db.py         checksum / sha256 references: 0
    kernel/seedlab/backup.py   INTACT / CORRUPT / MISSING, sha256 verified
  Confirm both yourself before starting; if either has changed, STOP and report it.

  THE DELETED THIRD PRECONDITION, recorded rather than quietly dropped. It read "every checksum hit
  in kernel/ lives in seedlab artifacts", and it was FALSE: `checksum` appears in 5 files including
  kernel/domains/, and `sha256` in 19 including kernel/chronicle.py and kernel/shelf/. I wrote it
  from a `head -6` truncation and read a cut-off list as a complete one.

  It was also DECORATION. Its job was to dramatise the asymmetry and it was never load-bearing: the
  finding is that the SAVE PATH is unverified, which precondition 1 states exactly. The other hits
  are content addressing, a different job for the same primitive, and their existence neither
  supports nor weakens the case for checksumming a character record.

  A precondition that cannot change the work can only block it. This one did.

verification_command: |
  cd /home/josh/Projects/MatrymLabs/codeforge
  export PATH="$PWD/.venv/bin:$PATH"
  make check

definition_of_done: >
  a character record carries a checksum over its own durable fields; restoring a record whose
  checksum does not match REFUSES with a verdict word rather than returning a partial character;
  an unchecksummed legacy record is handled explicitly and NOT silently trusted; make check green.

out_of_scope: >
  Migrating existing rows. The non-destructive law forbids it and a legacy record must be handled
  by policy, not by rewriting anyone's save.
  kernel/seedlab/backup.py. It already does this correctly and is where the pattern was read from.
  The reward ledger, the purse, inventory. Character record only.

approval_gates: >
  Founder merges. No self-certification. THE POLICY DECISION IS NOT YOURS: what happens to a record
  whose checksum fails is a founder call, because "treat as empty" means a player loses a character.
  Implement the DETECTION and REFUSAL; surface the policy question in the RETURN with the options
  you can see. Do not pick one and ship it.

rollback: >
  git revert the merge commit. The checksum column is additive; existing rows are untouched.

boundary: >
  Computed by packet_gate: the allowlisted files import 14 first-party modules this order may not
  change. Read, not skimmed, because the last version of this order was blocked for exactly this.

  character_store.py is the one that matters and it is deliberately excluded. CharacterRecord is
  defined there and the checksum must NOT become a field on it: law 3 is derive-do-not-store, and a
  checksum stored on the record it checksums becomes part of its own input. The route stays
  reachable because the checksum lives on CharacterRow, written and verified in
  character_store_sql.py, which IS allowlisted.

  The other 13 are read-only collaborators of characters.py: combat, durability, equipment, items,
  job_progress, jobs, loose_store, paths, progression, quest, resources, session, world. A save
  reads them; none of them stores a character, so none needs to change for a checksum to be durable.

file_allowlist:
  - kernel/world/save_integrity.py              # NEW. checksum_of / verify_record /
                                                # IntegrityVerdict
  - kernel/world/character_store_sql.py         # ADDED 2026-08-12. The persistence boundary. This
                                                # is where the checksum is written and read
  - kernel/world/db.py                          # the column on CharacterRow, additive only
  - kernel/world/characters.py                  # the doors: load_character / save_character /
                                                # put_record
  - tests/test_characters.py                    # existing twin, additive
  - tests/test_character_store.py               # ADDED 2026-08-12, existing twin, additive
  - tests/test_save_integrity.py                # NEW, the contract tests below
  - registry/designations/modules.json          # only if a new module is created
  - migrations/versions/*.py                    # ADDED 2026-08-12. The additive Alembic
                                                # revision for the checksum column, permitted by
                                                # the migration ruling. Additive only
  - handoff/CX-009/RETURN.md                    # NEW, explicitly authorisedrised

contract_tests:       tests/test_save_integrity.py
contract_test_policy: |
  ASSERTION-LOCKED. Create exactly. You may ADD. If an assertion is wrong, STOP and say so.

return_artifact:      handoff/CX-009/RETURN.md
return_authorisation: |
  EXPLICITLY AUTHORISED. Required. Extraction block may not be blank.

store_search_result: |
  SEARCH BOTH TIERS and log both, per ADR-0005. Search "checksum", "integrity", "corruption",
  "verify". I searched and found the capability in kernel/seedlab/backup.py, which is ENGINE code
  and not a catalogued Part; judge whether its shape should be consumed rather than re-derived, and
  record the reason either way. A one-tier search that finds nothing is an incomplete search.

parts_to_consume: |
  Likely none catalogued. `applied-once` (PRT-0007) is the nearest certified neighbour and is a
  different problem: it records that something happened once, not that a record is intact.

watch_for: |
  THIS IS THE PULL RULE'S SECOND OCCURRENCE IF YOU FIND IT. seedlab/backup.py verifies bytes and
  this packet verifies a record. If the two want the same primitive, say so in the extraction block
  and do NOT unify them here: a Part is extracted by the Verdict Gate on evidence, not by an
  implementer noticing a resemblance mid-order.
```



## HOW THIS ORDER GOT HERE, in one place instead of five amendments

Five blocks. **Four were my specification defects. The fifth was a real finding and is why this
order is rewritten rather than patched again.**

| # | I asserted | what was true |
|---|---|---|
| 1 | `characters.py` is "the character record" | the record is in `character_store.py` |
| 2 | put a `checksum` field on `CharacterRecord` | law 3 forbids it; a checksum stored on its own input |
| 3 | "no migrations" is absolute | I cut the approval clause while trimming the doctrine |
| 4 | `codeforge migrate-db` runs Alembic | it runs `import_legacy_json()` |
| 5 | one boundary can checksum the row | **two adapters write it, by design** |

Every one of the first four was a claim about a file I had not opened. Block 5 is different: the
order was sound and the system had a second writer nobody had accounted for.

## THE FINDING THAT REWROTE THIS ORDER

`CharacterRow` has exactly two writers, and the split is deliberate and documented:

```
kernel/world/character_store_sql.py   28 writes   gameplay
kernel/world/membership_sql.py         5 writes   account, auth_salt, auth_hash
```

`membership_sql`'s own card: *"this adapter is the only place the account/owner/v1-auth columns are
read or written for auth purposes. Column-scoped, per the merge-save law."* That design exists so a
gameplay save cannot clobber credentials, and it is correct.

It also means **a whole-record checksum written at one boundary is invalidated by a legitimate write
through the other.** Reproduced on a disposable database: `upsert_full` then
`SqlMembershipStore.set_account` then `find` returns **corrupt**. The verdict was right; the scope
was wrong.

## FOUNDER RULING 2026-08-12: scope the checksum, and state the scope

**The checksum covers the 17 gameplay columns `_apply_gameplay` owns, and excludes `account`,
`auth_salt` and `auth_hash`.**

Covered: `allocated coins equipped_gear friends guild guild_rank job level location lockouts order
professions quest_state rank reputation secondary_job xp`

Excluded, and why: `auth_salt` and `auth_hash` are never written by a gameplay save. `account` is
written by both adapters, so `membership_sql.set_account` can change it without passing the
boundary that computes the checksum. Covering a column a second writer can change independently is
not integrity, it is a false alarm generator.

**This is scoping, not weakening, and the difference is that it is written down.** The invariant is
now precise rather than broad: *the gameplay state a player would lose is verified on read; ownership
and credentials are governed by the merge-save law and a narrower, auditable path.* An integrity
record that claims more coverage than it has is worse than one that states its edges.

`IntegrityVerdict` must name its scope in its own output, so nobody reads `intact` as covering
credentials.

## THE ROUTE, TRACED

```
kernel/world/db.py                    CharacterRow gains a defaulted checksum column
migrations/versions/                  an additive Alembic revision, run by `make db-migrate`
kernel/world/character_store_sql.py   computes over the 17 on write, verifies on read
kernel/world/save_integrity.py        checksum_of / verify_record / IntegrityVerdict
```

`CharacterRecord` never carries the checksum. `membership_sql.py` is NOT in the allowlist and needs
no change; that is the ruling, not an oversight. `adapters/cli.py` is not the migration route and
needs no change either.

**Follow `migrations/versions/a2b8f1e6c04d_add_character_coins.py`**: additive column,
`server_default`, and the `# pragma: allowlist secret` comments the scanner requires on revision
ids. Nineteen revisions precede yours.

**`schema_guard.require_current_schema` already reports a database behind the code.** Do not build a
second detector.

**A save written before the column existed is NOT corrupt.** It takes the default and verifies
clean on its next write. An integrity check that condemns every existing save is worse than none.

## Invariant

**A gameplay save that cannot be verified is a save the player loses, and the verdict says exactly
which columns it speaks for.**
