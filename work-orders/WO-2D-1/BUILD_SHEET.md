# WO-2D-1 BUILD SHEET

**Repo:** `codeforge`

## Scope

`codeforge` only. One new report file under `reports/`. **No source file is modified.** This is a
measurement order and it produces a document, not a behaviour change.

## Invariant

The report states what is measured and does not state what is not. Every count is reproducible by
a command pasted beside it. A classification that cannot be defended from the file it came from is
a guess, and a guess in a scouting report becomes a false premise in the order that follows it,
which is exactly how the last two seam criteria came to be unfalsifiable.

```yaml
packet_id:            WO-2D-1
title:                Scout the real seam surface, so 2D-2 is sized by measurement
stream:               engine
repository:           codeforge
goal: >
  D8 proposes making Session.position engine-native and Session.location derived. Before anyone
  edits the domain model, classify what the 123 `session.location` references actually DO, so the
  injection is sized from evidence rather than from the shape of the grep.

  Three buckets, and the third is the one that decides the order's difficulty:
    ROOM-LABEL CONSUMER   uses the value as a key into a room-scoped collection and would be
                          unaffected by a derived property. announce(), npcs_in(), WORLD.get().
    ASSIGNMENT            writes the field. Becomes engine.place(room).
    GENUINE POSITION      anything that treats the label as more than a room key: compares it to a
                          literal, stores it, serialises it, does arithmetic or string work on it,
                          or relies on its identity. These are the ones a derived property could
                          break, and they are the finding.

  When done: a dated report in reports/ with the three counts, EVERY genuine-position site listed
  by file and line with one sentence on why it is in that bucket, and a verdict on whether 2D-2 is
  a small change or a large one.

out_of_scope: >
  Do NOT modify kernel/world/session.py or any consumer. Do NOT introduce Session.position. Do NOT
  refactor anything you find, however obviously wrong it looks; a scouting order that also fixes
  things cannot be reviewed, because the reader cannot tell the measurement from the repair. File
  what you find and stop.

file_allowlist:
  - reports/2026-08-14-seam-surface-scout.md    (new; the whole file is yours)

blast_radius: |
  $ grep -rn 'session\.location' --include=*.py kernel/ adapters/ forge.py | grep -v build/ | wc -l
  123
  $ grep -rl 'session\.location' --include=*.py kernel/ adapters/ forge.py | grep -v build/ | wc -l
  27
  Measured 2026-08-14 on origin/main. Nothing is modified by this order, so the blast radius of
  the CHANGE is one new file. The blast radius of the FINDING is the 27 files above, which is the
  point of measuring it.

boundary: >
  This order owns exactly one new report file. It reads the 27 files that reference
  `session.location` and modifies none of them. `kernel/world/session.py` is read to understand
  the field and is not edited here; 2D-2 owns it.

preconditions: >
    CHECK: file kernel/world/session.py exists
    CHECK: file kernel/world/session.py contains location
    CHECK: file ENGINE_SEAM.md absent

    Behavioural:
      D8 is ruled and readable in the Workshop root's ENGINE_SEAM.md. It is NOT in this
      repository, which is why the CHECK above asserts its absence here rather than its presence.
      export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
      make proto && make check                                    exit 0 before you start

contract_tests: >
  None, and deliberately. This order adds no behaviour, so a test would assert the contents of a
  document, which is a check that the author agreed with themselves. The contract here is that
  every count in the report is reproducible: paste the command beside the number.

definition_of_done:
  - "A dated report at reports/2026-08-14-seam-surface-scout.md."
  - "Three counts, each with the command that produced it pasted beside it, and the three summing
     to 123 or an explanation of why they do not."
  - "EVERY genuine-position site listed by file:line with one sentence saying what it does with
     the value that a room key would not survive."
  - "A verdict in the report's own words: is 2D-2 small, medium or large, and what is the single
     riskiest site."
  - "Permission and persistence called out specifically. `session.location` is read by rank and
     workshop-barrier checks and is stored by character_store; if either treats the label as more
     than a room key, that is the highest-value finding in the order and it belongs at the top."
  - "make proto && make check green, which for this order proves only that you broke nothing."

verification_command: |
  cd codeforge && make proto && make check && test -f reports/2026-08-14-seam-surface-scout.md

rollback: >
  Delete the report. Nothing else changed.

approval_gates: >
  none. This order cannot change behaviour.

size:                 small

taint_class:          SAFE
                      Reads only this repository's own source. No external material.

# EXTRACTION CONTEXT - read before implementing
store_search_result: >
  Certified Tier (hardware-store/catalog/): searched for a reference-classifier or call-site
  survey Part. Nothing catalogued. Working Shelf (codeforge/catalog/parts.yaml): the nearest
  entries are the content-addressed clone detector (EXP-27) and the file_plan repo-structure
  linter (EXP-28); neither classifies usage of a field. BOTH tiers searched, both empty. This is a
  one-off measurement and should stay one, unless 2D-1 turns out to be the third such survey.

parts_to_consume:     none

watch_for: >
  If classifying these 123 sites needs a rule you have to invent, say what the rule is in the
  report. A bucket boundary decided silently is how a scouting report becomes authoritative
  without ever being reviewed.
```
