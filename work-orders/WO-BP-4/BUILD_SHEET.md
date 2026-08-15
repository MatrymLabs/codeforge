# WO-BP-4 BUILD SHEET

**Repo:** `codeforge`

## Scope

`codeforge` only. The duplicate-key constructor in `kernel/world/seed.py` and its tests. **One
function, one failure mode.**

## Invariant

**Every malformed Blueprint file produces a `SeedError` naming the file, never a `TypeError`.** A
gate that crashes tells the author nothing about what was wrong with their content, which is the
one job a loader gate has.

```yaml
packet_id:            WO-BP-4
title:                The Blueprint loader raises SeedError on malformed YAML, never TypeError
stream:               engine
repository:           codeforge
goal: >
  The fuzz gate found a crash on origin/main and it reproduces in one line:

    yaml.load('? ?', Loader=_UniqueKeyLoader)
    -> TypeError: unhashable type: 'dict'    kernel/world/seed.py:469

  `? ?` is valid YAML for a COMPLEX KEY, a mapping used as a key.
  `_construct_unique_mapping` does `if key in mapping:` to detect duplicate labels, and that
  explodes when the key is unhashable.

  The test is named test_seed_gate_never_crashes_on_raw_text. The gate crashes, on two characters.

  When done, an unhashable or otherwise unusable key raises SeedError with a message an author can
  act on, and the fuzz gate passes.

out_of_scope: >
  Do NOT redesign the loader, the duplicate-key rule, or the SeedError hierarchy. One failure mode.
  Do NOT change what a VALID Blueprint loads to. The 5299 passing tests are the evidence that
  valid content is unaffected, and any one of them moving means the change went too far.
  Do NOT touch the Blueprint compatibility aliases from BP-1 in the same file; they are unrelated
  and landed as #977.
  Do NOT weaken or delete the fuzz test to make it pass. That test is correct and the code is not.

file_allowlist:
  - kernel/world/seed.py
  - tests/test_seed.py
  - tests/test_fuzz_gates.py

blast_radius: |
  $ grep -n "_UniqueKeyLoader" -- '*.py' | grep -v build/
  kernel/world/seed.py            defines it
  kernel/world/authored_towns.py:38   yaml.load(..., Loader=_UniqueKeyLoader)
  kernel/world/canon.py:53, :185      yaml.load(..., Loader=_UniqueKeyLoader)

  Three call sites outside the definition, all of them loading authored content from disk. Each
  gets the improved error for free and none needs editing: they already expect SeedError from a
  bad file, which is precisely the bug, since today they get TypeError instead.

  $ grep -c "raise SeedError" kernel/world/seed.py
  104        the existing convention to match. Read three of them before writing the new one.

boundary: >
  This order OWNS the constructor function and the two test files. It does NOT own
  authored_towns.py or canon.py: they consume the loader and are the reason the fix matters, but
  they need no change. If either needs editing, STOP and file BLOCKED, because that means the fix
  changed the loader's contract rather than its failure mode.

preconditions: >
    CHECK: file kernel/world/seed.py contains _construct_unique_mapping
    CHECK: file tests/test_fuzz_gates.py contains test_seed_gate_never_crashes_on_raw_text

    Behavioural, and the first one is the reproduction:
      export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
      python -c "import yaml; from kernel.world.seed import _UniqueKeyLoader; yaml.load('? ?', Loader=_UniqueKeyLoader)"
        expect: TypeError: unhashable type: 'dict'
      CAPTURE THAT OUTPUT VERBATIM IN THE BENCH REPORT BEFORE YOU FIX ANYTHING. Failure before
      repair: run it, record the failure, then repair, then run again and record both.

contract_tests:
  - tests/test_fuzz_gates.py
  ASSERTION-LOCKED, and this one especially. The fuzz test is CORRECT and the code is wrong.
  Deleting it, narrowing its input strategy, or adding an xfail would turn a caught bug into a
  hidden one. If you believe the test is wrong, file BLOCKED and say why.

definition_of_done:
  - "`yaml.load('? ?', Loader=_UniqueKeyLoader)` raises SeedError, not TypeError."
  - "The message names the problem in the author's terms: an unusable key in a Blueprint file, and
     which file if the loader knows it. Match the voice of the 104 existing SeedError messages."
  - "A NEW unit test pins the exact reproduction, `? ?`, so this cannot regress silently. The fuzz
     gate finding it again is luck; a named test is not."
  - "Consider the sibling case in the same pass and say what you found: a LIST used as a key,
     `? [a]`, is also unhashable. If it has the same fault, fix both; if not, say why not."
  - "tests/test_fuzz_gates.py::test_seed_gate_never_crashes_on_raw_text passes."
  - "The whole suite passes with no other test edited. 5299 currently pass; 5300+ afterwards."
  - "make proto && make check green."

verification_command: |
  cd codeforge && make proto && make check && python -c "
  import yaml
  from kernel.world.seed import SeedError, _UniqueKeyLoader
  try: yaml.load('? ?', Loader=_UniqueKeyLoader)
  except SeedError as e: print('SeedError, correct:', e)
  "

rollback: >
  git revert. The loader returns to raising TypeError on complex keys, which is where main is now.

approval_gates: >
  none. It is a bug fix inside one function with a reproducible trigger.

size:                 small

taint_class:          SAFE
                      A defect in this repository's own parser, found by its own fuzz gate.

# EXTRACTION CONTEXT
store_search_result: >
  Certified Tier (hardware-store/catalog/): searched for a YAML-hardening or safe-loader Part.
  Nothing catalogued. Working Shelf (codeforge/catalog/parts.yaml): searched the same; the
  transform_verifier and contract parts are adjacent but neither guards deserialisation. BOTH
  tiers searched, both empty.

parts_to_consume:     none. SeedError already exists and is the convention.

watch_for: >
  This is the FOURTH instrument this week that reported the wrong cause: lint-go called a missing
  toolchain missing generated code, `imports` called a PATH fault a missing package, lint-go again
  called a read-only cache missing generated code, and now the Blueprint loader reports a malformed
  file as a Python TypeError. If you see a fifth, say so plainly. Four is a pattern about how this
  codebase reports failure, not four unrelated bugs, and naming it is worth more than the fix.
