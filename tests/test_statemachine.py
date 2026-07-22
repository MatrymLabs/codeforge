"""Test twin for parts/statemachine.py -- the pure finite-state machine.

Acceptance: a legal transition fires and carries its effect; a guard can allow. Refusal
(the hostile half): an unknown event, a blocked guard, a guard that raises, and a malformed
machine all fail the *right* way -- a refusal at runtime, a loud error at build. A property
test pins the core invariant: from any state on any event, `advance` never raises and never
lands off the graph.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from hypothesis import given
from hypothesis import strategies as st

from parts.shelf.statemachine import Fired, Refusal, Transition, advance, build

# A tiny door machine reused across cases: locked --unlock[key_fits]--> open.
_DOOR = build(
    states={"locked", "open"},
    start="locked",
    transitions=[Transition("locked", "unlock", "open", guard="key_fits", effect="open_it")],
)


def _has_key(ctx: Mapping[str, object]) -> str | None:
    return None if ctx.get("has_key") else "You don't have the key."


# --- acceptance -----------------------------------------------------------------
def test_a_legal_transition_fires_with_its_effect() -> None:
    out = advance(_DOOR, "locked", "unlock", {"has_key": True}, {"key_fits": _has_key})
    assert out == Fired(dst="open", effect="open_it")


def test_a_transition_with_no_guard_always_fires() -> None:
    m = build(states={"a", "b"}, start="a", transitions=[Transition("a", "go", "b")])
    assert advance(m, "a", "go") == Fired(dst="b", effect=None)


# --- refusal (the hostile half) -------------------------------------------------
def test_an_unknown_event_refuses_rather_than_raising() -> None:
    out = advance(_DOOR, "locked", "kick", {}, {"key_fits": _has_key})
    assert isinstance(out, Refusal)
    assert "no transition" in out.reason


def test_a_transition_illegal_from_the_current_state_refuses() -> None:
    # unlock is only legal from 'locked'; from 'open' there is no such edge.
    out = advance(_DOOR, "open", "unlock", {"has_key": True}, {"key_fits": _has_key})
    assert isinstance(out, Refusal)


def test_a_guard_can_block_with_a_reason() -> None:
    out = advance(_DOOR, "locked", "unlock", {"has_key": False}, {"key_fits": _has_key})
    assert out == Refusal("You don't have the key.")


def test_a_guard_that_raises_becomes_a_refusal_not_a_crash() -> None:
    def boom(ctx: Mapping[str, object]) -> str | None:
        raise RuntimeError("kaboom")

    out = advance(_DOOR, "locked", "unlock", {}, {"key_fits": boom})
    assert isinstance(out, Refusal)
    assert "errored" in out.reason


def test_a_guard_missing_from_the_registry_is_a_loud_programmer_error() -> None:
    with pytest.raises(KeyError, match="key_fits"):
        advance(_DOOR, "locked", "unlock", {}, guards={})


def test_build_rejects_a_start_outside_the_states() -> None:
    with pytest.raises(ValueError, match="start state"):
        build(states={"a"}, start="z", transitions=[])


def test_build_rejects_a_transition_from_an_unknown_state() -> None:
    with pytest.raises(ValueError, match="unknown state"):
        build(states={"a"}, start="a", transitions=[Transition("ghost", "go", "a")])


def test_build_rejects_a_transition_to_an_unknown_state() -> None:
    with pytest.raises(ValueError, match="unknown state"):
        build(states={"a"}, start="a", transitions=[Transition("a", "go", "nowhere")])


def test_build_rejects_a_nondeterministic_machine() -> None:
    with pytest.raises(ValueError, match="non-deterministic"):
        build(
            states={"a", "b", "c"},
            start="a",
            transitions=[Transition("a", "go", "b"), Transition("a", "go", "c")],
        )


# --- property: advance is total and stays on the graph --------------------------
@given(
    state=st.sampled_from(["locked", "open", "unknown_state"]),
    event=st.sampled_from(["unlock", "kick", "open", ""]),
    has_key=st.booleans(),
)
def test_advance_never_raises_and_never_leaves_the_graph(
    state: str, event: str, has_key: bool
) -> None:
    out = advance(_DOOR, state, event, {"has_key": has_key}, {"key_fits": _has_key})
    if isinstance(out, Fired):
        assert out.dst in _DOOR.states  # a fired transition always lands on a real state
    else:
        assert isinstance(out, Refusal)
