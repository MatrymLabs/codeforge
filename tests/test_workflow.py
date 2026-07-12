"""Test twin for parts/workflow.py -- the config-driven workflow engine (roles + history)."""

import pytest

from parts.statemachine import Fired, Refusal
from parts.workflow import (
    ANY_ROLE,
    Step,
    WorkflowEngine,
    WorkflowError,
    build_workflow,
)


def _approval():
    """A tiny role-gated approval workflow: draft -> submitted -> approved."""
    return build_workflow(
        "approval",
        start="draft",
        steps=[
            Step("draft", "submit", "submitted", roles=frozenset({"author"})),
            Step("submitted", "approve", "approved", roles=frozenset({"manager"})),
            Step("submitted", "reject", "draft", roles=frozenset({"manager"})),
        ],
        terminal=["approved"],
    )


def test_build_rejects_a_terminal_state_that_is_not_in_the_graph():
    with pytest.raises(WorkflowError, match="terminal"):
        build_workflow("bad", "a", [Step("a", "go", "b")], terminal=["c"])


def test_build_rejects_a_non_deterministic_graph():
    with pytest.raises(ValueError, match="non-deterministic"):
        build_workflow("bad", "a", [Step("a", "go", "b"), Step("a", "go", "c")])


def test_a_legal_move_fires_and_records_history():
    engine = WorkflowEngine(_approval())
    run = engine.open()
    outcome = engine.advance(run, "submit", actor="author")
    assert isinstance(outcome, Fired)
    assert run.state == "submitted"
    assert run.history == [
        {"event": "submit", "actor": "author", "from": "draft", "to": "submitted"}
    ]


def test_an_unknown_event_is_a_refusal_not_a_crash():
    engine = WorkflowEngine(_approval())
    run = engine.open()
    outcome = engine.advance(run, "teleport")
    assert isinstance(outcome, Refusal)
    assert run.state == "draft"  # unchanged


def test_the_wrong_role_is_refused_and_the_right_role_is_allowed():
    engine = WorkflowEngine(_approval())
    run = engine.open()
    engine.advance(run, "submit", actor="author")
    denied = engine.advance(run, "approve", actor="author")  # author is not a manager
    assert isinstance(denied, Refusal) and "may not" in denied.reason
    assert run.state == "submitted"
    allowed = engine.advance(run, "approve", actor="manager")
    assert isinstance(allowed, Fired) and run.state == "approved"
    assert engine.is_done(run)


def test_actions_lists_only_what_this_actor_may_do():
    engine = WorkflowEngine(_approval())
    run = engine.open()
    engine.advance(run, "submit", actor="author")
    assert engine.actions(run, actor="manager") == ["approve", "reject"]
    assert engine.actions(run, actor="author") == []  # nothing here for the author


def test_a_guard_can_block_a_move():
    wf = build_workflow(
        "gated",
        start="a",
        steps=[Step("a", "go", "b", guard="never")],
    )
    engine = WorkflowEngine(wf, guards={"never": lambda ctx: "the guard says no"})
    run = engine.open()
    outcome = engine.advance(run, "go")
    assert isinstance(outcome, Refusal) and outcome.reason == "the guard says no"
    assert run.state == "a"


def test_any_role_steps_are_open_to_everyone():
    wf = build_workflow("open", start="a", steps=[Step("a", "go", "b")], terminal=["b"])
    engine = WorkflowEngine(wf)
    run = engine.open()
    assert isinstance(engine.advance(run, "go", actor="anybody"), Fired)
    assert engine.is_done(run)
    assert ANY_ROLE in wf.roles[("a", "go")]
