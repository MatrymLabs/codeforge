# Keel Record: Proactive NPCs (foes that strike first, on the world beat)

*Human Keel Record (see [../human_keel_doctrine.md](../human_keel_doctrine.md)). This documents a
critical-junction design decision and its build slice. Per the doctrine, AI proposes and Josh
approves; **AI does not assign ownership**. The level-4 ownership claim and the "what I learned"
reflection below are left for Josh to complete when he can defend the design to an interviewer.*

- **Build:** proactive/aggressive NPCs (`parts/aggression.py` + a shared blow resolution in
  `parts/combat.py` + a typed `StrikeFrame`), wired into the engine tick.
- **Ownership level claimed:** *(pending Josh's own claim; undeclared until he defends it)*

## Intent
Close the M5 (engine climb) slice the plan names as the genuine unbuilt extension of combat: NPCs
that **initiate**. Reactive combat already ships (a surviving NPC with an `atk` stat counters when
struck, `combat._counter_attack`, #94). Aggression is its other half: a foe that does not wait to be
hit. This makes the world feel alive and is the second real consumer of the typed event frames
shipped in the prior slice (#245).

## Problem
The engine has no clock but the player. `handle_command(session, text) -> str` is the only door;
every mutation today is driven by a player verb. "A proactive NPC" therefore reduces to one question:
*where does the heartbeat come from?* Naively this invites a background scheduler thread ticking NPCs
on a timer, which adds a second mutator path into canonical world state and lands squarely in the
ship's known distributed-race failure pattern ("assertions race; poll with a deadline").

## Constraints
- Smallest useful slice: one new part (`aggression`), one seed flag (`aggressive`), one shared blow
  resolver extracted from the existing counter path. No new thread, no second door into world state.
- Behavior preserved: with no seed setting `aggressive: true`, `menace()` returns `""` on every tick,
  so the whole existing game is byte-identical. The capability ships **dormant** until a game opts in.
- Architecture laws honored: the engine tick stays the only door (the player's command IS the beat);
  state stays canonical, mutated only by validated combat logic; a `StrikeFrame` is a projection
  request, never a mutation.
- Reuse over duplication: the open-strike and the counter share one resolver (`_resolve_npc_blow`),
  so a proactive foe inherits the Engineer's Emergency Repair reaction and the training-ground
  failsafe unchanged; only the opening verb differs ("lunges" vs "strikes back").
- One blow per beat: an aggressive NPC opens via the beat and is skipped by the counter path, so it
  never strikes twice in a single tick.
- Input validation fails loud: an `aggressive` NPC with `atk 0` (cannot land a blow) or `hp 0`
  (cannot be fought back) is a contradiction, refused at seed load.

## Decision
Approved: **fork A (piggyback the world-tick)** over fork B (a background scheduler thread). After a
player's command resolves, `handle_command` calls `aggression.menace(session)`; every aggressive NPC
sharing the room opens with a strike, appended to the tick's response. The capability ships dormant
(no shipped seed is aggressive yet); which game gets a proactive foe is a separate content decision
left to Josh. Fork B (a real timer thread for autonomous wandering/patrol) is a defensible future
step once the workload justifies it, but is not the smallest safe experiment.

## Alternatives considered
- **Fork B: a background scheduler thread ticking NPCs on a timer.** Rejected for this slice: adds a
  second mutator path into canonical state and concurrency the tests would have to poll for; a "stop
  for Josh" networking/execution change, not the smallest experiment. Revisit for true autonomy
  (NPCs that move and act with no player present).
- **Seed an aggressive NPC into `first-forge` now.** Deferred: that changes the shipped new-player
  experience (a content/keel decision). The engine capability ships proven-by-tests and dormant; the
  content choice is Josh's, on evidence, in a follow-up.
- **Reuse the `atk` stat alone as the aggression signal (no new flag).** Rejected: `atk > 0` already
  means "counters when struck." Overloading it would make every reactive foe suddenly aggressive.
  A distinct `aggressive` flag keeps reactive and proactive orthogonal and backward-compatible.
- **Leave the counter broadcast on the string bus; only the open-strike uses a frame.** Rejected as
  inconsistent: routing both through one `StrikeFrame` via the shared resolver makes combat a real
  second consumer of the typed bus with no test regressions (bystander text unchanged).

## AI contribution
AI-assisted implementation of `parts/aggression.py` (`menace`), the `_resolve_npc_blow` extraction +
`open_strike` in `parts/combat.py` (behavior-preserving refactor of `_counter_attack`), the
`StrikeFrame` in `parts/frames.py`, the `aggressive` seed field + loud validation in `parts/seed.py`,
the `_route`/`handle_command` beat wiring in `forge.py`, the test twins (`tests/test_aggression.py`,
plus `StrikeFrame` cases in `tests/test_frames.py` and seed-validation cases in `tests/test_seed.py`),
the Classification Registry filing `MOD-04.048`, and this record.

## Human modification (the keel)
Josh directed the M5 engine climb, chose proactive NPCs as the active slice after the reconciliation
confirmed it was the one genuinely unbuilt bench item, and made the fork-A-vs-B keel call (piggyback
the tick, no thread). He holds the acceptance bar: capability dormant until a game opts in, behavior
preserved for every existing seed, one blow per beat, and the failsafe unbroken.

## Tests / evidence
- `parts/aggression.py` twinned by `tests/test_aggression.py` (acceptance: opens on the beat, reaches
  through `handle_command`, exactly one blow per tick when attacked; refusal: reactive NPC never
  opens, another room is no threat, a callingless player is left alone; the failsafe restores a felled
  player). `StrikeFrame` acceptance + hostile refusal in `tests/test_frames.py`; seed-validation
  refusal (`aggressive` without `atk`/`hp`) + defaults in `tests/test_seed.py`.
- Behavior preserved: the full existing combat twin (`tests/test_combat.py`) passes unchanged,
  proving the `_counter_attack` refactor is a rename, not a rewrite.
- `make check` green: ruff + mypy --strict (298 files) + 1478 passed, coverage 93.59% >= 85% gate.
- Registry completeness CLEAN: `aggression` filed as `MOD-04.048`, twinned by `tests/test_aggression.py`.

## What Josh learned
*(For Josh to complete - the doctrine requires a human act beyond approval before a level-4 claim:
explain why the beat piggybacks the tick instead of a thread, trace an aggressive NPC's blow from
`handle_command` through `menace` to the player's HP, or name the failure mode the one-blow-per-beat
guard prevents.)*

## Final decision
Josh's, at the merge junction and of this record. The level-4 ownership claim is his to make on the
Career Board when he can defend the design; AI leaves it undeclared here.

## Uncertainty / review point
The slice ships dormant: no seed is aggressive yet, so the next decision is a content one (which game,
which room, which foe). True autonomy (NPCs that act with no player in the room, i.e. movement and
patrol) still needs fork B (a real clock) and is a separate keel decision. In the v0 training-ground
model every NPC reassembles on defeat, so an aggressive foe you "kill" reassembles and keeps coming;
that is intended for v0 and is where a persistent-death model would later change the feel.
