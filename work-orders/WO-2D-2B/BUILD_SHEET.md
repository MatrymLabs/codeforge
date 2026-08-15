# WO-2D-2B BUILD SHEET

**Repo:** `codeforge`

## Scope

`codeforge` only. Split the Engine CONTRACT out of `kernel/engine_seam.py` into the World Package,
so the world can consume it without reaching into the platform. **The differential harness does not
move.**

## Invariant

**The world boundary holds and behaviour does not change.** `world_boundary_gaps()` returns empty,
`world_import_violations()` returns `{}`, and every existing test passes unedited. This order moves
declarations between files; it changes no logic.

```yaml
packet_id:            WO-2D-2B
title:                The Engine contract belongs to the game, not the workshop
stream:               engine
repository:           codeforge
goal: >
  Principal Engineer ruling 2026-08-15, option A. WO-2D-2 put the engine in the path correctly and
  was blocked by a boundary it could not satisfy: `kernel/world/session.py` imported
  `kernel/engine_seam.py`, and kernel/world_boundary.py forbids the World Package (Layer 2) from
  importing the platform (Layer 1). The gate said so exactly:

    {'session': ['engine_seam']}
    'session: imports platform part(s) engine_seam'

  THE ORDER CAUSED THAT. WO-2D-2 told the Bench to consume the Protocol from engine_seam, and the
  author did not check the layer. The Bench could not have satisfied both instructions.

  The ruling: the game's notion of where a player is belongs to the GAME. So the contract moves
  into the World Package and the harness that TESTS the seam stays in the platform, which is what
  each of them actually is.

  Move to a new `kernel/world/engine.py`:
    NodePosition   (engine_seam.py:33)   what Engine0D.place() returns
    Engine         (engine_seam.py:55)   the Protocol: place, room_of, carry_limit
    Engine0D       (engine_seam.py:82)   the default the world runs on

  Leave in kernel/engine_seam.py: ChunkPosition, Engine2DStub, Engine2D, Divergence,
  AspectFalsifiability, SeamVerdict, the battery, the saboteurs, falsifiable_probes and
  run_differential. Those exist to MEASURE the seam, which is workshop work.

  engine_seam.py then imports the three from kernel.world.engine. That direction is explicitly
  allowed: world_boundary.py's own docstring says the platform "is built ON the world (it imports
  the world to catalog and audit it)".

out_of_scope: >
  Do NOT change any logic. Not a method body, not a default, not a message. This is a move.
  Do NOT move ChunkPosition or Engine2D. They are used only by the differential today, and moving
  a thing "while you are there" is how a move becomes a rewrite nobody can review.
  Do NOT edit kernel/world_boundary.py. The rule is correct and is the reason this order exists.
  Do NOT edit tests/test_engine_seam_differential.py. If it breaks, the move changed something and
  that is a finding.

file_allowlist:
  - kernel/world/engine.py                  (new)
  - kernel/engine_seam.py
  - kernel/world/session.py
  - tests/test_engine.py                    (new, if the moved contract needs its own twin)
  - registry/designations/modules.json      (a new module needs its designation)

blast_radius: |
  $ git grep -ln "engine_seam" -- '*.py' | grep -v build/
  kernel/engine_seam.py
  tests/test_engine_seam_differential.py

  TWO files, one of which is the module itself. The contract has almost no consumers today, which
  is exactly why this is cheap now and would not be later.

  $ grep -n "from kernel.engine_seam import" <WO-2D-2 branch>:kernel/world/session.py
  14: from kernel.engine_seam import Engine, Engine0D      <- the violation

  Every CARD in kernel/world/ carries a test twin by convention. A new world module needs one, and
  a designation row, or the registry completeness gate will refuse it.

boundary: >
  This order OWNS the three declarations being moved, the two files they move between, and
  session.py's import line. It does NOT own the differential harness, the battery, the probes or
  the saboteurs; WO-2D-3 owns those.

  It does NOT own kernel/world_boundary.py. If the boundary still reports a violation after the
  move, that is a finding about the design and a BLOCKED report, never a reason to edit the rule
  that caught it.

preconditions: >
    CHECK: file kernel/engine_seam.py contains class Engine
    CHECK: file kernel/world_boundary.py exists
    CHECK: file kernel/world/engine.py absent

    Behavioural:
      export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
      make proto && make check                                    exit 0 before you start
      NOTE: WO-2D-2's branch is NOT merged and must not be merged before this lands. This order
      prepares the layer so that work can land without violating the boundary.

contract_tests:
  - tests/test_world_boundary.py
  ASSERTION-LOCKED and it is the deciding gate. It currently PASSES on main and must still pass
  after the move, and it must pass with WO-2D-2's session.py change applied on top.

definition_of_done:
  - "kernel/world/engine.py exists and holds NodePosition, Engine and Engine0D, with a CARD
     docstring naming its purpose, per the repository convention."
  - "kernel/engine_seam.py imports those three from kernel.world.engine and re-exports them, so
     `from kernel.engine_seam import Engine` keeps working for anything that already does it."
  - "kernel/world/session.py imports Engine and Engine0D from kernel.world.engine."
  - "THE DECIDING TEST: `python -c \\"from kernel.world_boundary import world_boundary_gaps,
     world_import_violations; print(world_boundary_gaps(), world_import_violations())\\"` prints
     an empty list and an empty dict, WITH session.py importing the engine. If it does not, the
     split did not put the contract on the right side."
  - "tests/test_engine_seam_differential.py passes UNEDITED. It is the proof the harness still
     works against a contract that lives somewhere else."
  - "A test twin for the new module, per the CARD convention, and a designation row so the registry
     completeness gate is satisfied."
  - "make proto && make check green, whole suite, no existing test edited."

verification_command: |
  cd codeforge && make proto && make check && python -c "from kernel.world_boundary import world_boundary_gaps, world_import_violations; print(world_boundary_gaps(), world_import_violations())"

rollback: >
  git revert. The three declarations return to engine_seam.py and the boundary is unchanged,
  because it was never edited.

approval_gates: >
  none for the move itself. If the split reveals that Engine2D or ChunkPosition ALSO belong in the
  world, say so and stop: which layer owns the 2D engine is a Principal Engineer question and not
  this order's to answer.

size:                 small

taint_class:          SAFE

# EXTRACTION CONTEXT
store_search_result: >
  Certified Tier and Working Shelf both searched for a layering, port-and-adapter or
  contract-extraction Part. Nothing catalogued. This is a one-off split inside one repository.

parts_to_consume:     none.

watch_for: >
  This is a layering fault that a test caught and an order caused. If you find a SECOND world
  module reaching into the platform while you are in there, do not fix it, name it: two is a
  pattern about how this codebase grew and it deserves its own order rather than a quiet ride
  along with this one.
