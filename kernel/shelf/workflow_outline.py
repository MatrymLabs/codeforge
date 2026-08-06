"""Accessible, deterministic outline projection for the canonical workflow model.

The outline is a read-only projection. It contains no executable callbacks and no independent
workflow state; edits must continue to target ``kernel.shelf.workflow.Workflow`` definitions.
That keeps text, forms, MUD panels, and a future node canvas on the same authoritative model.
"""

from __future__ import annotations

from dataclasses import dataclass

from kernel.shelf.workflow import Workflow


class WorkflowOutlineError(ValueError):
    """A workflow cannot be projected into a safe accessible outline."""


@dataclass(frozen=True)
class OutlineTransition:
    """One readable transition in the workflow outline."""

    source: str
    event: str
    destination: str
    roles: tuple[str, ...]
    guard: str = ""
    effect: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "event": self.event,
            "destination": self.destination,
            "roles": list(self.roles),
            "guard": self.guard,
            "effect": self.effect,
        }


@dataclass(frozen=True)
class OutlineState:
    """A state row with accessible label and action references."""

    state_id: str
    label: str
    is_start: bool
    is_terminal: bool
    actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "state_id": self.state_id,
            "label": self.label,
            "is_start": self.is_start,
            "is_terminal": self.is_terminal,
            "actions": list(self.actions),
        }


@dataclass(frozen=True)
class OutlineFocusItem:
    """One keyboard-focusable, screen-reader-addressable outline item."""

    item_id: str
    kind: str
    label: str
    summary: str
    read_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "kind": self.kind,
            "label": self.label,
            "summary": self.summary,
            "read_only": self.read_only,
        }


@dataclass(frozen=True)
class WorkflowOutline:
    """A text-first projection of one validated workflow definition."""

    schema_version: str
    workflow_id: str
    start_state: str
    states: tuple[OutlineState, ...]
    transitions: tuple[OutlineTransition, ...]

    @classmethod
    def from_workflow(cls, workflow: Workflow, *, schema_version: str = "1.0") -> WorkflowOutline:
        if not workflow.workflow_id.strip():
            raise WorkflowOutlineError("workflow_id must not be empty")
        if not schema_version.strip():
            raise WorkflowOutlineError("schema_version must not be empty")
        states = tuple(
            OutlineState(
                state_id=state,
                label=workflow.labels.get(state, state),
                is_start=state == workflow.machine.start,
                is_terminal=state in workflow.terminal,
                actions=tuple(
                    sorted(event for (source, event) in workflow.roles if source == state)
                ),
            )
            for state in sorted(workflow.machine.states)
        )
        transitions = tuple(
            OutlineTransition(
                source=transition.src,
                event=transition.event,
                destination=transition.dst,
                roles=tuple(sorted(workflow.roles.get((transition.src, transition.event), ()))),
                guard=transition.guard or "",
                effect=transition.effect or "",
            )
            for transition in sorted(
                workflow.machine.transitions,
                key=lambda item: (item.src, item.event, item.dst),
            )
        )
        return cls(
            schema_version,
            workflow.workflow_id,
            workflow.machine.start,
            states,
            transitions,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "start_state": self.start_state,
            "states": [state.to_dict() for state in self.states],
            "transitions": [transition.to_dict() for transition in self.transitions],
        }

    def focus_items(self) -> tuple[OutlineFocusItem, ...]:
        """Return stable focus order for keyboard and assistive-technology clients.

        States precede transitions, and both groups preserve the projection's deterministic order.
        Items are descriptive and read-only; an editor must submit a change to the canonical
        workflow definition instead of mutating this projection.
        """

        states = tuple(
            OutlineFocusItem(
                item_id=f"state:{state.state_id}",
                kind="state",
                label=state.label,
                summary=(
                    f"{state.label}; state {state.state_id}; "
                    f"{'start; ' if state.is_start else ''}"
                    f"{'terminal; ' if state.is_terminal else ''}"
                    f"actions: {', '.join(state.actions) or 'none'}"
                ).rstrip("; "),
            )
            for state in self.states
        )
        transitions = tuple(
            OutlineFocusItem(
                item_id=f"transition:{index}",
                kind="transition",
                label=f"{transition.source} via {transition.event}",
                summary=(
                    f"{transition.source} to {transition.destination} via {transition.event}; "
                    f"roles: {', '.join(transition.roles) or 'none'}"
                ),
            )
            for index, transition in enumerate(self.transitions)
        )
        return states + transitions

    def text_fallback(self) -> str:
        """Return a stable hierarchy usable without a canvas or rich client."""
        lines = [f"Workflow: {self.workflow_id}", f"Start: {self.start_state}", "States:"]
        for state in self.states:
            flags = []
            if state.is_start:
                flags.append("start")
            if state.is_terminal:
                flags.append("terminal")
            suffix = f" ({', '.join(flags)})" if flags else ""
            actions = ", ".join(state.actions) or "none"
            lines.append(f"  {state.label} [{state.state_id}]{suffix}; actions: {actions}")
        lines.append("Transitions:")
        for transition in self.transitions:
            roles = ", ".join(transition.roles) or "none"
            details = [f"roles: {roles}"]
            if transition.guard:
                details.append(f"guard: {transition.guard}")
            if transition.effect:
                details.append(f"effect: {transition.effect}")
            lines.append(
                f"  {transition.source} --{transition.event}--> {transition.destination} "
                f"({'; '.join(details)})"
            )
        return "\n".join(lines)


@dataclass(frozen=True)
class OutlineNavigator:
    """Pure keyboard navigation state over a ``WorkflowOutline``."""

    outline: WorkflowOutline
    focus_index: int = 0

    def __post_init__(self) -> None:
        if self.focus_index < 0 or self.focus_index >= len(self.items):
            if self.items:
                raise WorkflowOutlineError("focus_index is outside the outline focus order")
            if self.focus_index != 0:
                raise WorkflowOutlineError("empty outlines only support focus_index 0")

    @property
    def items(self) -> tuple[OutlineFocusItem, ...]:
        return self.outline.focus_items()

    @property
    def focused(self) -> OutlineFocusItem | None:
        return self.items[self.focus_index] if self.items else None

    def move(self, key: str) -> OutlineNavigator:
        """Apply a bounded navigation key without changing workflow semantics."""

        if not self.items:
            return self
        normalized = key.strip().lower()
        if normalized in {"down", "j", "next"}:
            index = min(self.focus_index + 1, len(self.items) - 1)
        elif normalized in {"up", "k", "previous"}:
            index = max(self.focus_index - 1, 0)
        elif normalized == "home":
            index = 0
        elif normalized == "end":
            index = len(self.items) - 1
        else:
            raise WorkflowOutlineError(f"unsupported outline navigation key: {key!r}")
        return OutlineNavigator(self.outline, index)

    def announcement(self) -> str:
        """Return the current screen-reader/text announcement, including position."""

        if not self.focused:
            return f"Workflow {self.outline.workflow_id}; no focusable outline items."
        return (
            f"{self.focused.summary}. Item {self.focus_index + 1} of {len(self.items)}. "
            "Read-only outline; edit the canonical workflow to make changes."
        )
