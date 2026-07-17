# Keel Record: The arch previews a built game (read-only)

*Human Keel Record (see [../human_keel_doctrine.md](../human_keel_doctrine.md)). Per the doctrine,
AI proposes and Josh approves; **AI does not assign ownership**. The level-4 ownership claim and the
"what I learned" reflection below are left for Josh to complete when he can defend the design.*

- **Build:** `@arch preview <seed>` (`parts/foundry.preview_seed`) - looking through the arch at a
  built game, read-only, without entering it.
- **Ownership level claimed:** *(pending Josh's own claim; undeclared until he defends it)*

## Intent
Advance the proving-ground loop (log in -> workshop -> arch -> play the game you built) by its
smallest honest next rung. A scout found the loop's build half already shipped (`@forge` scaffolds
parts; `@arch` is the owner-gated, read-only security boundary). The unbuilt half is "enter and
play," which is blocked by a deliberate architecture wall (seed selection is frozen at import). This
slice ships the first rung of that half without touching the wall: the arch can *look at* a built
game before any later rung wires *entering* one.

## Problem
`@arch` today only lists forged source-file candidates. There is no way, from inside the MUD, to see
what a built game *is* - the world you would wake in. The full "walk through and play" needs a
runtime world-entry mechanism (currently `seed.SEED_NAME` is read once at import, world dicts are
module-level). Doing that now would be a core-architecture change. The problem was to deliver visible
loop progress without unfreezing that wall.

## Constraints
- Read-only projection: load another seed's data and render it; **never** mutate world state or swap
  the running seed (architecture law 1: state is canonical, renderers never mutate). A test pins that
  `world.START_ROOM` is unchanged after a preview.
- Reuse the shipped security boundary: `@arch` stays ADMIN / `min_rank="owner"`; a player is denied
  at the tick.
- Honest labelling: the output says plainly it is a preview, not entering - "play what you built is a
  later rung of the loop." No false claim that you can play yet.
- No new module or command designation: extend the already-filed `foundry` (MOD-10.020) and the
  already-filed `@arch` (CMD-10.021), so the registry completeness gate stays satisfied.
- Critical-junction rule: the *runtime world-entry* decision is explicitly deferred, not made here.

## Decision
Approved (read-only arch preview) over three heavier alternatives. Add `preview_seed(seed_name)` to
`parts/foundry.py`: it loads a seed's `rooms.yaml`/`npcs.yaml` read-only, finds the START_ROOM
(`next(iter(rooms))`, the engine's own definition), and renders the room you would wake in, its
exits, the room count, and the inhabitant roster. `arch_command` routes `preview <seed>` to it; bare
`@arch` still lists forged candidates (behavior preserved).

## Alternatives considered
- **Design runtime world-entry now** (session-scoped world swap). Deferred: a core-architecture
  change to the frozen-at-import world model; deserves its own keel decision, not a tail-end build.
- **Wire `cast play`** (launch an exported cast subprocess). Deferred: subprocess I/O routing into
  the session is a larger surface than the first honest rung needs.
- **Pause slice 3 entirely.** Rejected in favor of shipping the small, safe, visible rung now and
  documenting the deferred decision.

## AI contribution
AI-assisted implementation of `parts/foundry.preview_seed`, the `arch_command` routing, the `@arch`
summary update in `forge.py`, five tests in `tests/test_foundry.py` (acceptance: shows the start
room/inhabitants of a real seed; refusal: unknown seed, empty name lists installed; a projection
never swaps the world; owner-gated at the tick), and this record.

## Human modification (the keel)
Josh directed the M5 engine climb, and at the slice-3 junction chose the read-only arch preview over
designing runtime world-entry now, wiring `cast play`, or pausing. He holds the keel decisions: that
the loop advances by its smallest honest rung, that the frozen world model is not unfrozen yet, and
the acceptance bar (read-only, owner-gated, honestly labelled).

## Tests / evidence
- `parts/foundry.py` + `tests/test_foundry.py` (5 new tests); `make check` green: ruff + mypy
  --strict (296 files) + 1462 passed, coverage 93.57% >= 85%.
- Registry completeness CLEAN (no new module/command; foundry MOD-10.020 and @arch CMD-10.021 already
  filed and twinned).
- Runtime smoke through the tick: `@arch preview first-forge` renders The Cold Forge + its roster; no
  name lists installed games; an unknown game is refused; a `player` is denied at the arch.

## What Josh learned
*(For Josh to complete - the doctrine requires a human act beyond approval before a level-4 claim:
explain why the preview loads a fresh rooms dict instead of reading the live world, name the wall
that keeps "enter and play" a separate slice, or trace `@arch preview` from the verb to the START_ROOM.)*

## Final decision
Josh's, at the merge junction and of this record. The level-4 ownership claim is his to make on the
Career Board when he can defend the design; AI leaves it undeclared here.

## Uncertainty / review point
The deferred decision is the real one: how to *enter* a built game at runtime without breaking the
"seed frozen at import, world dicts module-level, state canonical" model. Candidate directions for a
future keel decision: a session-scoped world overlay, or promoting the `cast` export + subprocess
boot into an in-MUD launch. This slice deliberately stops at "look, don't enter."
