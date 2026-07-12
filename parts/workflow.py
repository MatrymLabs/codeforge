"""CARD: workflow -- a config-driven workflow engine on the pure FSM: roles and history.

A workflow is a lifecycle whose legal moves are a state machine (`parts/statemachine`) plus the
two things a bare FSM lacks: WHO may make each move (role gating) and a RECORD of what happened
(the history trail). One `WorkflowEngine` drives any workflow defined as data, so the SAME core
runs a game quest (`parts/quest`) and a business onboarding checklist (`parts/onboarding`) -- only
the adapter and the applied effects differ. Like the machine it wraps, it never renders and never
mutates world state: it steps a local `Instance` and names an effect for the caller to apply.

This is the first reusable vertical slice of the manufacturing vision (docs/vision_resync.md):
one part, proven in the game and reused in a practical application.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from parts.statemachine import Fired, Guard, Machine, Outcome, Refusal, Transition, advance, build

ANY_ROLE = "*"  # a step open to any actor


class WorkflowError(ValueError):
    """A workflow definition is malformed (most graph validation is delegated to statemachine)."""


@dataclass(frozen=True)
class Step:
    """One workflow move: from `state`, event `event` goes to `to`, for actors in `roles`."""

    state: str
    event: str
    to: str
    roles: frozenset[str] = frozenset({ANY_ROLE})
    guard: str | None = None  # a name resolved from the engine's guard registry
    effect: str | None = None  # a name the CALLER applies; the engine never mutates the world


@dataclass(frozen=True)
class Workflow:
    """A validated workflow: the machine, its terminal states, the role map, and state labels."""

    workflow_id: str
    machine: Machine
    terminal: frozenset[str]
    roles: Mapping[tuple[str, str], frozenset[str]]  # (state, event) -> allowed roles
    labels: Mapping[str, str]  # state -> human label


@dataclass
class Instance:
    """A live run of a workflow: where it is now, and the trail of how it got there."""

    workflow_id: str
    state: str
    history: list[dict[str, str]] = field(default_factory=list)  # {event, actor, from, to}
    context: dict[str, object] = field(default_factory=dict)


def build_workflow(
    workflow_id: str,
    start: str,
    steps: Sequence[Step],
    *,
    terminal: Sequence[str] = (),
    labels: Mapping[str, str] | None = None,
) -> Workflow:
    """Assemble a workflow from steps. Fails loud (via `statemachine.build`) on a bad graph."""
    states = {start}
    transitions: list[Transition] = []
    roles: dict[tuple[str, str], frozenset[str]] = {}
    for s in steps:
        states.add(s.state)
        states.add(s.to)
        transitions.append(Transition(s.state, s.event, s.to, s.guard, s.effect))
        roles[(s.state, s.event)] = s.roles
    machine = build(states, start, transitions)  # loud on off-graph / non-deterministic edges
    for t in terminal:
        if t not in machine.states:
            raise WorkflowError(f"terminal state {t!r} is not one of the workflow's states")
    return Workflow(workflow_id, machine, frozenset(terminal), roles, dict(labels or {}))


class WorkflowEngine:
    """Drives instances of one workflow: role-gate a move, fire the machine, record the history."""

    def __init__(self, workflow: Workflow, guards: Mapping[str, Guard] | None = None) -> None:
        self.workflow = workflow
        self.guards = dict(guards or {})

    def open(self, context: Mapping[str, object] | None = None) -> Instance:
        """A fresh run at the workflow's start state."""
        return Instance(
            self.workflow.workflow_id, self.workflow.machine.start, [], dict(context or {})
        )

    def actions(self, instance: Instance, actor: str = ANY_ROLE) -> list[str]:
        """The events `actor` may legally fire from the current state (before guards run)."""
        out = [
            event
            for (state, event), allowed in self.workflow.roles.items()
            if state == instance.state and (ANY_ROLE in allowed or actor in allowed)
        ]
        return sorted(out)

    def advance(
        self,
        instance: Instance,
        event: str,
        actor: str = ANY_ROLE,
        ctx: Mapping[str, object] | None = None,
    ) -> Outcome:
        """Role-gate, then fire the machine; on a legal move, record it and step the instance."""
        allowed = self.workflow.roles.get((instance.state, event))
        if allowed is not None and ANY_ROLE not in allowed and actor not in allowed:
            return Refusal(f"{actor!r} may not {event!r} from {instance.state!r}")
        outcome = advance(self.workflow.machine, instance.state, event, ctx, self.guards)
        if isinstance(outcome, Fired):
            instance.history.append(
                {"event": event, "actor": actor, "from": instance.state, "to": outcome.dst}
            )
            instance.state = outcome.dst
        return outcome

    def is_done(self, instance: Instance) -> bool:
        """True when the instance has reached a terminal state."""
        return instance.state in self.workflow.terminal
