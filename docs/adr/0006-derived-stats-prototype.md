# ADR-0006: Derived stats are formula-driven, and the current formulas are prototype

**Status:** accepted (the *mechanism* is accepted; the *numbers* are explicitly provisional)

## Context

The character score sheet shows five derived combat statistics -- ATK, DEF, EVA, MAG DEF,
ACC. An inspection of both this repo and the Evennia predecessor found the stat kernel and
the XP/JP progression math, but **no derived-stat formulas** anywhere. The sheet needs values
to render a real Engineer, and combat will eventually need them too.

Two risks pull against each other: rendering the Engineer needs numbers now, but inventing
"final" balance without design review would be a false claim of a decision that has not been
made.

## Decision

1. **Derived stats are computed by formula, from data, in one pure place** (`parts/derived.py`).
   The formulas take the six attributes plus the character level and return the five derived
   stats. They are pure and integer-valued, so every result is exact and pinned by the test
   twin -- a formula change is a visible, reviewable diff, never a silent drift.
2. **The current formulas are `prototype_balance_only`.** They are deterministic and
   reasonable, not balanced or final. The module and its card say so plainly; nothing presents
   them as tuned balance.
3. **Equipment and status modifiers are not folded in yet.** Derived stats are computed from
   base attributes and level alone. Stacking equipment/status modifiers is a later batch; the
   Evennia kernel's `ModifierStack` (additive/compound composition) is the salvage target.

## Consequences

- **The Engineer renders now,** with real numbers, without pretending they are final balance.
- **Balance is a one-file change.** When real balance is designed, only `parts/derived.py`
  changes; the sheet, the builder, and the view model are untouched.
- **Honest by construction.** The `prototype_balance_only` marker keeps the portfolio claim
  truthful: a computed stat is shown as computed, and a provisional formula is shown as
  provisional.

## Alternatives weighed

- **Render derived stats as zero / blank until balance is designed.** Honest, but an Engineer
  sheet of zeroes proves nothing about the character system. Rejected in favor of marked
  prototype formulas.
- **Invent "final" formulas now.** Fast, but it would present an unmade balance decision as
  made. Rejected -- readiness, not overclaim.
