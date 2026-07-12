"""CARD: onboarding -- the practical adapter for the Workflow Engine: an onboarding checklist.

The reverse of `parts/quest`: the SAME `WorkflowEngine` core, driven through a plain (non-game)
function interface instead of MUD commands, and ROLE-GATED (only the employee submits paperwork,
only HR completes orientation, only a manager activates). This is the two-way translation the
CodeForge vision is built on (docs/vision_resync.md): one core part proven in the game and reused
in a real business workflow. Its practical cousins are approval, case, and project workflows.
"""

from __future__ import annotations

from parts.workflow import Instance, Step, WorkflowEngine, build_workflow

ONBOARDING = build_workflow(
    "employee_onboarding",
    start="created",
    steps=[
        Step("created", "submit_paperwork", "paperwork", roles=frozenset({"employee"})),
        Step("paperwork", "complete_orientation", "oriented", roles=frozenset({"hr"})),
        Step("oriented", "activate", "active", roles=frozenset({"manager"})),
    ],
    terminal=["active"],
    labels={
        "created": "Account created; paperwork pending.",
        "paperwork": "Paperwork submitted; orientation pending.",
        "oriented": "Orientation complete; activation pending.",
        "active": "Employee active.",
    },
)


def new_onboarding() -> tuple[WorkflowEngine, Instance]:
    """A fresh onboarding run and the engine that drives it."""
    engine = WorkflowEngine(ONBOARDING)
    return engine, engine.open()


def status_line(run: Instance) -> str:
    """A one-line human status for a run (the non-game 'view')."""
    return ONBOARDING.labels.get(run.state, run.state)


def run_demo() -> list[str]:
    """The practical adapter end to end, as a transcript. The proof it runs outside the game."""
    engine, run = new_onboarding()
    transcript = [f"start: {status_line(run)}"]
    for event, actor in (
        ("submit_paperwork", "employee"),
        ("complete_orientation", "hr"),
        ("activate", "manager"),
    ):
        engine.advance(run, event, actor=actor)
        transcript.append(f"{actor} {event}: {status_line(run)}")
    transcript.append(f"done: {engine.is_done(run)}")
    return transcript
