"""CARD: quest -- the game adapter for the Workflow Engine: a regional quest as a workflow.

A quest is a workflow (`parts/workflow`) whose states a player walks with the `quest` MUD verb.
It proves the reusable core lives in the game: the SAME `WorkflowEngine` that drives a business
onboarding checklist (`parts/onboarding`) drives this quest -- only the effect differs (here, a
completed contract awards XP). The workflow is defined as data, so a seed could ship its own.
"""

from __future__ import annotations

from parts.seed import SEED_DIR, QuestSpec, load_quest
from parts.session import Session
from parts.statemachine import Fired
from parts.workflow import Instance, Step, Workflow, WorkflowEngine, build_workflow


def _built_in_quest() -> tuple[Workflow, str, int]:
    """The default arc for a seed that ships no quest.yaml (e.g. first-forge, spiral-ascent)."""
    workflow = build_workflow(
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
    return workflow, "Coilward Contract", 50


def _from_seed(spec: QuestSpec) -> tuple[Workflow, str, int]:
    """Build a quest workflow from a seed's quest.yaml -- the arc is data, not Python."""
    steps = [Step(s["state"], s["event"], s["to"], effect=s.get("effect")) for s in spec["steps"]]
    workflow = build_workflow(
        spec["id"],
        start=spec["start"],
        steps=steps,
        terminal=spec["terminal"],
        labels=spec["labels"],
    )
    return workflow, spec["name"], spec["reward_xp"]


# The world is data: if this seed ships a quest, walk THAT arc; otherwise the built-in contract.
_SEED_QUEST = load_quest(SEED_DIR / "quest.yaml")
_QUEST, _QUEST_NAME, _XP_REWARD = _from_seed(_SEED_QUEST) if _SEED_QUEST else _built_in_quest()
_ENGINE = WorkflowEngine(_QUEST)

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
            return f"[{_QUEST_NAME}] {line}"
        actions = _ENGINE.actions(run)
        return f"[{_QUEST_NAME}] {line}\n  You can: {', '.join(actions) or '(nothing)'}"
    outcome = _ENGINE.advance(run, event)
    if not isinstance(outcome, Fired):
        return f"You can't do that now. ({outcome.reason})"
    extra = _apply_effect(outcome.effect, session)
    return f"[{_QUEST_NAME}] {_QUEST.labels.get(run.state, run.state)}{extra}"


def _apply_effect(effect: str | None, session: Session) -> str:
    """Apply a quest step's named effect to the world. The workflow only NAMES effects (it never
    mutates); the game applies them here. `award_xp` grants the reward; `open_door:<id>` reforges
    a barrier (e.g. the broken bridge). Returns any extra line to append to the reply."""
    if not effect:
        return ""
    if effect == "award_xp" and session.stats is not None:
        from parts.combat import award_xp

        return "\n" + award_xp(session, _XP_REWARD)
    if effect.startswith("open_door:"):
        from parts import doors

        doors.open_gate(effect.split(":", 1)[1])  # the label already narrates the opening
    return ""


def reset_quests() -> None:
    """Test hook: clear all in-flight quest runs."""
    _RUNS.clear()
