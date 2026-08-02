# Keel Record: K2 - Death That Matters + Endgame That Completes

*Human Keel Record (see [../human_keel_doctrine.md](../human_keel_doctrine.md)). This documents the
second half of a critical-junction change to core combat feel. Per the doctrine, AI proposes and
Josh approves; **AI does not assign ownership**. The level-4 ownership claim and the "what I learned"
reflection below are left for Josh to complete when he can defend the design to an interviewer.*

- **Build:** a durability stake on lethal death + a raid/boss completion acknowledgment, both in
  `kernel/world/combat.py` (`DEATH_DURABILITY_TOLL`, `_death_gear_toll`, the `_kill_bounty` note),
  reusing `kernel/world/durability.py` and `kernel/world/lockouts.py`. No new module.
- **Ownership level claimed:** *(pending Josh's own claim; undeclared until he defends it)*

## Intent
Close K2, the survey's other combat-consequence gap: *"death has almost no stakes; endgame is a
farm, not a completion."* K1 gave a felled foe a real death; K2 gives the **player's** death a real
cost and makes a cleared boss/raid **read as completed**, not silently farmed. This is the deliberate
second slice named at the end of the K1 keel record ([foe-mortality.md](foe-mortality.md)).

## Problem
A lethal boss death today is almost a *convenience*: the hero teleports home, is fully healed, and
loses only 10% of carried coins - a fast-travel-and-heal with a small toll. And a raid, once its
weekly bounty is claimed, keeps paying the base drop with **no acknowledgment** that it is cleared,
so the endgame reads as an endless farm even though a completion state (the lockout) already exists.

## Constraints
- Smallest useful slice, reuse over new systems: the durability stake rides the EXISTING
  `durability.wear`/`mend` loop (an economy sink already in the game), and the completion signal
  reads the EXISTING weekly/daily lockout - no new persistence, no new module.
- Gentle and reversible: the gear toll is `mend`-able coin-sink wear, not XP loss or a de-level.
  Dying to trash stays a slap (the training-ground failsafe is untouched); only a **lethal** death
  (a real boss) batters gear. A bare hero takes no toll.
- Feel is a dial, not a law: `DEATH_DURABILITY_TOLL = 10` is a named tuning knob, Josh's to turn.
- Truth: the now-stale bounty comment ("the foe stays farmable because it reassembles") is corrected
  to K1's reality (it dies and respawns on its timer).

## Decision
Approved: **durability-on-death** for the "death matters" half over the harsher alternatives (XP debt
/ corpse run), because it reuses the economy, is reversible, and reads as a cost without punishing a
learning player. Applied only on the lethal path (`_fall_to_death`), so the training ground stays
safe. For the "endgame completes" half: **surface the existing lockout** - when a boss/raid's period
bounty is already claimed, the kill line acknowledges the clear ("... is already cleared today;
felled for the drop.") instead of returning nothing. K1's respawn timer + this acknowledgment + the
weekly lockout together make a raid read as *completed for the week*, not endlessly farmed.

## Alternatives considered
- **XP debt / de-level risk on death.** Rejected for this slice: impactful but reads as punishing in
  a MUD, and risks the "lose a level" feel-bomb. A reversible gear stake is the smaller safe
  experiment; XP debt can be revisited if playtesting wants a harsher endgame.
- **Corpse run (return to the death site to recover).** Deferred: a real feature (a corpse entity, a
  recovery interaction), its own slice. The gear stake delivers "death matters" now without it.
- **Apply the gear toll to the non-lethal failsafe too.** Rejected: the training-ground failsafe is
  the new-hero safety net; taxing it would punish learning. Boss death is where the stake belongs.
- **A dedicated raid-completion record/table.** Rejected as redundant: the weekly lockout already IS
  the completion state; it only needed surfacing, not a second source of truth.

## AI contribution
AI-assisted implementation of `DEATH_DURABILITY_TOLL` + `_death_gear_toll` and its wiring into
`_fall_to_death`, the completion acknowledgment in `_kill_bounty`, the stale-comment truth fix, and
the test twins in `tests/test_combat.py` (lethal death batters gear; the failsafe does not; a bare
hero takes no toll; a re-cleared boss is acknowledged), plus this record.

## Human modification (the keel)
Josh made the K1/K2 keel call ("do k1 then k2"). He holds the acceptance bar: death costs something
real but reversible, the training ground stays gentle, no de-level, and the endgame reads as
completed. The penalty magnitude and whether to extend the stake (XP debt, corpse run) are his dials.

## Tests / evidence
- `tests/test_combat.py`: a lethal death wears each worn piece by `DEATH_DURABILITY_TOLL` and names
  the stake; the non-lethal failsafe leaves gear at only the normal strike-wear (no death toll); a
  bare hero gets no gear message; a re-cleared boss surfaces "already cleared today" without a
  repeat bounty.
- Full suite green; `mypy --no-incremental` + `ruff` clean. No new module, no registry change.

## What Josh learned
*(For Josh to complete, per doctrine: e.g. explain why the toll rides the lethal path only, trace a
boss death from `_fall_to_death` -> `_death_gear_toll` -> `durability.wear` -> a `mend` bill, or argue
durability-on-death over XP debt for this game's feel.)*

## Final decision
Josh's, at the merge junction and of this record. The level-4 ownership claim is his to make on the
Career Board when he can defend the design; AI leaves it undeclared here.

## Uncertainty / review point
`DEATH_DURABILITY_TOLL` is a first tuning guess. The harsher stakes (XP debt, a corpse run) and a
dedicated raid-completion UI remain open, deliberately deferred as separate feel decisions. With K1 +
K2, the combat-consequence gap the survey named is closed: kills stick, and deaths and clears both
mean something.
