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

file_allowlist:
  - kernel/world/exit_integrity.py          # NEW. the checker. yours to write
  - tests/test_exit_integrity.py            # NEW. contract tests, verbatim from this packet
  - kernel/world/seed.py                    # to ACCEPT the one_way declaration, load_rooms only
  - content/seeds/first-forge/rooms.yaml    # to DECLARE deliberate one-way passages
  - content/seeds/aethryn/rooms.yaml        # same
  - registry/designations/modules.json      # the completeness gate WILL demand the new module
  - Makefile                                # to wire the gate into `check`
  - handoff/CX-001/RETURN.md                # NEW. you are explicitly authorised to create this

contract_tests:       tests/test_exit_integrity.py
contract_test_policy: |
  ASSERTION-LOCKED. The file is given verbatim below. Create it exactly as written. You may add
  tests; you may NOT weaken, delete, or rewrite an assertion in it. If an assertion is WRONG,
  stop and say so in the RETURN with the reasoning. Do not edit it into agreement with your
  implementation, which is the failure mode the lock exists to prevent.

return_artifact:      handoff/CX-001/RETURN.md
return_authorisation: |
  EXPLICITLY AUTHORISED. Create it. It is required, not optional, and its extraction block may
  not be left blank ("none observed" is a valid answer; silence is not).
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

## The data contract, decided here so you do not have to guess it

A deliberate one-way passage is declared on the room the player leaves, naming the directions that
have no expected reverse:

```yaml
cellar:
  name: The Cellar
  desc: ...
  exits: {west: workshop}
  one_way: [west]        # declared: leaving west is a drop, there is no way back up
```

Rules the contract tests pin:

1. `one_way` is OPTIONAL. A room without it behaves exactly as today, so every existing seed loads
   unchanged and this is additive.
2. It lists DIRECTIONS, not destinations, and each must be a direction the room actually declares
   in `exits`. A `one_way` naming a direction the room does not have is a STALE declaration and the
   loader refuses it, because a declaration that protects nothing will silently rot.
3. It applies only to CANONICAL directions. Named entrances are never checked, never reported, and
   never need declaring.
4. Declaring one_way does not create the exit; it only says the reverse is intentionally absent.

`seed.py`'s `load_rooms` is the only loader you touch. Follow the shape `load_jobs` already uses:
default the field, type-gate it, then value-gate it, and fail loud with the room label in the
message.

## The contract tests, verbatim

Create `tests/test_exit_integrity.py` with exactly this content. The API it exercises IS the
contract: `inspect_exits(rooms) -> ExitVerdict`, carrying `.accidental`, `.declared`, `.clean` and
`.render()`.

```python
"""Test twin for kernel/world/exit_integrity.py -- no exit is one-way BY ACCIDENT.

Acceptance: a reciprocal pair is clean; a one-way passage DECLARED in the seed is clean and is
reported as declared, not hidden; named non-canonical entrances are ignored entirely.

Refusal (fail loud): an undeclared one-way canonical exit is ACCIDENTAL and reddens the gate, and
the report names the room, the direction and the destination so it can be acted on. A `one_way`
declaration naming a direction the room does not have is refused by the loader as stale.

The distinction this file exists to pin: the bar is NOT "every exit is reciprocal". Deliberate
one-way passage is a legitimate design. The bar is that a one-way passage is a DECISION on the
record, never an accident that strands a player.
"""

from __future__ import annotations

from kernel.world.exit_integrity import inspect_exits


def _rooms(**rooms):
    return {label: dict(spec) for label, spec in rooms.items()}


# --- acceptance ------------------------------------------------------------------------------


def test_a_reciprocal_pair_is_clean() -> None:
    verdict = inspect_exits(_rooms(
        a={"exits": {"north": "b"}},
        b={"exits": {"south": "a"}},
    ))
    assert verdict.clean
    assert verdict.accidental == ()


def test_every_canonical_direction_has_a_reverse_it_is_checked_against() -> None:
    pairs = [("north", "south"), ("east", "west"), ("up", "down"),
             ("northeast", "southwest"), ("northwest", "southeast"), ("in", "out")]
    for forward, back in pairs:
        verdict = inspect_exits(_rooms(a={"exits": {forward: "b"}}, b={"exits": {back: "a"}}))
        assert verdict.clean, f"{forward}/{back} should be a reciprocal pair"


def test_a_named_entrance_is_never_checked() -> None:
    """A region hub naming its settlements is this world's real topology, not a defect."""
    verdict = inspect_exits(_rooms(
        veridia={"exits": {"greenhold": "greenhold"}},
        greenhold={"exits": {}},
    ))
    assert verdict.clean
    assert verdict.accidental == ()


def test_an_exit_to_a_room_that_does_not_exist_is_not_reported_here() -> None:
    """A dangling destination is a different complaint with a different owner."""
    verdict = inspect_exits(_rooms(a={"exits": {"north": "nowhere"}}))
    assert verdict.accidental == ()


# --- the declaration -------------------------------------------------------------------------


def test_a_declared_one_way_is_clean() -> None:
    verdict = inspect_exits(_rooms(
        cellar={"exits": {"west": "workshop"}, "one_way": ["west"]},
        workshop={"exits": {}},
    ))
    assert verdict.clean


def test_a_declared_one_way_is_still_REPORTED_as_declared() -> None:
    """Clean is not the same as invisible. The world should be able to list its one-way drops."""
    verdict = inspect_exits(_rooms(
        cellar={"exits": {"west": "workshop"}, "one_way": ["west"]},
        workshop={"exits": {}},
    ))
    assert len(verdict.declared) == 1
    assert verdict.declared[0].room == "cellar"
    assert verdict.declared[0].direction == "west"
    assert verdict.declared[0].to == "workshop"


def test_declaring_one_direction_does_not_excuse_another() -> None:
    verdict = inspect_exits(_rooms(
        a={"exits": {"north": "b", "east": "c"}, "one_way": ["north"]},
        b={"exits": {}},
        c={"exits": {}},
    ))
    assert len(verdict.accidental) == 1
    assert verdict.accidental[0].direction == "east"


# --- refusal ---------------------------------------------------------------------------------


def test_an_undeclared_one_way_is_accidental() -> None:
    verdict = inspect_exits(_rooms(
        cellar={"exits": {"west": "workshop"}},
        workshop={"exits": {}},
    ))
    assert not verdict.clean
    assert len(verdict.accidental) == 1


def test_the_report_names_room_direction_and_destination() -> None:
    """A report you cannot act on is not a report."""
    verdict = inspect_exits(_rooms(
        cellar={"exits": {"west": "workshop"}},
        workshop={"exits": {}},
    ))
    rendered = verdict.render()
    assert "cellar" in rendered and "west" in rendered and "workshop" in rendered


def test_a_reverse_pointing_at_a_DIFFERENT_room_is_still_accidental() -> None:
    """b goes south, but not back to a. The player cannot retrace their step."""
    verdict = inspect_exits(_rooms(
        a={"exits": {"north": "b"}},
        b={"exits": {"south": "c"}},
        c={"exits": {}},
    ))
    assert not verdict.clean
    assert verdict.accidental[0].room == "a"
```

## After the tests pass

Only then adjudicate the real seeds. Run the checker over both, and for every case decide DEFECT
(repair the exit) or DELIBERATE (declare it), with the reasoning in the RETURN. The 67 aethryn
cases are dominated by one shape and may all be one decision; say which it is and why.

Wire the checker into `make check` so this cannot silently regress, and prove the gate can fail by
sabotage before you report it green.

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
