# RETURN CX-009

```yaml
packet_id: CX-009
status: COMPLETE
pr_url: https://github.com/MatrymLabs/codeforge/pull/924

commands_run:
  - command: git rev-list --count HEAD..origin/main
    exit_code: 0
    output: "0"
  - command: pytest -q tests/test_save_integrity.py tests/test_character_store.py tests/test_schema_guard.py
    exit_code: 0
    output: "33 passed in 1.64s"
  - command: >
      create a disposable database at the prior Alembic revision, run schema_guard, then make
      db-migrate and re-read the legacy record after its next gameplay save
    exit_code: 0
    output: >
      schema_guard refused the missing characters.checksum column and named make db-migrate; the
      additive revision ran; the next gameplay save produced an intact record with level 2, xp 10.
  - command: pytest --collect-only -q
    exit_code: 0
    output: "5251 tests collected in 16.45s"
  - command: make check
    exit_code: 0
    output: >
      ruff format check passed (1069 files), ruff check passed, import contracts 4 kept 0 broken,
      mypy succeeded on 807 source files, pytest collected 5251 tests and completed with 5208
      passed, 43 skipped, 0 failed in 267.88s, coverage was 93.43%, and both Bandit scans plus the
      secret scan completed. The complete gate exited 0.
  - command: >
      search Certified Tier at hardware-store origin/main and Working Shelf catalog/parts.yaml for
      checksum, integrity, corruption, verify
    exit_code: 0
    output: >
      Certified Tier returned PRT-0003 source_monitor, which fingerprints external source snapshots,
      not durable character records. Working Shelf returned unrelated reproducible-generation,
      hash-chained-ledger, and optimistic-concurrency entries. No consumable character-record
      integrity Part found.

tests_passing: yes
files_touched:
  - kernel/world/save_integrity.py
  - kernel/world/character_store_sql.py
  - kernel/world/db.py
  - migrations/versions/f8a9c0d1e2f3_add_character_checksum.py
  - tests/test_character_store.py
  - tests/test_save_integrity.py
  - registry/designations/modules.json
  - handoff/CX-009/RETURN.md
blockers: none

policy_question: >
  Detection and refusal are implemented. On CORRUPT gameplay state, the current behavior refuses
  the record with SaveIntegrityError. Founder policy still chooses the recovery action: operator
  refusal, verified-backup recovery if available, or quarantine and fresh start.

extraction_signals:
  reimplemented: none observed
  recurrence: >
    The semantic second occurrence is kernel/seedlab/backup.py: both verify durable state by hash
    and return a named integrity verdict. This packet did not unify them; reviewer should assess an
    extraction candidate because their storage formats and scopes differ.
  generalizable: >
    The checksum and named-verdict shape is generalizable, but its gameplay-only scope is specific
    to CharacterRow's deliberate two-writer boundary.
  friction: >
    Neither reuse tier supplies a Part for checksumming a scoped durable domain record.

pattern_shapes: >
  canonical serialization plus a scoped checksum-backed integrity state machine: gameplay-state
  intact, corrupt, or unverified.
dissent: >
  The original whole-record scope was wrong because membership_sql legitimately writes account and
  credential fields independently. The implemented checksum explicitly covers only the 17 gameplay
  fields character_store_sql owns, and every verdict names that scope.
```
