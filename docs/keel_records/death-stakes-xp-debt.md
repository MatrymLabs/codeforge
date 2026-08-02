# Keel Record: K5 - XP Debt on a Lethal Death (the sharper stake)

*Human Keel Record (see [../human_keel_doctrine.md](../human_keel_doctrine.md)). This documents a
critical-junction change to progression/combat feel. Per the doctrine, AI proposes and Josh approves;
**AI does not assign ownership**. The level-4 ownership claim and the "what I learned" reflection
below are left for Josh to complete when he can defend the design to an interviewer.*

- **Build:** `apply_xp_debt` in `kernel/world/progression_awards.py` (the single deliberate XP
  drain), wired into the lethal-death path in `kernel/world/combat.py` alongside the K2 gear toll.
- **Ownership level claimed:** *(pending Josh's own claim; undeclared until he defends it)*

## Intent
K5, the sharper of the death-stakes options the game-bench re-rack named. K2 made a lethal death cost
coins + gear; K5 adds the classic MMO stake: **losing progress toward your next level** on a real
death. Josh approved K3-K5 together; this is the K5 slice.

## Problem
Even after K2, a lethal boss death costs only coins + gear wear. The progression axis - the thing a
player most cares about at the endgame - is untouched: dying to a boss never sets you back on the
climb at all. The classic answer (an XP debt) is also the classic feel-bomb if done wrong: losing a
*level* on death reads as punishing and can spiral. The design question is "a real setback that is
never a de-level."

## Constraints
- NEVER de-level. The debt is a fraction of the XP earned INTO the current level only, floored at
  the level's threshold, so a death costs progress toward the *next* level and never drops the one
  you have. `award_xp`'s "never drains" law is preserved for every reward path; `apply_xp_debt` is
  the ONE deliberate drain, named as such in the card.
- Reversible: what a death costs, play re-earns. No permanent loss.
- Lethal path only. Like the K2 gear toll, the XP debt rides `_fall_to_death` (a real boss);
  the training-ground failsafe (`_fall_and_recover`) stays gentle so a learning hero is never taxed.
- Feel is a dial: `XP_DEBT_FRACTION = 0.10` is a named tuning knob, Josh's to turn (or zero out).
- Lives with the leveling engine: `apply_xp_debt` sits in `progression_awards` (which owns the
  XP/level curves), not in combat, so the math has one home and combat just calls it.

## Decision
Approved: **a fractional XP debt on lethal death, floored at the current level**. On a boss death the
hero loses `XP_DEBT_FRACTION` of their progress into the current level (never below its threshold),
reported in the fall message ("The fall sets your progress back N XP (your level holds)."). A death
now stakes all three axes - purse, gear, progress - while keeping the hero's hard-won levels intact.

## Alternatives considered
- **Lose a whole level / drop below the threshold.** Rejected: the punishing feel-bomb; a death
  spiral where a weaker hero keeps dying and sinking. The floored-fraction gives a real setback with
  a hard floor at the current level.
- **A corpse run (return to the death site to recover the lost XP).** Deferred: a bigger feature (a
  corpse entity, a recovery interaction, a timer). The fractional debt delivers "progress matters"
  now; a corpse run can layer on later as its own slice.
- **XP debt on every death (including the failsafe).** Rejected: the training ground is the
  new-hero safety net; taxing progress there punishes learning. Boss death is where the stake belongs.
- **Debt as a fraction of TOTAL xp.** Rejected: at high level total-xp is enormous, so a flat
  fraction would erase hours. Fraction-of-current-level-progress scales fairly across the curve.

## AI contribution
AI-assisted implementation of `XP_DEBT_FRACTION` + `apply_xp_debt` in `progression_awards.py`, the
wiring + fall-message line in `combat._fall_to_death`, the card note on the deliberate-drain
exception, and the test twins (`tests/test_progression_awards.py` unit cases + `tests/test_combat.py`
integration: a lethal death sets progress back without de-leveling, the failsafe costs no XP).

## Human modification (the keel)
Josh approved K3-K5. He holds the acceptance bar: a real death sets you back but NEVER de-levels, the
training ground stays gentle, and the setback is reversible. The debt fraction and whether to combine
all three stakes (coins + gear + XP) or dial some back are his tuning decisions.

## Tests / evidence
- `tests/test_progression_awards.py`: the debt costs a fraction of current-level progress; floors at
  the level threshold (no de-level); a level-1 hero floors at 0; a zero fraction is a no-op.
- `tests/test_combat.py`: a lethal death names the XP stake and keeps the level while cutting
  progress (never below the floor); the training-ground failsafe costs no XP.
- Full suite green; `mypy --no-incremental` + `ruff` clean. No new module.

## What Josh learned
*(For Josh to complete, per doctrine: e.g. explain why the debt floors at the current level's
threshold, trace a boss death from `_fall_to_death` -> `apply_xp_debt` -> the floored setback, or
argue fraction-of-current-progress over fraction-of-total-xp for a fair curve.)*

## Final decision
Josh's, at the merge junction and of this record. The level-4 ownership claim is his to make on the
Career Board when he can defend the design; AI leaves it undeclared here.

## Uncertainty / review point
Three stacked stakes (coins + gear + XP) on one death may be more than the game wants; each is a
named dial and any can be softened from playtesting. A corpse run (recover the lost progress at the
death site) is the deliberate deferred follow-up if a sharper, more MMO-flavored death is wanted.
