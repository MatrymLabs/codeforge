# Boss Specials -- the Telegraphed Attack

*The encounter mechanic the status system was built for (roadmap #4): a boss attack you can SEE
coming and answer. Composes three shipped systems -- `boss_phases` (the enrage), `afflictions` (the
consequence), and a wind-up telegraph. Design canon behind `parts/world/boss_specials.py`.*

## The loop

A boss fight now has three gears:

1. **Normal blows** -- the numbers flat, as ever.
2. **Enrage** (`boss_phases`) -- below 30% HP, a boss's blows redouble and the room hears it.
3. **Telegraphed special** (this) -- once enraged, the boss may spend a beat **winding up**: it
   announces the telegraph and lands *no blow that beat*. The next beat it **unleashes** -- a
   `mult`x blow whose affliction is **guaranteed** (it was telegraphed; it connects).

The wind-up beat is the point: a free beat for the hero to heal, ward, or run. The fight becomes a
conversation -- read the tell, answer it -- not a slugfest.

## Data-driven, opt-in

A boss declares a `special` in the seed (boss-tier only):

```yaml
special: {telegraph: "The guardian gathers dark power", mult: 2, cadence: 3}
```

- `telegraph` -- the wind-up line (defaults to a generic "gathers its power").
- `mult` -- the unleash blow multiplier (default 2), on top of any enrage scaling.
- `cadence` -- begin a wind-up on at most 1-in-N of the boss's enraged beats (default 3).

On unleash, the boss's existing `inflicts` (see [afflictions.md](afflictions.md)) is applied for
sure rather than rolled. Aethryn's authored bosses use it: the Black Hollow guardian draws the dark
in then unleashes a stun, and the Heart of Xil'nath guardian rears then unleashes a venom.

## Safety and state

The wind-up is a runtime flag (`charging`) on the NPC, cleared on unleash and on any recovery
(reassembly clears it). Only an **enraged** boss winds up, so trash and healthy bosses are untouched
-- the escalation is felt only in the back half of a real boss fight, exactly where it belongs.

## What it composes

This is the top of the encounter-depth stack: `boss_phases` gives the turn, `afflictions` gives the
consequence, and `boss_specials` gives the readable telegraph that ties them into a real mechanic.
Further specials (phase-3 thresholds, multiple telegraphs, area effects) hang off this same seam.
