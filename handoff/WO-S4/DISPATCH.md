# DISPATCH WO-S4

```yaml
packet_id:            WO-S4
title:                Try to make the engines disagree
stream:               engine-2d seam
owner:                Codex
reviewer:             Claude Code, who re-runs every command independently
merges:               founder
size:                 medium
taint_class:          SAFE. No studied external material. This engine's own seam and its own Seed.

goal: >
    Widen the differential battery until it can find a divergence between Engine-0D and Engine-2D, or
    until the Workshop can say honestly that it tried and could not.

    THE INVARIANT, in prose and separate from the commands that test it: AGREED is only as strong as
    the battery that produced it. A verdict of "no divergence found" is worth exactly the breadth of
    the search behind it, and today that search is eight commands over four aspects, two of which
    carry a single probe each.

why_now: >
    Founder ruling 2026-08-13: LEG 2C is NOT closed. WO-S3 made Engine-2D read real geometry and the
    battery returned AGREED, but the overlay still owes proof.

    Measured on origin/main after WO-S3 merged:

      aspects probed:      inventory 3, progression 3, permission 1, persistence 1
      commands compared:   8
      rooms in the Seed:   12

    C1 asks for "identical state transitions for every non-spatial command, same inventory
    mutations, same progression, same permission denials, same persistence writes." Permission and
    persistence are each carried by ONE probe. Eight commands are compared across a twelve-room
    world. **AGREED across four aspects is only as strong as the four**, and two of them are thin.

    This order comes BEFORE a second Seed, deliberately. If the battery is too narrow, a second Seed
    passing it proves nothing more than the first did. Strengthen the instrument, then widen the
    population.

what_success_looks_like: >
    READ THIS TWICE. Success is NOT a green suite.

    Success is EITHER a divergence, named precisely, OR a battery that is demonstrably wider and
    still finds none. Both are complete outcomes. A wider battery that stays green is a stronger
    claim than the one we have; a divergence is worth more than both.

    IF YOU FIND A DIVERGENCE, STOP. ENGINE_SEAM C1 and the board: "Any divergence means something
    leaked across the seam, and that is a founder decision, never a bench rewrite." Record what
    diverged, under which engine, for which aspect, with the command that reproduces it. Mark the
    RETURN BLOCKED. Do not fix it. Do not adjust the overlay. Do not weaken the assertion.

    A BLOCKED return here is the best result this order can produce.

out_of_scope: >
    A RENDERER, and any spatial comparison. The battery is for NON-SPATIAL state. The engines are
    SUPPOSED to differ on position; that is the whole point of two engines. Comparing positions
    would manufacture a divergence that means nothing.

    THE `Engine` PROTOCOL. It must not gain a method. Its docstring states the test: a method that is
    not about position means the seam has moved. That is a BLOCK, not a widening.

    A SECOND SEED. Ruled as owed, and it is the NEXT order, not this one. Widening the battery and
    widening the world at once would leave a divergence ambiguous between the two causes.

    Changing Engine-0D or Engine-2D to make a probe pass. If a probe cannot run, that is
    INCONCLUSIVE and is reported as such.

boundary: >
    Computed by packet_gate from the allowlisted files' imports. Four first-party modules this order
    may NOT change, and the route stays reachable without touching any:

      kernel/overlay.py             WO-S3 created it and this order READS it, to derive room coverage
                                    from the overlay rather than from a literal. Read-only by
                                    construction: D5 says the overlay does not run at runtime and
                                    nothing here generates or mutates one.
      kernel/world/seed.py          locates the Seed the overlay was generated from. Read only; this
                                    order does not add, edit or re-generate Seed content.
      kernel/world/session.py       the battery constructs sessions to run probes. Sessions are
                                    WRITTEN by the core during a probe, which is the behaviour under
                                    comparison; the battery never writes one directly.
      kernel/world/reward_ledger.py reached transitively by the progression aspect. Widening
                                    progression probes exercises it; changing it would move what both
                                    engines are compared against, invalidating the comparison rather
                                    than passing it.

    The distinction that matters: a probe DRIVES the core and OBSERVES the result. If a widened probe
    appears to need a direct write into any of these to make an assertion pass, the probe is measuring
    the wrong thing, and that is a BLOCK rather than a widening of this allowlist.

preconditions: >
    CHECK: file kernel/engine_seam.py contains class Engine2D
    CHECK: file kernel/overlay.py exists
    CHECK: file tests/test_engine_seam_differential.py contains commands_compared

the_widening: >
    Ranked by how likely each is to surface a real leak, which is not the same as how easy each is.

    1. PERMISSION, currently ONE probe. The richest place for a leak, because a rank check that
       consults position would be invisible today. Probe denials at multiple ranks, on verbs that
       differ in what they touch, and include at least one denial that depends on WHERE the session
       is, since that is the aspect most likely to reach across the seam.

    2. PERSISTENCE, currently ONE probe. What is written must be identical under both engines. Probe
       a save and a restore, not just a write, because the restore path is where a position type
       would leak into canonical state if it were going to.

    3. COVERAGE OF THE SEED. Eight commands over twelve rooms leaves rooms the battery never enters.
       Drive the battery across every room in the overlay, not a sample.

    4. INVENTORY and PROGRESSION are already at three probes each. Add only if the first three
       surface nothing; a fifth inventory probe is cheaper than the others and worth less.

contract_tests: >
    Additive to tests/test_engine_seam_differential.py. The existing 17 stay green unchanged.

    The battery already carries a test asserting "a battery that measures nothing is INCONCLUSIVE,
    not AGREED", and a test that plants a divergence to prove detection works. Those are the two that
    matter and they exist. What this order must add:

      commands_compared rises, and the RETURN states the new number against the old 8
      every aspect carries more than one probe, asserted structurally so a future narrowing is caught
      every room in the overlay is entered by at least one probe, derived from the overlay rather
      than from a hardcoded list, so a twelve-room Seed and a fifty-room Seed both stay honest

    That third one is the one to write carefully: derive from the overlay, never from a literal, or
    the next Seed silently reduces coverage while the count still looks fine.

verification_command: |
    cd codeforge
    make check

definition_of_done: >
    Every aspect carries more than one probe; the battery enters every room in the overlay;
    commands_compared is reported old-versus-new; the verdict is AGREED with a wider search, or
    BLOCKED with a divergence named. `make check` green over the whole instrument.

    If BLOCKED on a divergence, definition_of_done is the divergence report. That is the order
    succeeding, not failing.

calibration_required: >
    The battery's planted-divergence test already proves detection. What must be calibrated is the
    WIDENING, because a probe that runs but asserts nothing would raise the count and prove less:

      for at least one NEW probe in each widened aspect, break the thing it watches, prove that probe
      FAILS, restore, prove it passes. Paste each transition, naming the aspect.

    A count that went up without a probe that can fail is the dominant defect wearing a bigger number.

rollback: >
    Revert the commit. The battery is additive and nothing consumes its verdict programmatically.

approval_gates: >
    TWO, both real, both stopping.
    A DIVERGENCE is a founder decision.
    ANY CHANGE TO THE `Engine` PROTOCOL is a founder decision.

store_search_result: >
    Both tiers searched 2026-08-13; one tier logged is an incomplete search.
    Certified Tier (hardware-store/catalog/, 20 cards): `applied-once` is the nearest by shape, a
    durable exactly-once record, and it is about idempotency rather than differential comparison.
    Nothing in the Store compares two implementations against one contract.
    Working Shelf (codeforge/catalog/parts.yaml, 104 entries): `contract-jig` is the closest, a
    consumer-declares-what-it-reads check, and `transform_verifier` compares before-and-after of a
    transformation. Neither runs one battery against two implementations.

    Verdict: NO PART EXISTS. The differential battery is itself the mechanism, and if it survives a
    second Seed it becomes an extraction candidate rather than a consumer of one. Note that in the
    RETURN as a signal; the pull rule's bar is a second real consumer and there is not one yet.

parts_to_consume: >
    None. See store_search_result.

watch_for: >
    THE FAILURE MODE IS A BIGGER NUMBER THAT MEANS LESS. Raising commands_compared from 8 to 30 by
    adding probes that all exercise the same shallow path is worse than the 8, because it buys
    confidence without buying coverage. The calibration requirement exists to catch exactly that:
    every new probe must be shown able to fail.

    Second: derive room coverage from the overlay, never from a literal list. A hardcoded twelve
    would silently under-cover the second Seed, and the second Seed is the next order.

    Third: do not compare positions. The engines are supposed to differ there.

blast_radius: >
    Run before this allowlist was fixed.

      grep -rln 'Engine2DStub|Engine2D|engine_seam' tests/ kernel/ adapters/
      -> kernel/engine_seam.py, tests/test_engine_seam_differential.py. No adapter imports the seam.

      grep -rln 'commands_compared|AGREED|INCONCLUSIVE' tests/ kernel/
      -> tests/test_engine_seam_differential.py and kernel/engine_seam.py carry the battery. Five
         other modules share the AGREED/INCONCLUSIVE vocabulary (hubble/diagnosis, verify_smt,
         shelf/transform_verifier, shelf/diagnostic_runner, bench_protocol) and were checked
         individually: none reads this battery's verdict.

      grep -rn 'world_overlay|kernel.overlay' --include='*.py'
      -> kernel/engine_seam.py and the battery only. The overlay has exactly two readers.

      test_world_boundary: WORLD_MODULES must equal the world's import closure
      -> this order adds no module to kernel/world/, so the boundary is untouched. WO-S3 was blocked
         here because its order put overlay.py in kernel/world/; that is why kernel/overlay.py is
         where it is, and why this order adds no new module at all.

    What that surfaced: the seam has exactly two consumers and the overlay two readers, so the change
    is contained; and the boundary test that caught WO-S3 stays green because nothing new enters
    kernel/world/.

file_allowlist:
  - tests/test_engine_seam_differential.py     # ADDITIVE. the existing 17 stay green
  - kernel/engine_seam.py                      # battery probes only; the Protocol must NOT change
  - handoff/WO-S4/RETURN.md                    # NEW, explicitly authorised
```
