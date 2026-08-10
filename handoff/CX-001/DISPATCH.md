# DISPATCH CX-001

```yaml
packet_id:            CX-001
title:                Leg 1C, exits resolve both ways
stream:               engine
owner:                Codex
reviewer:             Claude Code (re-runs every command independently)
merges:               founder
size:                 medium
flight:               M1 Aethryn Green
leg:                  1C
```

## Why this is yours and not mine

RELAUNCH names the lanes: Codex owns persistence, commands, events, transactions and integration;
Claude Code owns client, presentation, character flow and accessibility. Leg 1C splits on that
line. **The world graph is yours. The room's rendered shape is mine** (claimed as CC-002, touching
only the renderer and the seed's presentational fields).

We are not both editing `rooms.yaml`. If your fix requires changing an exit, say so in the RETURN
and I will stay out of that file until CX-001 lands.

## Goal

Leg 1C's bar is *"exits resolve both ways"*. Today they do not, and the number is measured, not
estimated.

## Measured baseline, reproduce it before you start

`CMD` A canonical exit is one of north/south/east/west/NE/NW/SE/SW/up/down/in/out. Named entrances
to sub-locations are NOT canonical and are deliberately excluded, because a region hub naming its
settlements is the topology this world genuinely has, and section 11 permits it.

```
first-forge: 13 rooms,  2 canonical exits with no matching reverse
    cellar   --west--> workshop   (no east back)
    workshop --down--> cellar     (no up back)

aethryn:     77 rooms, 67 canonical exits with no matching reverse
    greenhold  --out--> veridia   (no in back)
    elderwatch --out--> veridia   (no in back)
    riverbend  --out--> veridia   (no in back)
    sunmeadow  --out--> veridia   (no in back)
```

## Invariant

**A player who walks a canonical direction can walk back the way they came, or the world states
plainly why not.** One-way passage is a legitimate design choice (a chute, a collapsing bridge, a
one-way portal); an ACCIDENTAL one-way passage is a trap that strands a player.

The distinction is the whole packet: this is not "make every exit reciprocal". It is "no exit is
one-way by accident."

## The judgement I am NOT making for you

The 67 aethryn cases are dominated by one shape: a settlement exits `out` to its region, but the
region enters it by a NAMED exit (`greenhold: greenhold`) rather than `in`. That may be correct
modelling, in which case `out` should pair with the named entrance and the checker must understand
that, not the naive reverse.

Decide which it is, with evidence, and say so. If it is correct modelling, the deliverable is a
checker that understands the pairing and a world that passes it. If it is a defect, the deliverable
is the repair. **Do not silently make 67 edits to make a number go to zero.**

## Definition of done

```bash
cd /home/josh/Projects/MatrymLabs/codeforge
export PATH="$PWD/.venv/bin:$PATH"
make check
```

- A gate exists that fails on an ACCIDENTAL one-way canonical exit and passes on a DECLARED one.
  Its test twin proves both directions by sabotage; a gate that has not been shown to fail is not
  evidence.
- A deliberate one-way passage is expressible in the seed DATA, not in Python. The world is data.
- `make check` green, and the gate wired into it so this cannot silently regress.
- The RETURN records the adjudication of the 67, with the reasoning.

## Out of scope, explicitly

- `kernel/world/room_render.py` and the room's rendered hierarchy. That is CC-002, mine.
- The 63 non-canonical named entrances. They are legitimate topology, already checked, and are
  NOT to be "normalised" into compass directions.
- Any change to `contracts/native_seed*`. That contract was just ratified across two repos and a
  third change today would be churn.

## Rollback

`git revert` the merge commit. The checker is new, so nothing depends on it.

## EXTRACTION CONTEXT

```yaml
store_search_result: |
  NOT YET SEARCHED. Run the consume-first search for "graph traversal" and
  "bidirectional edge validation" BEFORE writing the checker, and log it. Rebuilding
  a certified part without a documented reason is a defect.

parts_to_consume: |
  None identified. The Store currently holds 6 parts, none graph-shaped.

watch_for: |
  A reverse-edge integrity check over a declared graph is the SECOND graph-validation
  shape in this codebase; kernel/world/callings.py already ships a cycle finder over
  the calling prerequisite graph (MOD-04.157). If your checker wants the same walk,
  that is `recurrence` and it is worth more than a clean report. Two independent
  consumers of one traversal is exactly what the pull rule fires on.
```
