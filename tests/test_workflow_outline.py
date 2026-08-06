import pytest

from kernel.shelf.workflow import ANY_ROLE, Step, build_workflow
from kernel.shelf.workflow_outline import OutlineNavigator, WorkflowOutline, WorkflowOutlineError


def _workflow():
    return build_workflow(
        "approval",
        start="draft",
        steps=[
            Step(
                "draft",
                "submit",
                "submitted",
                roles=frozenset({"author"}),
                effect="record_submission",
            ),
            Step(
                "submitted",
                "approve",
                "approved",
                roles=frozenset({"manager"}),
                guard="review_open",
            ),
            Step("submitted", "reject", "draft", roles=frozenset({ANY_ROLE})),
        ],
        terminal=["approved"],
        labels={"draft": "Draft", "submitted": "Awaiting review", "approved": "Approved"},
    )


def test_outline_is_deterministic_and_preserves_semantics() -> None:
    outline = WorkflowOutline.from_workflow(_workflow())
    assert outline.to_dict() == WorkflowOutline.from_workflow(_workflow()).to_dict()
    assert outline.states[0].state_id == "approved"
    submitted = next(state for state in outline.states if state.state_id == "submitted")
    assert submitted.label == "Awaiting review"
    assert submitted.actions == ("approve", "reject")
    approve = next(edge for edge in outline.transitions if edge.event == "approve")
    assert approve.roles == ("manager",)
    assert approve.guard == "review_open"


def test_outline_text_fallback_is_readable_without_visual_surface() -> None:
    text = WorkflowOutline.from_workflow(_workflow()).text_fallback()
    assert "Workflow: approval" in text
    assert "Draft [draft] (start)" in text
    assert "Approved [approved] (terminal)" in text
    assert "submitted --approve--> approved" in text
    assert "guard: review_open" in text


def test_outline_has_deterministic_focus_order_and_announcements() -> None:
    outline = WorkflowOutline.from_workflow(_workflow())
    navigator = OutlineNavigator(outline)

    assert [item.item_id for item in navigator.items] == [
        "state:approved",
        "state:draft",
        "state:submitted",
        "transition:0",
        "transition:1",
        "transition:2",
    ]
    assert navigator.focused is not None and navigator.focused.label == "Approved"
    assert "Item 1 of 6" in navigator.announcement()
    assert "Read-only" in navigator.announcement()


def test_outline_keyboard_navigation_is_bounded_and_rejects_unknown_keys() -> None:
    navigator = OutlineNavigator(WorkflowOutline.from_workflow(_workflow()))

    assert navigator.move("end").focused is not None
    assert navigator.move("end").move("down").focus_index == 5
    assert navigator.move("j").move("up").focus_index == 0
    with pytest.raises(WorkflowOutlineError, match="unsupported"):
        navigator.move("enter")
