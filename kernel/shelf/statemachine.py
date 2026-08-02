"""CARD: statemachine -- a pure finite-state machine: states, guarded transitions, honest refusals.

A lifecycle (a door, a quest, a combat phase, a compliance control) is a set of states and
the *legal* moves between them. This part makes the legal moves a table lookup and the
illegal moves impossible: `advance` consults the machine and returns either a `Fired`
outcome (the next state plus a named effect for the caller to apply) or a `Refusal` (why the
move was not allowed). It never renders, never broadcasts, and never mutates world state --
guards are pure, effects are applied by validated engine logic, honoring the architecture
laws (state is canonical, only engine logic mutates).

The machine is data: states, a start state, and transitions naming a guard and an effect.
Guards and effects are *names* resolved through a registry the caller supplies, so a machine
stays serializable (it can live in a seed) while the Python lives at the call site. Build one
with `build()`, which validates it loud and early: an off-graph transition or two edges for
the same (state, event) is a construction error, not a runtime surprise.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

# A guard inspects a read-only context and returns a refusal reason, or None to allow.
Guard = Callable[[Mapping[str, object]], str | None]


@dataclass(frozen=True)
class Transition:
    """One frozen edge: from `src`, event `event` moves to `dst`, if `guard` allows."""

    src: str
    event: str
    dst: str
    guard: str | None = None  # a name resolved from the caller's guard registry
    effect: str | None = None  # a name the CALLER applies; the machine never mutates


@dataclass(frozen=True)
class Fired:
    """A legal transition: the machine moved to `dst`; apply `effect` if there is one."""

    dst: str
    effect: str | None


@dataclass(frozen=True)
class Refusal:
    """An illegal move: no such transition, or a guard blocked it. `reason` explains why."""

    reason: str


Outcome = Fired | Refusal


@dataclass(frozen=True)
class Machine:
    """The blueprint: the state set, the start state, and a validated transition index.

    Construct with `build()`, never directly -- `build` validates the graph and computes the
    O(1) `index`. Constructing this class by hand skips that and yields an empty index.
    """

    states: frozenset[str]
    start: str
    transitions: tuple[Transition, ...]
    index: Mapping[tuple[str, str], Transition] = field(default_factory=dict, repr=False)


def build(states: Iterable[str], start: str, transitions: Iterable[Transition]) -> Machine:
    """Validate a machine and index it for O(1) advance. Fails loud on a malformed graph."""
    state_set = frozenset(states)
    edges = tuple(transitions)
    if start not in state_set:
        raise ValueError(f"start state {start!r} is not in the state set")
    index: dict[tuple[str, str], Transition] = {}
    for t in edges:
        if t.src not in state_set:
            raise ValueError(f"transition from unknown state {t.src!r}")
        if t.dst not in state_set:
            raise ValueError(f"transition to unknown state {t.dst!r}")
        key = (t.src, t.event)
        if key in index:
            raise ValueError(f"non-deterministic machine: two transitions for {key!r}")
        index[key] = t
    return Machine(states=state_set, start=start, transitions=edges, index=index)


def advance(
    machine: Machine,
    current: str,
    event: str,
    ctx: Mapping[str, object] | None = None,
    guards: Mapping[str, Guard] | None = None,
) -> Outcome:
    """Consult the machine: return `Fired(dst, effect)` for a legal move, else `Refusal`.

    An unknown (state, event) pair is a `Refusal`, never an exception -- illegal input is a
    normal answer. A guard that *raises* is caught and reported as a refusal (a broken guard
    must not crash the tick). A transition naming a guard absent from the registry is a
    programmer error and raises loud -- the machine and its wiring disagree.
    """
    transition = machine.index.get((current, event))
    if transition is None:
        return Refusal(f"no transition from {current!r} on {event!r}")
    if transition.guard is not None:
        guard_fn = (guards or {}).get(transition.guard)
        if guard_fn is None:
            raise KeyError(f"guard {transition.guard!r} is not in the guard registry")
        try:
            reason = guard_fn(ctx or {})
        except Exception as exc:  # a broken guard refuses; it must never crash the tick
            return Refusal(f"guard {transition.guard!r} errored: {exc}")
        if reason is not None:
            return Refusal(reason)
    return Fired(transition.dst, transition.effect)
