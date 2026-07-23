"""CARD: onboarding -- the practical adapter for the Workflow Engine: an onboarding checklist.

The reverse of `parts/quest`: the SAME `WorkflowEngine` core, driven through a plain (non-game)
function interface instead of MUD commands, and ROLE-GATED (only the employee submits paperwork,
only HR completes orientation, only a manager activates). This is the two-way translation the
CodeForge vision is built on (docs/vision_resync.md): one core part proven in the game and reused
in a real business workflow. Its practical cousins are approval, case, and project workflows.
"""

from __future__ import annotations

from collections.abc import Callable

from parts.shelf.workflow import Instance, Step, WorkflowEngine, build_workflow

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


def available(engine: WorkflowEngine, run: Instance) -> list[tuple[str, list[str]]]:
    """The `(action, roles)` pairs fireable from the run's current state, sorted by action."""
    return sorted(
        (event, sorted(roles))
        for (state, event), roles in engine.workflow.roles.items()
        if state == run.state
    )


def drive(
    reader: Callable[[str], str] = input,
    writer: Callable[[str], None] = print,
) -> Instance:
    """Run onboarding through a plain terminal interface: the practical adapter's own UI.

    The SAME `WorkflowEngine` that powers the MUD quest, driven here with no game - pick an action,
    the required role fires it, until the employee is active. IO is injected, so it is fully
    testable and the loop never touches the network. Reads only from `reader`; writes only to
    `writer`; the engine, not the interface, owns the state.
    """
    engine, run = new_onboarding()
    writer("Employee onboarding - the Workflow Engine through a practical interface.")
    writer("Type an action to advance, or 'quit' to stop.")
    while not engine.is_done(run):
        writer(f"\n  status: {status_line(run)}")
        options = available(engine, run)
        for event, roles in options:
            writer(f"    - {event}   (role: {', '.join(roles)})")
        choice = reader("action> ").strip()
        if choice in ("", "quit", "q"):
            writer("Left the workflow before completion.")
            return run
        match = next((opt for opt in options if opt[0] == choice), None)
        if match is None:
            writer(f"  '{choice}' is not available from here.")
            continue
        event, roles = match
        engine.advance(run, event, actor=roles[0])
        writer(f"  {roles[0]} -> {event}")
    writer(f"\n  DONE: {status_line(run)}")
    writer("  trail: " + " -> ".join(h["to"] for h in run.history))
    return run
