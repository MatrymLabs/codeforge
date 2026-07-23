# Hardware Store Part: Workflow Engine

*The first reusable vertical slice of the manufacturing vision ([vision_resync.md](../vision_resync.md)):
one core part proven in the game and reused in a practical application. Part Manifest below.*

## Part Manifest

| Field | Value |
|---|---|
| **part_id** | `workflow-engine` |
| **name** | Workflow Engine |
| **version** | 0.1 (beta) |
| **maturity** | `beta` (demonstrated in two contexts; not yet stable, not yet persistent) |
| **purpose** | Drive any lifecycle defined as data: role-gated moves between states, a recorded history trail, and named effects the caller applies. |
| **source** | `parts/shelf/workflow.py` (built on the pure FSM `parts/shelf/statemachine.py`) |
| **domain** | orchestration |
| **inputs** | a workflow definition (states, steps with roles/guards/effects, terminal states) + an `Instance` + an event + an actor role |
| **outputs** | a `Fired(dst, effect)` or `Refusal(reason)`; a mutated local `Instance` with history |
| **interfaces** | `build_workflow(...)`, `WorkflowEngine.open/actions/advance/is_done` |
| **dependencies** | `parts.shelf.statemachine` (internal, stdlib-only) |
| **security** | never mutates world state; effects are names the caller applies; role gating refuses before firing |
| **tests** | `tests/test_workflow.py` (core), `tests/test_quest.py` (game), `tests/test_onboarding.py` (practical + one-core proof) |
| **license** | MIT · **source_status** original · **owner** MatrymLabs |
| **adapters** | MUD command adapter (`parts/quest.py`), plain-function adapter (`parts/onboarding.py`); a web/API adapter is a later slice |

## Core behavior (domain logic, game-free)

A workflow is a validated state machine plus **role gating** (who may fire each event) and a
**history trail** (what happened). `advance` role-checks, fires the machine, and records the move.
It renders nothing and mutates no world state, honoring the architecture laws.

## Game demonstration

`parts/quest.py` -- the **Coilward Contract**: a player walks `offered -> accepted -> underway ->
done` with the `quest` MUD verb; finishing fires the `award_xp` effect. Reachable through the
engine tick (`handle_command(session, "quest ...")`).

## Practical translation

`parts/onboarding.py` -- **employee onboarding**: the *same* `WorkflowEngine`, driven through a
plain function interface, role-gated so only the employee submits paperwork, only HR completes
orientation, and only a manager activates. Its cousins are approval, case, incident, and project
workflows.

**Proof:** `test_onboarding.py::test_one_core_powers_both_the_game_quest_and_the_practical_workflow`
asserts the same engine class drives both a quest and an onboarding run.

## Not yet (honest labels)

Persistence (runs are in-memory), parallelism (single-threaded), a web/API adapter, and seed-shipped
workflow definitions are later slices. A part is not stable merely because it works once.
