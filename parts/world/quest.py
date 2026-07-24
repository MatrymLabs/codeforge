"""CARD: quest -- the game adapter for the Workflow Engine: a seed's quests as workflows.

A quest is a workflow (`parts/shelf/workflow`) whose states a player walks with the `quest` verb.
It proves the reusable core lives in the game: the SAME `WorkflowEngine` that drives a business
onboarding checklist (`parts/onboarding`) drives these quests -- only the effect differs (here, a
completed contract awards XP). The arcs are DATA: a seed ships `quest.yaml` (its primary arc) and
any number of `quests/*.yaml`, so a world declares many stories, not one hard-coded in Python.

A player carries one run PER quest; the map of their in-flight states persists (save_state /
restore_state), so a story survives a restart. World events (a foe felled, a room entered) advance
whichever quest declares that trigger; the `quest` verb is always the fallback.
"""

from __future__ import annotations

import json

from parts.shelf.statemachine import Fired
from parts.shelf.workflow import Instance, Step, Workflow, WorkflowEngine, build_workflow
from parts.world.seed import SEED_DIR, QuestSpec, load_quest
from parts.world.session import Session


def _built_in_quest() -> tuple[Workflow, str, int]:
    """The default arc for a seed that ships no quests at all (a bare seed)."""
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
    """Build a quest workflow from a seed's quest spec -- the arc is data, not Python."""
    steps = [Step(s["state"], s["event"], s["to"], effect=s.get("effect")) for s in spec["steps"]]
    workflow = build_workflow(
        spec["id"],
        start=spec["start"],
        steps=steps,
        terminal=spec["terminal"],
        labels=spec["labels"],
    )
    return workflow, spec["name"], spec["reward_xp"]


def _load_specs() -> list[QuestSpec]:
    """Every quest spec this seed ships: `quest.yaml` first (the primary arc), then `quests/*.yaml`
    in name order, then GENERATED bounties (one hunt-contract per combatant foe -- side-content at
    volume, parts.world.bounties). The world stays data; adding a story is a YAML file."""
    specs: list[QuestSpec] = []
    primary = load_quest(SEED_DIR / "quest.yaml")
    if primary:
        specs.append(primary)
    quests_dir = SEED_DIR / "quests"
    if quests_dir.is_dir():
        for path in sorted(quests_dir.glob("*.yaml")):
            spec = load_quest(path)
            if spec:
                specs.append(spec)
    from parts.world.bounties import generate_bounties
    from parts.world.seed import load_npcs

    specs.extend(generate_bounties(load_npcs(SEED_DIR / "npcs.yaml")))
    return specs


class _Quest:
    """One loaded quest: its workflow, display name, XP reward, engine, and world-event triggers."""

    def __init__(self, workflow: Workflow, name: str, xp: int, spec: QuestSpec | None) -> None:
        self.workflow = workflow
        self.name = name
        self.xp = xp
        self.engine = WorkflowEngine(workflow)
        self.events = {event for (_state, event) in workflow.roles}  # every event this quest knows
        # (kind, target label) -> the event that world action fires in THIS quest.
        self.triggers: dict[tuple[str, str], str] = {}
        for step in spec["steps"] if spec else []:
            for key, kind in _TRIGGER_KEYS.items():
                target = step.get(key)
                if target:
                    self.triggers[(kind, str(target))] = step["event"]


# step trigger key -> world-event kind. defeat = an npc falls, take = an item is picked up,
# enter = a room is entered.
_TRIGGER_KEYS = {"on_defeat": "defeat", "on_take": "take", "on_enter": "enter"}


def _load_quests() -> dict[str, _Quest]:
    """The seed's quests by id (the built-in contract if the seed ships none)."""
    specs = _load_specs()
    if not specs:
        wf, name, xp = _built_in_quest()
        return {wf.workflow_id: _Quest(wf, name, xp, None)}
    quests: dict[str, _Quest] = {}
    for spec in specs:
        wf, name, xp = _from_seed(spec)
        quests[spec["id"]] = _Quest(wf, name, xp, spec)
    return quests


_QUESTS = _load_quests()
# (kind, target) -> [quest_id, ...]: EVERY quest a world action advances. A single foe can advance
# both an authored arc and its generated bounty, so a defeat fans out to all who trigger on it.
_EVENT_ROUTES: dict[tuple[str, str], list[str]] = {}
for _qid, _quest in _QUESTS.items():
    for _trigger in _quest.triggers:
        _EVENT_ROUTES.setdefault(_trigger, []).append(_qid)

_RUNS: dict[str, dict[str, Instance]] = {}  # player_id -> {quest_id: their run of that quest}


def _run(player_id: str, quest_id: str) -> Instance:
    """The player's run of one quest, opened fresh at its start the first time it is touched."""
    player_runs = _RUNS.setdefault(player_id, {})
    if quest_id not in player_runs:
        player_runs[quest_id] = _QUESTS[quest_id].engine.open()
    return player_runs[quest_id]


def _line(quest: _Quest, run: Instance) -> str:
    """One quest's `[Name] label` line for the current state."""
    return f"[{quest.name}] {quest.workflow.labels.get(run.state, run.state)}"


def _list_all(session: Session) -> str:
    """The STORY quests (hand-authored arcs), with the player's state and moves. Generated bounties
    are counted, not listed here -- they live under the `contracts` verb, never flooding this."""
    from parts.world.bounties import is_bounty

    blocks = []
    bounty_count = 0
    for qid, quest in _QUESTS.items():
        if is_bounty(qid):
            bounty_count += 1
            continue
        run = _run(session.player_id, qid)
        line = _line(quest, run)
        if quest.engine.is_done(run):
            blocks.append(line + " (complete)")
        else:
            actions = quest.engine.actions(run)
            hint = f"  ({qid}: {', '.join(actions)})" if actions else ""
            blocks.append(line + hint)
    tail = f"\n{bounty_count} hunt-contracts on the board (type CONTRACTS)." if bounty_count else ""
    return "Your quests:\n" + "\n".join(blocks) + tail


def contracts_view(session: Session) -> str:
    """The `contracts` verb: the bounty board -- every generated hunt-contract and its status."""
    from parts.world.bounties import is_bounty

    open_lines: list[str] = []
    done_lines: list[str] = []
    for qid, quest in _QUESTS.items():
        if not is_bounty(qid):
            continue
        run = _run(session.player_id, qid)
        label = quest.workflow.labels.get(run.state, run.state)
        (done_lines if quest.engine.is_done(run) else open_lines).append(f"  {label}")
    if not open_lines and not done_lines:
        return "There are no hunt-contracts on the board."
    parts = ["The bounty board:"]
    parts.extend(open_lines)
    if done_lines:
        parts.append(f"Collected: {len(done_lines)}.")
    return "\n".join(parts)


def _advance(session: Session, quest_id: str, event: str) -> str:
    """Fire one event in one quest, apply its effect, and report the new state."""
    quest = _QUESTS[quest_id]
    run = _run(session.player_id, quest_id)
    outcome = quest.engine.advance(run, event)
    if not isinstance(outcome, Fired):
        return f"You can't do that now. ({outcome.reason})"
    extra = _apply_effect(quest, outcome.effect, session)
    return f"{_line(quest, run)}{extra}"


def quest_view(session: Session, arg: str = "") -> str:
    """The `quest` verb. Bare: list every quest. `quest <id>`: show one. `quest <id> <event>` or
    `quest <event>`: advance (a bare event applies to the first quest that legally accepts it, so
    single-quest play still reads `quest accept`)."""
    arg = arg.strip().lower()
    if not arg or arg == "status":
        return _list_all(session)
    parts = arg.split()
    if parts[0] in _QUESTS:
        quest_id = parts[0]
        if len(parts) == 1:
            return _line(_QUESTS[quest_id], _run(session.player_id, quest_id))
        return _advance(session, quest_id, parts[1])
    # A bare event: apply it to the first quest that can legally fire it right now...
    for quest_id, quest in _QUESTS.items():
        if arg in quest.engine.actions(_run(session.player_id, quest_id)):
            return _advance(session, quest_id, arg)
    # ...else, if some quest KNOWS the event (just not now), let its engine give the real refusal.
    for quest_id, quest in _QUESTS.items():
        if arg in quest.events:
            return _advance(session, quest_id, arg)
    return f"No quest here can do '{arg}'. Type QUEST to see your quests."


def _apply_effect(quest: _Quest, effect: str | None, session: Session) -> str:
    """Apply a quest step's named effect to the world. The workflow only NAMES effects (it never
    mutates); the game applies them here. `award_xp` grants the quest's reward; `open_door:<id>`
    reforges a barrier (e.g. the broken bridge). Returns any extra line to append to the reply."""
    if not effect:
        return ""
    if effect == "award_xp" and session.stats is not None:
        from parts.world.progression_awards import award_xp

        return "\n" + award_xp(session, quest.xp)
    if effect.startswith("open_door:"):
        from parts.world import doors

        doors.open_gate(effect.split(":", 1)[1])  # the label already narrates the opening
    return ""


def on_event(session: Session, kind: str, target: str) -> str | None:
    """World-event hook: if `kind` (defeat|take|enter) on `target` advances any quest, fire that
    step and return its line. Returns None when nothing triggers, or the arc isn't at that beat yet
    (the engine refuses an out-of-order move -- the `quest <event>` verb stays the fallback)."""
    quest_ids = _EVENT_ROUTES.get((kind, target))
    if not quest_ids:
        return None
    lines = []
    for quest_id in quest_ids:  # a defeat can advance an authored arc AND its bounty at once
        quest = _QUESTS[quest_id]
        run = _run(session.player_id, quest_id)
        outcome = quest.engine.advance(run, quest.triggers[(kind, target)])
        if isinstance(outcome, Fired):
            extra = _apply_effect(quest, outcome.effect, session)
            lines.append(f"{_line(quest, run)}{extra}")
    return "\n".join(lines) if lines else None


def save_state(player_id: str) -> str:
    """A player's in-flight quest states as a {quest_id: state} JSON map, for persistence. "" when
    they have touched no quest yet, so a brand-new character stores nothing."""
    runs = _RUNS.get(player_id)
    if not runs:
        return ""
    return json.dumps({qid: run.state for qid, run in runs.items()}, sort_keys=True)


def restore_state(player_id: str, raw: str) -> None:
    """Reseed a player's quest runs from a persisted {quest_id: state} map so their stories survive
    a restart. Skips any unknown quest or state (a record from another seed) -- never a crash. A
    bare state string (the pre-multi-quest format) is honored against the primary quest."""
    if not raw:
        return
    try:
        states = json.loads(raw)
    except (ValueError, TypeError):
        states = raw  # a legacy single-state string; matched to the primary quest below
    if isinstance(states, str):
        primary = next(iter(_QUESTS))
        states = {primary: states}
    if not isinstance(states, dict):
        return
    for quest_id, state in states.items():
        quest = _QUESTS.get(quest_id)
        if quest and isinstance(state, str) and state in quest.workflow.machine.states:
            run = Instance(quest.workflow.workflow_id, state, [], {})
            _RUNS.setdefault(player_id, {})[quest_id] = run


def reset_quests() -> None:
    """Test hook: clear all in-flight quest runs."""
    _RUNS.clear()
