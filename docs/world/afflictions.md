# Afflictions -- Harmful Statuses the Player Suffers

*The mirror of the foe-side status effects (`brand` burn, `daze`) a player inflicts: the statuses a
foe inflicts on the PLAYER. This is the substrate a telegraphed boss special needs to actually
threaten a hero -- the prerequisite for richer encounter mechanics (roadmap #4). Design canon behind
`parts/world/afflictions.py`.*

## Two kinds

- **Damage-over-time** (`venom`, `bleed`, a lingering burn): saps `damage` HP each world beat for
  `ticks` beats. It **never fells the player on its own** -- HP is floored at 1, so an untended tick
  can't kill you; the foe's own blow lands the finishing hit. (The same discipline the foe-side burn
  keeps.) Re-applying refreshes the clock, it does not stack.
- **Daze**: a stun for `beats` world beats. While dazed, the player's offensive actions (`attack`,
  `use`) are refused with a clear line; a fresh daze extends to the longer duration, never shortens.

## Two clocks, deliberately

Player afflictions age on the **world beat** (`tick_afflictions`, wired beside `tick_burns` in the
engine tick), not the combat clock. So they progress whether or not the player keeps swinging -- a
poison ticks while you flee, a daze wears off while you wait. This mirrors how the foe-side burn ages
on the beat via `tick_burns`/`menace`.

## The source: an NPC's `inflicts`

A foe opts in with a seed field:

```yaml
inflicts: {status: venom, chance: 2, damage: 12, ticks: 4}   # a damage-over-time on a hit
inflicts: {status: daze,  chance: 3, beats: 1}               # a stun on a hit
```

On a landed blow (one that dealt damage), `maybe_inflict` rolls `chance` (1-in-N, default always)
and, on a hit, lays the affliction. `status: daze` stuns; any other name is a DoT of that name.
Aethryn's authored bosses use both: the Black Hollow guardian's dark blow dazes, and the Heart of
Xil'nath guardian's bite leaves a sapping venom.

## What this unblocks

Encounter depth (roadmap #4) -- boss phase-3 specials and telegraphed attacks -- can now inflict real
consequences on the player through this same `apply_dot` / `apply_daze` / `inflicts` surface, rather
than only scaling raw damage. `render_afflictions` gives a view a one-line summary of what ails the
hero when one is wired.
