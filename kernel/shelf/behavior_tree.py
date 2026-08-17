"""CARD: behavior_tree -- a reactive behavior tree for NPC AI and task/agent orchestration.

The first rung of the R&D AI / Orchestration Lab, and the game-dev survey's top
reverse-engineering opportunity (flagged twice): the decision architecture that is the AAA
NPC-AI workhorse AND the shape LLM-agent/workflow orchestration is rediscovering. CodeForge
already has the FSM half (kernel/shelf/statemachine); this is the Behavior Tree half.

A behavior tree ticks from the root each step (reactive): composites route control by their
children's returned Status, so priorities are re-checked every tick (a higher-priority
branch pre-empts a lower one the moment its condition becomes true).

  Status:     SUCCESS | FAILURE | RUNNING
  Leaves:     Action (do work, return a Status/bool), Condition (a boolean guard)
  Composites: Sequence (AND - all must succeed, in order), Selector (OR - first success),
              Parallel (succeed when >= threshold children succeed)
  Decorators: Inverter, AlwaysSucceed, AlwaysFail, Repeater

It is domain-neutral: a `context` (blackboard) is passed to every leaf; the tree decides,
the leaves act. Usable for a Haven guard NPC and for a CodeForge task-orchestration policy.

Clean-room, stdlib only.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(Enum):
    """The result of ticking a node."""

    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


class BehaviorTreeError(ValueError):
    """Raised on a malformed tree (an action returning a non-Status/bool, a bad threshold)."""


Context = Any  # a blackboard (any object); leaves decide how to read/write it


@dataclass
class Node:
    """Base node. Every node ticks a context to a Status."""

    name: str = ""

    def tick(self, context: Context) -> Status:  # pragma: no cover - overridden
        raise NotImplementedError

    def _label(self) -> str:
        return self.name or type(self).__name__


@dataclass
class Action(Node):
    """A leaf that does work. `fn(context)` returns a Status, or a bool (True=SUCCESS)."""

    fn: Callable[[Context], Status | bool] = lambda _c: Status.SUCCESS

    def tick(self, context: Context) -> Status:
        result = self.fn(context)
        if isinstance(result, Status):
            return result
        if isinstance(result, bool):
            return Status.SUCCESS if result else Status.FAILURE
        raise BehaviorTreeError(
            f"action {self._label()} returned {type(result).__name__}, expected Status or bool"
        )


@dataclass
class Condition(Node):
    """A leaf guard: SUCCESS if `pred(context)` is truthy, else FAILURE (never RUNNING)."""

    pred: Callable[[Context], bool] = lambda _c: True

    def tick(self, context: Context) -> Status:
        return Status.SUCCESS if self.pred(context) else Status.FAILURE


@dataclass
class Sequence(Node):
    """AND: tick children in order. FAILURE on the first failure, RUNNING on the first
    running child, SUCCESS only if every child succeeds. An empty sequence is SUCCESS."""

    children: tuple[Node, ...] = ()

    def tick(self, context: Context) -> Status:
        for child in self.children:
            status = child.tick(context)
            if status is not Status.SUCCESS:
                return status
        return Status.SUCCESS


@dataclass
class Selector(Node):
    """OR (fallback): tick children in order. SUCCESS on the first success, RUNNING on the
    first running child, FAILURE only if every child fails. An empty selector is FAILURE."""

    children: tuple[Node, ...] = ()

    def tick(self, context: Context) -> Status:
        for child in self.children:
            status = child.tick(context)
            if status is not Status.FAILURE:
                return status
        return Status.FAILURE


@dataclass
class Parallel(Node):
    """Tick all children; SUCCESS when >= `threshold` succeed, FAILURE when too many have
    failed to still reach the threshold, else RUNNING."""

    children: tuple[Node, ...] = ()
    threshold: int = 1

    def __post_init__(self) -> None:
        if self.threshold < 1:
            raise BehaviorTreeError(f"parallel {self._label()} threshold must be >= 1")

    def tick(self, context: Context) -> Status:
        successes = failures = 0
        for child in self.children:
            status = child.tick(context)
            if status is Status.SUCCESS:
                successes += 1
            elif status is Status.FAILURE:
                failures += 1
        if successes >= self.threshold:
            return Status.SUCCESS
        if len(self.children) - failures < self.threshold:
            return Status.FAILURE
        return Status.RUNNING


@dataclass
class Inverter(Node):
    """Flip SUCCESS<->FAILURE; RUNNING passes through."""

    child: Node | None = None

    def tick(self, context: Context) -> Status:
        assert self.child is not None, "inverter needs a child"
        status = self.child.tick(context)
        if status is Status.SUCCESS:
            return Status.FAILURE
        if status is Status.FAILURE:
            return Status.SUCCESS
        return status


@dataclass
class AlwaysSucceed(Node):
    """Tick the child but always report SUCCESS (unless RUNNING)."""

    child: Node | None = None

    def tick(self, context: Context) -> Status:
        assert self.child is not None
        status = self.child.tick(context)
        return Status.RUNNING if status is Status.RUNNING else Status.SUCCESS


@dataclass
class AlwaysFail(Node):
    """Tick the child but always report FAILURE (unless RUNNING)."""

    child: Node | None = None

    def tick(self, context: Context) -> Status:
        assert self.child is not None
        status = self.child.tick(context)
        return Status.RUNNING if status is Status.RUNNING else Status.FAILURE


@dataclass
class Repeater(Node):
    """Tick the child up to `times`, stopping early on FAILURE or RUNNING; SUCCESS if all
    repetitions succeed. `times <= 0` is a no-op SUCCESS."""

    child: Node | None = None
    times: int = 1

    def tick(self, context: Context) -> Status:
        assert self.child is not None
        for _ in range(self.times):
            status = self.child.tick(context)
            if status is not Status.SUCCESS:
                return status
        return Status.SUCCESS


@dataclass
class RunResult:
    """The outcome of running a tree to completion (or a tick cap)."""

    status: Status
    ticks: int
    capped: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)


def run(root: Node, context: Context, *, max_ticks: int = 1000) -> RunResult:
    """Tick the tree until it settles to SUCCESS/FAILURE, or until `max_ticks` (a guard
    against an always-RUNNING tree). Returns the final status and the tick count."""
    if max_ticks < 1:
        raise BehaviorTreeError("max_ticks must be >= 1")
    ticks = 0
    status = Status.RUNNING
    while ticks < max_ticks:
        ticks += 1
        status = root.tick(context)
        if status is not Status.RUNNING:
            return RunResult(status=status, ticks=ticks)
    return RunResult(
        status=Status.RUNNING,
        ticks=ticks,
        capped=True,
        notes=(f"hit the max_ticks cap ({max_ticks}); the tree never settled",),
    )


def render(root: Node, *, indent: int = 0) -> str:
    """A human-readable rendering of the tree structure."""
    line = "  " * indent + f"- {root._label()} ({type(root).__name__})"
    lines = [line]
    children: tuple[Node, ...] = ()
    if isinstance(root, (Sequence, Selector, Parallel)):
        children = root.children
    elif (
        isinstance(root, (Inverter, AlwaysSucceed, AlwaysFail, Repeater)) and root.child is not None
    ):
        children = (root.child,)
    for child in children:
        lines.append(render(child, indent=indent + 1))
    return "\n".join(lines)
