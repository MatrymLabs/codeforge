# WO-M2-05 BUILD SHEET

**Repo:** `codeforge`

## Scope

`codeforge` only. Two files: `kernel/engine_seam.py` and
`tests/test_engine_seam_differential.py`. No other repository is touched, and no file outside
that pair is created or modified.

## Invariant

The differential's REPORTED strength never exceeds its MEASURED strength. Every aspect the
verdict names is classified as falsifiable-by-sabotage or structurally-unfalsifiable-with-a-
reason, and no aspect is silently absent. Breaking this invariant looks exactly like the defect
that produced this order: a board claiming an effective battery of 4 over an instrument that
measures 3.

```yaml
packet_id:            WO-M2-05
title:                The seam verdict states which aspects CANNOT diverge, and why
stream:               engine
repository:           codeforge
goal: >
  The differential reports "14 comparison(s) across 5 aspect(s), 3 of them falsifiable" and stops
  there. A reader cannot tell WHICH 3, cannot tell whether the other 11 are weak probes or
  structurally unfalsifiable ones, and has no way to learn that progression and permission sit
  ABOVE the seam by D1, so a probe there that COULD diverge would itself be the leak. That
  reasoning exists only in a docstring inside falsifiable_probes(). When done, the rendered
  verdict states per aspect whether it is falsifiable by sabotage or structurally unfalsifiable,
  and the Workbench cannot claim a falsifiable count the instrument does not report.

out_of_scope: >
  Do NOT make progression or permission falsifiable. Do NOT fold an engine-derived value into a
  probe's answer to raise the count. falsifiable_probes() already argues why that buys a number
  and proves nothing, and that argument is correct: an above-the-seam probe that can diverge IS
  the leak. Do not add saboteurs beyond the Protocol's three levers. Do not touch the overlay,
  the wire protocol, Engine2D geometry, or any content/ file. Do not change what the existing
  14 probes measure.

file_allowlist:
  - kernel/engine_seam.py
  - tests/test_engine_seam_differential.py

blast_radius: |
  $ grep -rln "falsifiable" --include=*.py . | grep -v build/
  ./kernel/engine_seam.py
  ./kernel/shelf/applied_once.py
  ./tests/test_reward_ledger_conforms.py
  ./tests/test_engine_seam_differential.py
  ./tests/test_retroforge_artifact.py

  applied_once.py, test_reward_ledger_conforms.py and test_retroforge_artifact.py use the WORD
  in unrelated prose, not the SeamVerdict field. Verified by reading each. The field has exactly
  two consumers, both in the allowlist.

boundary: >
  The allowlisted files import kernel/overlay.py, kernel/world/seed.py, ranks.py, characters.py,
  character_store.py, reward_ledger.py and progression, and this order changes NONE of them. It
  adds a classification ALONGSIDE the existing probes; it does not alter what any probe calls or
  what any of those modules return. The route stays reachable because the battery already imports
  them today and runs green, and nothing here touches a call site. If classifying an aspect turns
  out to require changing what a probe measures, that is a different order: STOP and report it.

preconditions: >
    CHECK: file kernel/engine_seam.py exists
    CHECK: file kernel/engine_seam.py contains falsifiable_probes
    CHECK: file tests/test_engine_seam_differential.py exists

    Behavioural, and run before you touch anything:
      make proto                                                  FIRST, and every order below
        native/spine imports protobuf bindings that ADR-0012 git-ignores, so `make check` cannot
        pass on a bench that has never generated them. codeforge's own CI runs this as an explicit
        step before the gate; a bench is no different. protoc 27.3 and protoc-gen-go are on this
        host, verified 2026-08-14.
      cd codeforge && make check                                    green
      .venv/bin/python -c 'from kernel.engine_seam import run_differential;
      print(run_differential().render())'
        expect: 14 comparison(s) across 5 aspect(s), 3 of them falsifiable / VERDICT: AGREED
      A red or differently-shaped baseline means STOP and report, not adapt.

contract_tests:
  - tests/test_engine_seam_differential.py
  ASSERTION-LOCKED. The existing assertions in this file are not yours to modify. In particular
  test_real_engine_2d_passes_the_non_spatial_battery pins commands_compared, and
  test_an_aspect_with_no_MEASURED_probe_is_not_reported_as_covered pins the coverage rule. Add
  new tests; change no existing assertion. If an existing assertion appears wrong, STOP and file
  a BLOCKED Bench Report saying which and why.

definition_of_done:
  - "SeamVerdict carries a per-aspect falsifiability record: for each aspect, either the probe
     names that sabotage can move, or the reason it is structurally unfalsifiable."
  - "The reason is DATA, not a docstring. The D1 argument (progression and permission are above
     the seam; a divergence there is itself the leak) must be readable from the rendered output,
     because the Workbench has already dispatched 'make progression falsifiable' once against a
     docstring nobody read."
  - "render() prints it. A reader of the output alone can say which aspects carry evidence of
     agreement and which are regression guards."
  - "A new test asserts that every aspect is classified: no aspect may be silently absent from
     the falsifiability record. Model it on the existing C1 four-aspect coverage test."
  - "A new test asserts the structural reason is non-empty for every aspect with zero falsifiable
     probes. An unfalsifiable aspect with no stated reason is the defect this order exists to fix."
  - "make check green."

verification_command: |
  cd codeforge && make proto && make check && .venv/bin/python -c "from kernel.engine_seam import run_differential; print(run_differential().render())"

rollback: >
  git revert the single commit. The instrument is read-only with respect to world state and has
  no persisted artifact, so revert is total.

approval_gates: >
  none for implementation. If your per-aspect record shows an aspect the Workbench currently
  claims is falsifiable and is NOT, say so in the Bench Report. Do not correct the Workbench;
  that is Claude Code's board and the Principal Engineer's ruling.

size:                 small

taint_class:          SAFE
                      Derived from this repository's own instrument and from ENGINE_SEAM.md D1,
                      both first-party. No studied external material of any kind.

# EXTRACTION CONTEXT - read before implementing
store_search_result: >
  Certified Tier (hardware-store/catalog/): searched for a falsifiability, mutation-scoring or
  probe-classification Part. Nothing catalogued. Working Shelf (codeforge/catalog/parts.yaml):
  searched the same; the nearest entries are the mutation scorer (adapters/mutation_scorer.py,
  branch feat/real-mutation-scorer, unmerged) and kernel/shelf/applied_once.py, neither of which
  classifies probes. BOTH tiers searched, both empty. Build it here.

parts_to_consume:     none

watch_for: >
  This is the second time this instrument has been asked to report honestly about its own
  strength, after the valid-room saboteur correction recorded in _saboteurs(). If you find
  yourself writing a third variation of "count the probes that can actually move", say so: a
  mechanism written three times in one file is a Part candidate under the pull rule, and it would
  need a named second consumer before it went anywhere.
```

## Why this order exists, in one paragraph

The Workbench carried "PROGRESSION MADE FALSIFIABLE, or the falsifiable count reported beside
commands_compared" as owed work. Re-verification on 2026-08-14 found the second half already
landed on origin/main, and found the first half is a trap the code itself argues against. It also
found the Workbench's own effective-battery figure wrong: the board says permission contributes 1
of 4, the instrument reports 0, and the true falsifiable set is exactly
`inventory/carry_limit`, `persistence/save_restore_casefile`, `coverage/all_overlay_rooms`. Every
one of those errors is the same error: the reasoning lives somewhere a reader of the output cannot
see. This order moves it into the output.
