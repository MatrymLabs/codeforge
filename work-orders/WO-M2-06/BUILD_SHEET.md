# WO-M2-06 BUILD SHEET

**Repo:** `codeforge`

## Scope

`codeforge` only. A new Blueprint under `content/seeds/seam-probe/`, additions to
`tests/test_engine_seam_differential.py`, and a designation row if the loader demands one. No
other repository is touched.

## Invariant

A verdict is attributable to the Blueprint it was measured on. Two Blueprints produce two
verdicts, never one merged number, because the entire question this order asks is whether the
second behaves like the first.

```yaml
packet_id:            WO-M2-06
title:                A second Blueprint, so the battery is run against a population of two
stream:               engine
repository:           codeforge
goal: >
  RESTATED 2026-08-14 after the original was measured and found unable to vary. The first version
  asked for AGREED on two Blueprints. That test could not fail: `seed` is recorded and never
  booted, thirteen of fourteen probes never read a Blueprint, and the fourteenth hardcoded
  first-forge's overlay. `run_differential("first-forge")` and `run_differential("spiral-ascent")`
  return byte-identical verdicts today, on a second Blueprint that already exists.

  So this order does the thing that makes the question answerable, then asks it. TWO parts, in
  order: parameterise the coverage probe so it reads the Blueprint UNDER TEST instead of a
  hardcoded path, then author a second minimal Blueprint and run the differential against both,
  reporting the verdict PER BLUEPRINT.

  What the second Blueprint proves is the LOADER AND OVERLAY PATH generalising beyond the one
  world they were built against. It does not prove the non-spatial battery agrees across worlds,
  because that battery is world-independent by design and correctly so.

out_of_scope: >
  Do NOT make the non-spatial probes world-dependent. Thirteen of them never read a Blueprint and
  that is the design: a probe that needs a booted world tests the world rather than the seam.
  `run_differential`'s own docstring says so. The ONLY probe that becomes Blueprint-sensitive is
  coverage/all_overlay_rooms, because it already reads an overlay and reads the wrong one.
  Do NOT modify the saboteurs or falsifiable_probes(). WO-M2-05 has LANDED (#966), so this order
  now owns kernel/engine_seam.py for the coverage change only. Do
  NOT touch content/seeds/aethryn/ or content/seeds/first-forge/. Do NOT build a playable world:
  this Blueprint exists to be booted by a test, not entered by a human. No renderer, no client,
  no wire protocol.

file_allowlist:
  - kernel/engine_seam.py                (the coverage probe and its call path ONLY)
  - content/seeds/seam-probe/            (new; the whole directory is yours)
  - tests/test_engine_seam_differential.py
  - registry/designations/modules.json   (only if the loader requires a designation)

blast_radius: |
  $ grep -rln "first-forge" --include=*.py . | grep -v build/
  (run this before you fix the allowlist and paste the real output here; if it names a module
   outside the allowlist, STOP and report rather than widening the allowlist yourself)

  The overlay path content/seeds/first-forge/world_overlay.json is read by kernel/overlay.py.
  A second Blueprint needs its own overlay or must prove it needs none. Which of those is true
  is the first thing this order finds out, and it is a finding either way.

boundary: >
  The allowlisted files import kernel/engine_seam.py and kernel/overlay.py, and this order changes
  neither. WO-M2-05 owns engine_seam.py and lands first; this order CALLS run_differential and
  passes it a Blueprint, which is why the definition of done says "accepts which Blueprint to
  boot, defaulting to today's behaviour": a defaulted parameter is reachable without editing any
  existing caller. kernel/overlay.py is read to answer whether the second Blueprint needs its own
  overlay. If the answer is that overlay.py must CHANGE to support a second Blueprint, that is the
  finding, not the fix: STOP and file it BLOCKED.

preconditions: >
    CHECK: file kernel/engine_seam.py contains falsifiable_probes
    CHECK: file content/seeds/first-forge/world_overlay.json exists
    CHECK: file content/seeds/seam-probe/blueprint.yaml absent

    Behavioural:
      WO-M2-05 has LANDED: the rendered verdict names a reason per aspect. If it does not, this
      order is not ready and the correct action is to say so, not to start.
      make proto                                                  FIRST, and every order below
        native/spine imports protobuf bindings that ADR-0012 git-ignores, so `make check` cannot
        pass on a bench that has never generated them. codeforge's own CI runs this as an explicit
        step before the gate; a bench is no different. protoc 27.3 and protoc-gen-go are on this
        host, verified 2026-08-14.
      cd codeforge && make check                                    green
      The differential is AGREED on first-forge BEFORE a second Blueprint is added. A red
      baseline makes the new Blueprint's result unreadable.

contract_tests:
  - tests/test_engine_seam_differential.py
  ASSERTION-LOCKED for every existing assertion. Add; do not edit.

definition_of_done:
  - "PART 1, and it lands first. `_overlay_rooms` at kernel/engine_seam.py:333 stops hardcoding
     content/seeds/first-forge/world_overlay.json and reads the Blueprint under test. The `seed`
     parameter run_differential already accepts must actually reach it. Defaulting to first-forge
     so no existing caller changes."
  - "A test proves the parameterisation BITES: run the differential against two DIFFERENT
     Blueprints and assert the coverage probe answers differently. Today
     run_differential('first-forge') and run_differential('spiral-ascent') are byte-identical;
     after this they must not be, or the change did nothing. This is the calibration and it is
     mandatory."
  - "PART 2. A second Blueprint under content/seeds/seam-probe/, deliberately minimal: the fewest
     rooms, items and Callings that let the loader and the overlay pipeline run. Trivial is the
     point. C1: if the seam fails on something trivial that is learned for the price of an
     afternoon."
  - "It is genuinely NOT first-forge: different room labels, different item labels, different
     counts. A copy with renamed keys proves nothing and will be rejected on review."
  - "It LOADS through the existing loader gates in kernel/world/seed.py and GENERATES a valid
     overlay through the same pipeline first-forge uses. That is the claim this Blueprint is here
     to support."
  - "The verdict is reported PER BLUEPRINT. Two results are two findings, never one merged number."
  - "If the second Blueprint DIVERGES: stop, file a BLOCKED Bench Report with the divergence
     rendered verbatim, and do not repair it. A divergence is a Principal Engineer decision and
     never a Bench rewrite. A BLOCKED return here is the best available outcome, not a setback."
  - "If the second Blueprint needs its own world_overlay.json, SAY SO. If it needs none, say that
     instead. Either answer is a real seam fact nobody has written down, and it is worth more than
     the AGREED."
  - "make proto && make check green."

verification_command: |
  cd codeforge && make proto && make check && .venv/bin/python -m pytest tests/test_engine_seam_differential.py -q

rollback: >
  git revert the commit; delete content/seeds/seam-probe/. The Blueprint is additive and no
  existing world, save file or migration references it.

approval_gates: >
  A DIVERGENCE STOPS THE WORK AND COMES TO THE FOUNDER. That is the only gate, and it is hard.

size:                 medium

taint_class:          SAFE
                      Original content authored for this repository. No external world, ruleset or
                      studied material is used. Do not derive the probe Blueprint from any MUD
                      corpus in rd/00-intake/legacy-muds/; that material is CAUTION and must not
                      reach an implementation order.

# EXTRACTION CONTEXT - read before implementing
store_search_result: >
  Certified Tier (hardware-store/catalog/): no Blueprint-authoring or world-fixture Part.
  Working Shelf (codeforge/catalog/parts.yaml): the Blueprint loader and validator already exist
  in kernel/world/seed.py and are what you build on; there is no fixture-Blueprint Part. BOTH
  tiers searched.

parts_to_consume: >
  kernel/world/seed.py loader gates. The world is data (architecture law 2): the probe Blueprint
  is YAML validated by the existing loader, never hard-coded in Python. Any temptation to build
  it in a fixture function is the law this repository states first.

watch_for: >
  If the second Blueprint needs its own world_overlay.json, then overlay generation is per
  Blueprint and that is a real seam fact nobody has written down. Flag it. If it needs none, that
  is a stronger finding and flag that instead. Either answer is worth more than the AGREED.
```

## Sequencing note, from the board

"Strengthen the instrument, then widen the population. If the battery is too narrow, a second
Blueprint passing it proves nothing more than the first did." WO-M2-05 is the strengthening and
lands first. This order is the widening. Running them in the other order wastes the second
Blueprint on an instrument that cannot yet say what it measured.
