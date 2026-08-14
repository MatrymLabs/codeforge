# RETURN WO-S4

**Status:** RE-VERIFIED WITH FINDINGS. Not BLOCKED: no divergence was found. Not clean either.

**Written by Claude Code, the reviewer, not the implementer.** WO-S4 was implemented and merged as
codeforge #951 (`7834a29c`) and no Bench Report was ever filed, so the order landed without a record
and `.ai/WORKBENCH.md` still listed it as owed. This is the Verification Duty discharged after the
fact and the record closed. The implementer's own account of the work does not exist; what follows
is what I measured myself.

## Verdict on the order's own terms

The order asked for one of two complete outcomes: a divergence named precisely, or a battery
demonstrably wider that still finds none.

**Outcome: the second, qualified.** The battery is genuinely wider. It is not as much wider as its
own headline number says, and the qualification is the finding.

## What was measured, this session, against origin/main

```
CMD: git rev-list --count HEAD..origin/main          -> 0   (HEAD 0d5f1e4e)
CMD: cd codeforge && make check
     ruff / mypy         All checks passed! / no issues found in 812 source files
     pytest              5245 passed, 54 skipped in 158.76s
     coverage            93.41% against an 85% floor
     MAKE EXIT=0
```

Battery, measured directly rather than read from the diff:

```
verdict          : AGREED
commands_compared: 14        (was 8: the order required old-versus-new and here it is)
aspects_covered  : inventory, progression, permission, persistence, coverage
divergences      : ()
probes per aspect: inventory 3, progression 3, permission 4, persistence 3, coverage 1
```

Against the order's `the_widening`, ranked as it ranked them:

| widening asked for | before | after | met |
|---|---|---|---|
| 1. permission, "currently ONE probe" | 1 | 4 | yes |
| 2. persistence, "currently ONE probe" | 1 | 3 | yes |
| 3. coverage of the Seed, every room | none | 1 probe, all 12 rooms | yes, and derived |
| 4. inventory and progression, only if the first three surface nothing | 3, 3 | 3, 3 | correctly left alone |

Room coverage is derived from the overlay (`tuple((room, room) for room in sorted(overlay))`), not
from a literal list. That was the order's third `watch_for` and it was honoured.

## FINDING 1, material: ten of fourteen probes cannot fail

The order's own `watch_for` names the failure mode it feared: *"THE FAILURE MODE IS A BIGGER NUMBER
THAT MEANS LESS ... every new probe must be shown able to fail."*

So I tested exactly that, and not the way the suite does. An engine controls precisely three things
through the `Engine` Protocol: `place`, `room_of`, and `carry_limit`. I sabotaged each in turn and
recorded, per probe, whether its observed output changed.

```
aspect       probe                         room_of   carry_limit  place
inventory    carry_limit                   .         CATCH        .
inventory    purse_renders                 .         .            .
inventory    module_is_position_free       .         .            .
progression  xp_for_level                  .         .            .
progression  jp_for_level                  .         .            .
progression  calling_gate                  .         .            .
permission   rank_denies_admin             .         .            .
permission   player_denies_teleport        .         .            .
permission   wizard_denies_grant           .         .            .
permission   workshop_barrier_denies_wizard CATCH    .            .
persistence  grant_key_shape               .         .            .
persistence  save_restore_casefile         CATCH     .            CATCH
persistence  gameplay_save_preserves_auth  .         .            .
coverage     all_overlay_rooms             CATCH     .            CATCH

probes that cannot fail for ANY protocol-legal sabotage: 10 of 14
```

**Effective battery: 4 probes, not 14.** Per aspect: inventory 1 of 3, permission 1 of 4,
persistence 1 of 3, coverage 1 of 1, and **progression 0 of 3.**

The battery carries a test named
`test_the_engines_genuinely_differ_below_the_seam`, whose docstring calls comparing a thing to
itself *"this Workshop's dominant defect shape."* Ten of its own probes do that: they read a value
the core computes without consulting the engine, under two engines, and compare it to itself.

**Why this is a finding and not a failure.** The order's calibration bar was *"at least one NEW
probe in each widened aspect"* shown able to fail. Permission has one and persistence has one, so
the implementer met the contract as written. The contract was the thing that was too weak, and it
was too weak in the exact way its own `watch_for` predicted. Progression is the sharpest case: its
three probes satisfy the structural assertion `probes[aspect] > 1` while not one of them can produce
a divergence.

**What the 10 are worth, stated fairly rather than dismissed.** They are regression guards. If the
core were later changed to consult position when computing XP or rendering a purse, they would catch
it. That is real value. It is not evidence of agreement today, and the difference matters: AGREED
over 14 reads as a broader search than AGREED over 4.

**Expected correction, not applied here.** Either make progression falsifiable by driving it through
a path that reaches the engine, or record in the battery which probes are falsifiable and report
that number beside `commands_compared`. The second is cheaper and more honest, and it would have
surfaced this on the day. Not my call and not my order: this is the reviewer's finding, returned
rather than repaired.

## FINDING 2, minor: a hardcoded 12 the order warned about

`tests/test_engine_seam_differential.py`, in
`test_widened_battery_has_multiple_probes_per_aspect_and_covers_overlay`:

```python
assert len(overlay) == 12
```

The order's `watch_for`: *"derive room coverage from the overlay, never from a literal. A hardcoded
twelve would silently under-cover the second Seed."* The coverage assertion itself IS derived, so
the substance is honoured; this extra line pins the Seed's size to a literal in the same test. It
will not under-cover the second Seed, because the test loads `first-forge` explicitly, but it is the
warned-against shape and it will need deleting when the second Seed lands. Cheap to fix, no behaviour
depends on it.

## FINDING 3, cosmetic

Same test imports `kernel.engine_seam` twice by two mechanisms, once as
`__import__("kernel.engine_seam", fromlist=["_battery"])._battery()` and four lines later as
`import kernel.engine_seam as seam`. The string-magic form is redundant. No defect, reads as
leftover.

## Approval gates: neither tripped

- **A divergence is a founder decision.** None found. The `Engine` Protocol was not changed;
  `place`, `room_of` and `carry_limit` are the same three members.
- **Out of scope respected.** No renderer, no spatial comparison, no second Seed, and neither engine
  was changed to make a probe pass.

## FINDING 4: the gate is not deterministic under load

`make check` went red once during this verification and green on a clean re-run. Both runs, same
tree, same commit:

```
run 1 (a second make check running concurrently on the same host)
  E   TimeoutError: timed out
      assert b"Build.Report" in built.encode() and b"1 passed" in built.encode()
  MAKE EXIT=2

run 2 (nothing else running)
  5245 passed, 54 skipped in 180.72s
  MAKE EXIT=0
```

Reported rather than written off, because "it passed the second time" is how a real intermittent
failure gets filed as noise. The test shells out to a build and asserts on its captured output
against a fixed timeout, so it measures the host's spare capacity as well as the property it names.
On this host, one Pi 5 running two gates, that is enough to flip it.

Not this order's doing and not in its allowlist. Filed as a Known Fault below and worth its own
order: a timeout tuned to an idle machine is a gate that reports on the machine.

## Known Faults

- **KF-S4-1** Ten of fourteen battery probes cannot fail. Finding 1.
- **KF-S4-2** `assert len(overlay) == 12` pins the Seed size to a literal. Finding 2.
- **KF-S4-3** A build-shelling test times out under concurrent load. Finding 4. Reproduced once,
  green on a quiet host, so it is intermittent rather than broken.

## Principal Engineer decisions needed

**D-7. Does Leg 2C close on a battery of 4 falsifiable probes?** The order's stated invariant was
"AGREED is only as strong as the battery that produced it." By that standard the honest number is
4, not 14. Close 2C, or dispatch the progression widening first.

**D-8. Does the second Seed still come next?** The ruling ordered battery-then-population precisely
so a narrow battery would not make a second Seed prove nothing. Finding 1 says the battery is
narrower than its count. The same reasoning that put the battery first argues for fixing progression
before widening the world.

## Reusable Part signals

```yaml
reimplemented: >
  none observed.
recurrence: >
  A count that rises while the thing counted stays weak. Third sighting: commands_compared 8 to 14
  with 10 unfalsifiable probes here; the language census reporting six languages measured in one
  repository; the research register asserting 55 findings over 26 rows. Same shape, three domains.
generalizable: >
  Yes, and narrowly: a FALSIFIABILITY AUDIT. Given a set of probes and the levers a subject can
  actually move, report which probes cannot change their answer for any legal input. It is the
  script in this report's Finding 1 and it took nine lines. It would have caught all three
  recurrences above. Not a Part yet: one real consumer, and the pull rule wants two.
friction: >
  The order's calibration bar asked for "at least one NEW probe in each widened aspect" able to
  fail. That is satisfiable by a battery that is 71% decorative, and it was. A bar stated per-probe
  rather than per-aspect would have caught it at authoring time, in the order I wrote.
```
