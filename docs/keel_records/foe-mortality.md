# Keel Record: Foe Mortality (a felled foe stays down and respawns; the dummy still reassembles)

*Human Keel Record (see [../human_keel_doctrine.md](../human_keel_doctrine.md)). This documents a
critical-junction change to core combat feel and its build slice. Per the doctrine, AI proposes and
Josh approves; **AI does not assign ownership**. The level-4 ownership claim and the "what I learned"
reflection below are left for Josh to complete when he can defend the design to an interviewer.*

- **Build:** `kernel/world/mortality.py` (the death/respawn policy), wired into the defeat path
  (`kernel/world/combat.py`) and the single presence seam (`kernel/world/npcs.py` `npcs_in`); a
  `reassembles` seed flag (`kernel/world/seed.py`); the training dummy flagged in `first-forge`.
- **Ownership level claimed:** *(pending Josh's own claim; undeclared until he defends it)*

## Intent
Close K1, the largest gap the game-bench survey named between "playable" and "AAA MMORPG": nothing
in the world ever read as *cleared*. Since the v0 training-ground model, **every** foe reassembled at
full health the instant it fell (`combat.land_hit` set `hp_now = hp` unconditionally), so a kill read
like sparring. This is the exact follow-up the proactive-NPCs keel record anticipated ("that is where
a persistent-death model would later change the feel").

## Problem
The reassemble-on-defeat behavior is *identity* for one entity: the training dummy that "reassembles
itself" is named in `CLAUDE.md` and the respawn philosophy. So K1 is not "turn off reassembly" - it
is "give a **mortal** world foe a real death and a respawn, while keeping the dummy's instant
reassembly." Two design hazards: (1) a per-foe respawn timer via the scheduler would add tens of
thousands of jobs at world-generation scale; (2) a "dead" foe must vanish from *every* presence path
(render, target-trace, aggression, roaming) or a corpse becomes attackable in one code path.

## Constraints
- Smallest useful slice: one new pure part (`mortality`), one seed flag (`reassembles`), one filter
  at the single presence seam. No new thread, no scheduler jobs, no second door into world state.
- Scales to the generated world: **lazy** respawn. A felled mortal foe carries a `dead_until` beat;
  `npcs_in` skips it and revives it in place the first time presence is queried on/after that beat.
  One dict field and an integer compare per foe - no timer per creature.
- One seam: `npcs_in` is the sole foe-presence path (render, `trace_npc`, `aggression.menace`,
  `roaming.roam` all route through it). Filtering there covers every path; verified no combat/
  aggression/threat/party code scans `NPCS` for co-location directly.
- Behavior preserved where it must be: the training dummy (and anything a seed marks `reassembles`)
  is byte-identical - it collapses and stands right back up. Peaceful NPCs never enter the defeat
  path, so they never carry `dead_until`.
- Fails loud: a `reassembles` flag on an uncombatable (hp 0) foe, or a non-bool value, is refused at
  seed load - the same discipline as `aggressive`/`lethal`.
- One source of wording: `mortality.defeat_clause` gives the room and every actor path (`attack`,
  the two ability finishers) one phrase, so "slain" vs "reassembles" can never drift between paths.

## Decision
Approved: **lazy, tier-timed mortality** over (a) a scheduler job per foe and (b) leaving reassembly
universal. Default is mortal: a felled foe dies, drops from its room, and revives at full after
`RESPAWN_BEATS[tier]` (normal 15 / elite 40 / boss 120 / raid 300 beats, a starting curve to tune).
The training dummy is the deliberate exception via `reassembles: true`. Bosses now respawn on a long
timer rather than reassembling instantly; the daily/weekly bounty lockouts are unaffected (they gate
on the calendar, not the boss's presence), so endgame farming still works - it just respects a
respawn, which is *more* MMO-shaped. The player-death stakes half (K2) is the next, separate slice.

## Alternatives considered
- **A scheduler job per felled foe.** Rejected: correct but tens of thousands of live jobs at world
  scale. The lazy `dead_until` + compare gives the same behavior with a dict field and no registry.
- **Keep bosses reassembling (only trash dies).** Rejected: a boss that reassembles the instant it
  falls is the sharpest "sparring, not a kill" case. A long boss timer + the existing bounty lockout
  is both more MMO-shaped and simpler (one rule, tier-scaled) than a boss carve-out.
- **A visible corpse ("the corpse of X lies here") during the dead window.** Deferred: pure flavor;
  absence already reads as "cleared." A corpse render is an easy additive follow-up if wanted.
- **Wall-clock respawn timers.** Rejected: the engine's only clock is the world beat (one command);
  a beat timer stays deterministic and testable, consistent with the scheduler and zone reset.

## AI contribution
AI-assisted implementation of `kernel/world/mortality.py` (`fell`/`is_dead`/`respawn_delay`/
`reassembles`/`defeat_clause`), the defeat-path rewire and shared `defeat_clause` in
`kernel/world/combat.py` + the two ability finishers in `kernel/world/abilities.py`, the aliveness
filter in `kernel/world/npcs.py` `npcs_in`, the `reassembles`/`dead_until` `Npc` fields + loud
loader validation in `kernel/world/seed.py`, the `first-forge` dummy flag, the respawn-policy catalog
update in `kernel/world/respawn.py`, the test twin `tests/test_mortality.py` + updated combat/seed
tests, and this record.

## Human modification (the keel)
Josh made the K1/K2 keel call ("do k1 then k2") after being shown the game-bench read, choosing to
change the world's combat consequence while explicitly preserving the training-dummy identity. He
holds the acceptance bar: the dummy still reassembles, existing behavior preserved for peaceful NPCs,
the change scales to the generated world, and death is a respawn (not a permanent removal).

## Tests / evidence
- `tests/test_mortality.py` (acceptance: a felled mortal foe is absent until its tier beat, then
  revives at full in place; refusal: a `reassembles` foe never dies; boundary: the exact respawn
  beat; hostile: unknown tier, never-felled foe, transient statuses shed on defeat).
- `tests/test_seed.py`: `reassembles` loads through, is absent by default, and is refused loud on an
  hp-0 foe or a non-bool value.
- `tests/test_combat.py`: updated to the new law - the dummy still reassembles; mortal foes are
  "slain"; the bounty-lockout tests model a respawn (`_respawn`) between re-kills.
- Behavior preserved: full suite green; `mypy --no-incremental` (697 files) + `ruff` clean.

## What Josh learned
*(For Josh to complete, per doctrine: e.g. explain why respawn is lazy at the presence seam instead
of a scheduler job, trace a felled wolf from `land_hit` -> `mortality.fell` -> `dead_until` ->
`npcs_in` skipping it -> lazy revival, or name the failure mode the single-seam filter prevents.)*

## Final decision
Josh's, at the merge junction and of this record. The level-4 ownership claim is his to make on the
Career Board when he can defend the design; AI leaves it undeclared here.

## Uncertainty / review point
The `RESPAWN_BEATS` curve is a first tuning guess (a beat is one command), not a measured value; it
is the obvious dial to adjust from play. K2 (player-death stakes: XP debt / durability-on-death /
corpse run, and a true raid completion state) is the deliberate next slice, kept separate because it
changes the *player's* consequence, not the foe's. A visible corpse during the dead window is an
optional flavor follow-up.
