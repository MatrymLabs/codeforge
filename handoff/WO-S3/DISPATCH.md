# DISPATCH WO-S3

```yaml
packet_id:            WO-S3
title:                Make Engine-2D real enough to disagree
stream:               engine-2d seam
owner:                Codex
reviewer:             Claude Code, who re-runs every command independently
merges:               founder
size:                 medium
taint_class:          SAFE. No studied external material. This engine's own seam and its own Seed data.

goal: >
    Replace `Engine2DStub` with an Engine-2D that derives position from a GENERATED WORLD OVERLAY
    instead of from a hash of the room label, and run the existing differential battery against it.

    THE INVARIANT, in prose and separate from the commands that test it: the core is engine-agnostic,
    and the differential test is the only thing that can say so honestly. Today it compares Engine-0D
    against a stub that cannot disagree, because its position function is a hash of the same string
    the core already holds. A stub agreeing with the core proves the stub, not the seam.

why_now: >
    `.ai/handoff.md` names LEG 2C open and the Build's destination as "boot ONE trivial Seed under
    Engine-0D and Engine-2D and assert identical non-spatial state transitions."

    Measured: `tests/test_engine_seam_differential.py` passes 11 of 11, and its own imports read
    `Engine2DStub`. `kernel/engine_seam.py:98` says so in the class docstring: "A stub on purpose:
    WO-S1 proves the SEAM, and a renderer would prove a renderer. Chunk coordinates are derived
    deterministically from the room label so the mapping is reproducible without a world overlay,
    which is D5's build step and is not Phase 0."

    Phase 0 is over. D5's build step is this order.

the_ruling_that_shapes_it: >
    ENGINE_SEAM D5, quoted because it settles the design and is not negotiable here:

      "Core Seed data holds the canonical world. Geometry, chunk layout, and tile assignments live in
       a generated overlay produced offline, deterministically, before boot. It cannot mutate
       canonical state because it does not run at runtime. Tiles are projection, exactly as text is
       projection."

    Three consequences, and an implementation that violates any of them is wrong even if green:
      the overlay is GENERATED, by a build step, from Seed data. Not authored by hand.
      the overlay is DETERMINISTIC. The same Seed produces the same overlay, byte for byte.
      the overlay is READ-ONLY at runtime. Nothing in the engine writes it, and the generator does
      not run at boot.

    D6 also binds: "Tiles carry no describable semantics." The overlay holds geometry, never meaning.
    If a tile needs to know it is an ancient oak, the design has gone wrong.

out_of_scope: >
    A RENDERER. C1 is explicit: "Phase 0 proves an engine seam, not a renderer." No Godot, no
    drawing, no client. This order ends at an engine that answers `place` and `room_of` from real
    geometry.

    THE SEAM PROTOCOL. `Engine` in kernel/engine_seam.py must not gain a method. Its docstring
    states the test: "If this Protocol ever needs a method that is not about position, the seam has
    moved and something core has slid below it." If Engine-2D appears to need one, that is a BLOCK
    and a founder question, not a widening.

    Collision, pathfinding, tick cadence, chunk streaming, and the contiguous-vs-instanced question
    (C2, open as R4). None of these are settled and none is needed to answer `place`.

    Deleting `Engine2DStub`. Keep it. The differential battery's own tests use it to prove the
    harness detects a planted divergence, and a stub that cannot disagree is exactly the right tool
    for that job.

boundary: >
    Computed by packet_gate from the allowlisted files' imports. The seam reaches two first-party
    modules this order may NOT change, and the route stays reachable without touching either:

      kernel/world/session.py       the differential battery constructs sessions to run its
                                    non-spatial probes. Engine-2D answers `place` and `room_of`
                                    about a session's position; it never mutates one. Session is
                                    READ across the seam and written only by the core, which is D1.
      kernel/world/reward_ledger.py reached transitively by the progression aspect of the battery.
                                    The battery ASSERTS on progression identically under both
                                    engines; that is the point of the probe. Changing the ledger
                                    would change what both engines are being compared against, which
                                    would invalidate the comparison rather than pass it.

    If Engine-2D appears to need a write into either, the seam has moved and something core has slid
    below it. That is the exact condition the Engine Protocol's own docstring names, and it is a
    BLOCK and a founder question, not a widening of this allowlist.

preconditions: >
    CHECK: file kernel/engine_seam.py contains Engine2DStub
    CHECK: file tests/test_engine_seam_differential.py exists
    CHECK: file registry/designations/modules.json exists
    CHECK: file kernel/engine_seam.py lacks Engine2D(

THE_MOST_IMPORTANT_INSTRUCTION_IN_THIS_ORDER: >
    IF THE DIFFERENTIAL TEST DIVERGES, STOP. DO NOT FIX IT.

    ENGINE_SEAM C1 and the Build board both say it: "Any divergence means something leaked across
    the seam, and that is a founder decision, never a bench rewrite."

    A divergence is the most valuable outcome this order can produce. It means a real Engine-2D
    found something the stub could not, which is the entire reason for replacing the stub. Record
    what diverged, under which engine, for which aspect, with the command that shows it, mark the
    RETURN BLOCKED, and hand it back.

    Do not adjust the overlay to make a divergence go away. Do not weaken an assertion. Do not add a
    tolerance. The order succeeds if it produces a truthful answer, and "they disagree, here is
    exactly how" is a truthful answer worth more than a green suite.

contract_tests: >
    Additive to tests/test_engine_seam_differential.py, and the existing 11 must keep passing
    unchanged. Four new ones:

      the overlay generator is DETERMINISTIC: generating twice from the same Seed yields identical
      bytes. Assert on the bytes, not on a summary of them.

      Engine-2D reads the overlay and does NOT hash the room label. Prove it the only way that is
      not circular: two rooms whose labels hash to the same bucket under the stub's function must
      receive DIFFERENT positions under the real engine, or the engine is still a hash in disguise.

      `room_of(place(room)) == room` for every room in the trivial Seed, under BOTH engines. The one
      question the seam says both must answer identically.

      the overlay is READ-ONLY at runtime: no engine method writes it. A test that opens it for
      writing and fails is not the point; assert that the engine holds no write path to it.

verification_command: |
    cd codeforge
    make check

definition_of_done: >
    A generated overlay, produced by a build step from Seed data, deterministic byte-for-byte, and
    read-only at runtime. An `Engine2D` that satisfies the existing `Engine` Protocol WITHOUT
    extending it and derives position from that overlay. `Engine2DStub` retained. The differential
    battery run against the real engine with its result reported honestly, agreed or diverged. The
    new module filed in registry/designations/modules.json, because the completeness gate will
    demand it. `make check` green over the whole instrument.

    If the battery diverges, definition_of_done is the BLOCKED return with the divergence named.
    That is a complete outcome, not a failure.

calibration_required: >
    The battery already proves it can detect a planted divergence, which is why this order does not
    rebuild that. What must be calibrated is the NEW claim:

      corrupt one entry in the generated overlay, prove `room_of(place(room)) == room` FAILS for that
      room, restore, prove it passes. Paste both.

    An overlay nothing verifies is a data file, not a source of truth.

rollback: >
    Revert the commit. The stub is retained, so reverting restores the previous engine wholesale and
    the overlay becomes an unused generated file.

approval_gates: >
    TWO, both real.

    A DIVERGENCE is a founder decision. See the instruction above; it stops the order.

    ANY CHANGE TO THE `Engine` PROTOCOL is a founder decision, because the seam moving is the thing
    the seam exists to detect. Propose it in the RETURN and stop.

store_search_result: >
    Both tiers searched 2026-08-13; one tier logged is an incomplete search.
    Certified Tier (hardware-store/catalog/, 20 cards: 3 CERTIFIED, 4 CANDIDATE, 13 STUDIED): the
    thirteen STUDIED cards include `metatile-hierarchy`, `tilemap-bit-packing` and
    `constrained-map-streaming`, which are the closest by subject in the whole Store. All three are
    STUDIED, meaning written down and NOT implemented, so none can be consumed as code. They are
    worth READING before designing the overlay's layout, and that is the first time the studied-card
    campaign has had a real consumer to read it.
    Working Shelf (codeforge/catalog/parts.yaml, 104 entries): `weighted-table`, `zone-scheduler`,
    `minimap`. `minimap` renders an ASCII map from a room graph, which is a projection of the same
    data this overlay generates, but it consumes a graph rather than producing geometry.

    Verdict: NO PART to consume as code. Three STUDIED cards to read as design input. Log which of
    them, if any, actually informed the layout; if one does, that is the first evidence a STUDIED
    card earned its place and it belongs in the RETURN.

parts_to_consume: >
    None as code. See store_search_result. If the overlay's layout ends up matching a studied
    pattern, say which and why in the RETURN as an extraction signal.

watch_for: >
    THE FAILURE MODE IS AN ENGINE THAT IS STILL A HASH WEARING A FILE. If the generator derives
    geometry from the room label and writes it to disk, and the engine reads it back, nothing has
    changed except the number of steps. The second contract test exists to catch exactly that, and
    it is the one to write first.

    Second: the completeness gate will refuse a new module that is not filed in
    registry/designations/modules.json. That is not a surprise, it is in the allowlist.

    Third: the differential battery has a test asserting "a battery that measures nothing is
    INCONCLUSIVE, not AGREED." If the real engine cannot be probed for an aspect, the honest result
    is INCONCLUSIVE. Do not report AGREED over a probe that did not run.

blast_radius: >
    Run before this allowlist was fixed.

      grep -rln 'Engine2DStub|engine_seam' tests/ kernel/ adapters/
      -> kernel/engine_seam.py, tests/test_engine_seam_differential.py.  Nothing else, and in
         particular NO adapter imports the seam, so no runtime surface changes.

      grep -rln 'differential' tests/ kernel/
      -> tests/test_engine_seam_differential.py only, once __pycache__ and the unrelated
         AGREED/INCONCLUSIVE vocabulary in hubble/diagnosis, verify_smt, transform_verifier,
         diagnostic_runner and bench_protocol are excluded. Those five share the words, not the
         battery, and were checked individually rather than counted.

      ls registry/designations/modules.json  -> EXISTS. The completeness gate demands every module
         be filed, so a new engine module without a registry row fails `make check`. In the allowlist.

      grep -rln 'overlay' kernel/ content/ tests/  -> no overlay generator or overlay data exists.
         This order creates the first.

    What that surfaced: the seam has exactly two consumers and no adapter depends on it, so the
    change is contained; and the registry is a hard dependency that would have blocked the order at
    the gate had it not been declared.

file_allowlist:
  - kernel/engine_seam.py                      # the real Engine2D; the Protocol must NOT change
  - kernel/world/overlay.py                    # NEW. the generator, offline and deterministic
  - content/seeds/                             # NEW generated overlay data only; no canonical edits
  - tests/test_engine_seam_differential.py     # ADDITIVE. the existing 11 stay green unchanged
  - registry/designations/modules.json         # the completeness gate will demand the new module
  - handoff/WO-S3/RETURN.md                    # NEW, explicitly authorised
```
