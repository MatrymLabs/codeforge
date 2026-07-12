"""CARD: quest -- the game adapter for the Workflow Engine: a regional quest as a workflow.

A quest is a workflow (`parts/workflow`) whose states a player walks with the `quest` MUD verb.
It proves the reusable core lives in the game: the SAME `WorkflowEngine` that drives a business
onboarding checklist (`parts/onboarding`) drives this quest -- only the effect differs (here, a
completed contract awards XP). The workflow is defined as data, so a seed could ship its own.
"""

from __future__ import annotations

from parts.session import Session
from parts.statemachine import Fired
from parts.workflow import Instance, Step, WorkflowEngine, build_workflow

_QUEST = build_workflow(
    "coilward_contract",
    start="offered",
    steps=[
        Step("offered", "accept", "accepted"),
        Step("accepted", "begin", "underway"),
        Step("underway", "finish", "done", effect="award_xp"),
    ],
    terminal=["done"],
    labels={
        "offered": "A contract waits at the board: clear the coil-warren.",
        "accepted": "You have taken the contract.",
        "underway": "The warren work is underway.",
        "done": "The contract is fulfilled.",
    },
)
_ENGINE = WorkflowEngine(_QUEST)
_XP_REWARD = 50

_RUNS: dict[str, Instance] = {}  # player_id -> their quest run


def _run(player_id: str) -> Instance:
    return _RUNS.setdefault(player_id, _ENGINE.open())


def quest_view(session: Session, arg: str = "") -> str:
    """The `quest` verb: show the quest, or advance it (`quest accept|begin|finish`)."""
    run = _run(session.player_id)
    event = arg.strip().lower()
    if not event or event == "status":
        line = _QUEST.labels.get(run.state, run.state)
        if _ENGINE.is_done(run):
            return f"[Coilward Contract] {line}"
        actions = _ENGINE.actions(run)
        return f"[Coilward Contract] {line}\n  You can: {', '.join(actions) or '(nothing)'}"
    outcome = _ENGINE.advance(run, event)
    if not isinstance(outcome, Fired):
        return f"You can't do that now. ({outcome.reason})"
    reward = ""
    if outcome.effect == "award_xp" and session.stats is not None:
        from parts.combat import award_xp

        reward = "\n" + award_xp(session, _XP_REWARD)
    return f"[Coilward Contract] {_QUEST.labels.get(run.state, run.state)}{reward}"


def reset_quests() -> None:
    """Test hook: clear all in-flight quest runs."""
    _RUNS.clear()
