"""CARD: quest -- the game adapter for the Workflow Engine: a seed's quests as workflows.

A quest is a workflow (`kernel/shelf/workflow`) whose states a player walks with the `quest` verb.
It proves the reusable core lives in the game: the SAME `WorkflowEngine` that drives a business
onboarding checklist (`kernel/onboarding`) drives these quests -- only the effect differs (here, a
completed contract awards XP). The arcs are DATA: a seed ships `quest.yaml` (its primary arc) and
any number of `quests/*.yaml`, so a world declares many stories, not one hard-coded in Python.

A player carries one run PER quest; the map of their in-flight states persists (save_state /
restore_state), so a story survives a restart. World events (a foe felled, a room entered) advance
whichever quest declares that trigger; the `quest` verb is always the fallback.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from kernel.shelf.statemachine import Fired
from kernel.shelf.workflow import Instance, Step, Workflow, WorkflowEngine, build_workflow
from kernel.world.seed import BLUEPRINT_DIR, Npc, QuestSpec, load_quest
from kernel.world.session import Session


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
    """The seed's AUTHORED quest specs: `quest.yaml` (the primary arc) then `quests/*.yaml` in name
    order. Generated bounties are added later (register_bounties), once the full foe set (with the
    procedural Spiral) is assembled. The world stays data; a story is a YAML file."""
    specs: list[QuestSpec] = []
    primary = load_quest(BLUEPRINT_DIR / "quest.yaml")
    if primary:
        specs.append(primary)
    quests_dir = BLUEPRINT_DIR / "quests"
    if quests_dir.is_dir():
        for path in sorted(quests_dir.glob("*.yaml")):
            spec = load_quest(path)
            if spec:
                specs.append(spec)
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
_TRIGGER_KEYS = {
    "on_defeat": "defeat",
    "on_take": "take",
    "on_enter": "enter",
    "on_cull": "cull",  # a creature TYPE felled (by keyword), not one specific foe: cull-N quests
    "on_forage": "forage",  # a (zone-scoped) material harvested: forage-N quests
}


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


def register_bounties(npcs: dict[str, Npc]) -> None:
    """Generate hunt-contracts from the LIVE foe set and fold them into the quest engine. Called by
    world.py once the world -- including the procedural Spiral -- is fully assembled, so a bounty
    exists for EVERY combatant foe (seed + generated), not only authored ones. Idempotent."""
    from kernel.world.bounties import generate_bounties  # noqa: PLC0415

    # Ambient wilderness life (the mass-generated bestiary) gets no hunt-contract: a million meadow-
    # hares must not mint a million bounty quests. Notable foes -- every hand-authored and Spiral
    # foe, which carry no `ambient` flag -- keep theirs. This is the boot-time hot spot at scale.
    notable = {label: npc for label, npc in npcs.items() if not npc.get("ambient")}
    _fold_in(generate_bounties(notable))


def register_errands(
    settlements: list[dict[str, object]], destinations: list[dict[str, object]]
) -> None:
    """Generate travel-errands from the settlements + the map's destinations and fold them into the
    engine (kernel.world.errands). Called by world.py after the world is assembled. Idempotent."""
    from kernel.world.errands import generate_errands  # noqa: PLC0415

    _fold_in(generate_errands(settlements, destinations))


def register_storylines(
    zones: list[dict[str, object]],
    settlements: list[dict[str, object]],
    dungeons: list[dict[str, object]],
) -> None:
    """Generate one narrative chain per zone that pairs a town with a dungeon, and fold them into
    the engine (kernel.world.storylines). Called by world.py once assembled. Idempotent."""
    from kernel.world.storylines import generate_storylines  # noqa: PLC0415

    _fold_in(generate_storylines(zones, settlements, dungeons))


def register_culls(zones: list[dict[str, object]]) -> None:
    """Generate zone-scoped 'cull N of a kind' contracts at volume and fold them into the engine
    (kernel.world.cull). Called by world.py after the world is assembled. Idempotent."""
    from kernel.world.cull import generate_culls  # noqa: PLC0415

    _fold_in(generate_culls(zones))


def register_forages(zones: list[dict[str, object]]) -> None:
    """Generate zone-scoped 'gather N of a material' contracts and fold them into the engine
    (kernel.world.forage). Called by world.py after the world is assembled. Idempotent."""
    from kernel.world.forage import generate_forages  # noqa: PLC0415

    _fold_in(generate_forages(zones))


def register_crawls(dungeons: list[dict[str, object]]) -> None:
    """Generate one 'descend to the heart of a dungeon' contract per dungeon and fold them into the
    engine (kernel.world.dungeon_crawl). Called by world.py once assembled. Idempotent."""
    from kernel.world.dungeon_crawl import generate_crawls  # noqa: PLC0415

    _fold_in(generate_crawls(dungeons))


def register_spine(zones: list[dict[str, object]]) -> None:
    """Lay the world's main-road spine (the Forgeward Road) and fold it into the engine
    (kernel.world.spine). Called by world.py after the world is assembled. Idempotent."""
    from kernel.world.spine import forge_spine  # noqa: PLC0415

    spec = forge_spine(zones)
    _fold_in([spec] if spec is not None else [])


def all_ids() -> list[str]:
    """Every registered quest id (read-only). Lets other modules survey the board without reaching
    into the private registry -- e.g. zone_story counting a zone's culls, or analytics."""
    return list(_QUESTS)


def hook_of(quest_id: str) -> str | None:
    """A quest's START-state label -- its player-independent 'hook' (what the board first says), or
    None for an unknown id. Used to show a quest in a dossier without opening a per-player run."""
    quest = _QUESTS.get(quest_id)
    if quest is None:
        return None
    return quest.workflow.labels.get(quest.workflow.machine.start)


def register_specs(specs: list[QuestSpec]) -> None:
    """Fold a pre-built list of generated QuestSpecs into the engine. For archetypes whose generator
    also produces side-artifacts world.py must place (e.g. delivery's parcel items), so world.py
    builds once, places the artifacts, and folds the specs here. Idempotent."""
    _fold_in(specs)


def unregister_specs(quest_ids: list[str]) -> None:
    """The clean inverse of register_specs: UNLOAD the named quests -- drop each from the registry,
    remove its world-event routes, and clear any in-flight runs -- so a region (or a test) can load
    quests and later unload them without leaking global state. Unknown ids are ignored (idempotent).
    The missing per-region teardown a persistent world needs to swap content in and out."""
    for quest_id in quest_ids:
        quest = _QUESTS.pop(quest_id, None)
        if quest is None:
            continue
        for trigger in quest.triggers:
            routes = _EVENT_ROUTES.get(trigger)
            if routes and quest_id in routes:
                routes.remove(quest_id)
                if not routes:
                    del _EVENT_ROUTES[trigger]
        for player_runs in _RUNS.values():
            player_runs.pop(quest_id, None)


def _fold_in(specs: list[QuestSpec]) -> None:
    """Register generated QuestSpecs into the engine (skipping any already known) and route their
    triggers. The shared tail of register_bounties/register_errands."""
    for spec in specs:
        if spec["id"] in _QUESTS:
            continue  # never double-register
        workflow, name, xp = _from_seed(spec)
        quest = _Quest(workflow, name, xp, spec)
        _QUESTS[spec["id"]] = quest
        for trigger in quest.triggers:
            _EVENT_ROUTES.setdefault(trigger, []).append(spec["id"])


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


def active_quest(session: Session) -> dict[str, str] | None:
    """The player's foremost UNFINISHED story quest, as a small projection for a GMCP tracker, or
    None when every authored arc is done. Bounties are excluded -- they live on the contracts board,
    and one tracker line should follow the story, not the churn of generated hunts. Read-only: it
    never opens or advances a run beyond what viewing already does (architecture law 1)."""
    from kernel.world.bounties import is_bounty  # noqa: PLC0415

    for qid, quest in _QUESTS.items():
        if is_bounty(qid):
            continue
        run = _run(session.player_id, qid)
        if not quest.engine.is_done(run):
            return {"name": quest.name, "step": quest.workflow.labels.get(run.state, run.state)}
    return None


def _list_all(session: Session) -> str:
    """The STORY quests (hand-authored arcs), with the player's state and moves. The generated
    VOLUME (bounties, culls) is counted, not listed -- it lives under `contracts`, never flooding
    this."""
    from kernel.world.bounties import is_bounty  # noqa: PLC0415
    from kernel.world.cull import is_cull  # noqa: PLC0415
    from kernel.world.forage import is_forage  # noqa: PLC0415

    blocks = []
    board_count = 0
    for qid, quest in _QUESTS.items():
        if (
            is_bounty(qid) or is_cull(qid) or is_forage(qid)
        ):  # high-volume contracts: count, not list
            board_count += 1
            continue
        run = _run(session.player_id, qid)
        line = _line(quest, run)
        if quest.engine.is_done(run):
            blocks.append(line + " (complete)")
        else:
            actions = quest.engine.actions(run)
            hint = f"  ({qid}: {', '.join(actions)})" if actions else ""
            blocks.append(line + hint)
    tail = f"\n{board_count} contracts on the board (type CONTRACTS)." if board_count else ""
    return "Your quests:\n" + "\n".join(blocks) + tail


def contracts_view(session: Session) -> str:
    """The `contracts` verb: the notice board -- every generated side-quest (hunt-contract or
    travel-errand) and its status, grouped so the board reads clearly."""
    from kernel.world.bounties import is_bounty  # noqa: PLC0415
    from kernel.world.errands import is_errand  # noqa: PLC0415
    from kernel.world.storylines import is_storyline  # noqa: PLC0415

    def _board(match) -> tuple[list[str], int]:
        openq: list[str] = []
        done = 0
        for qid, quest in _QUESTS.items():
            if not match(qid):
                continue
            run = _run(session.player_id, qid)
            if quest.engine.is_done(run):
                done += 1
            else:
                openq.append(f"  {quest.workflow.labels.get(run.state, run.state)}")
        return openq, done

    from kernel.world.cull import is_cull  # noqa: PLC0415
    from kernel.world.forage import is_forage  # noqa: PLC0415

    tales, tales_done = _board(is_storyline)
    hunts, hunts_done = _board(is_bounty)
    errands, errands_done = _board(is_errand)
    cull_total, cull_active, cull_done = _tally(session, is_cull)
    forage_total, forage_active, forage_done = _tally(session, is_forage)
    if not (
        tales
        or hunts
        or errands
        or tales_done
        or hunts_done
        or errands_done
        or cull_total
        or forage_total
    ):
        return "There is nothing posted on the notice board."
    parts = ["The notice board:"]
    if tales or tales_done:
        parts.append("Tales:")
        parts.extend(tales)
        if tales_done:
            parts.append(f"  (told: {tales_done})")
    if hunts or hunts_done:
        parts.append("Hunt-contracts:")
        parts.extend(hunts)
        if hunts_done:
            parts.append(f"  (collected: {hunts_done})")
    if errands or errands_done:
        parts.append("Errands:")
        parts.extend(errands)
        if errands_done:
            parts.append(f"  (done: {errands_done})")
    if cull_total:  # too many to list one by one, like a real board: summarised, not itemised
        prog = (
            f" ({cull_active} in progress, {cull_done} cleared)" if cull_active or cull_done else ""
        )
        parts.append(f"Cull-contracts: {cull_total} posted{prog}. Fell any beast to answer one.")
    if forage_total:
        fp = (
            f" ({forage_active} in progress, {forage_done} done)"
            if forage_active or forage_done
            else ""
        )
        parts.append(f"Forage-contracts: {forage_total} posted{fp}. Work any node to answer one.")
    return "\n".join(parts)


def _tally(session: Session, match: Callable[[str], bool]) -> tuple[int, int, int]:
    """(posted, in-progress, done) contracts of a kind for a player, WITHOUT opening a run per quest
    -- the board summarises the high-volume archetypes instead of listing them. Only runs the player
    already touched are inspected; the total is a cheap key scan."""
    total = sum(1 for qid in _QUESTS if match(qid))
    active = done = 0
    for qid, run in _RUNS.get(session.player_id, {}).items():
        if match(qid):
            if _QUESTS[qid].engine.is_done(run):
                done += 1
            else:
                active += 1
    return total, active, done


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
    """Apply a quest step's named effect(s) to the world. The workflow only NAMES effects (it never
    mutates); the game applies them here. Several effects may be chained with ';' (e.g.
    `award_xp;grant_rep:making:50`), each applied in order. Returns the extra lines to append."""
    if not effect:
        return ""
    parts = [one.strip() for one in effect.split(";") if one.strip()]
    return "".join(_apply_one(quest, one, session) for one in parts)


def _apply_one(quest: _Quest, effect: str, session: Session) -> str:
    """Apply ONE named effect. `award_xp` grants the quest's reward; `open_door:<id>` reforges a
    barrier; `grant_rep:<order>:<amount>` earns standing with an Order. Returns any extra line."""
    if effect == "award_xp" and session.stats is not None:
        from kernel.world.progression import get_next_level_threshold  # noqa: PLC0415
        from kernel.world.progression_awards import award_xp  # noqa: PLC0415

        threshold = get_next_level_threshold(session.level)
        reward = quest.xp if threshold is None else min(quest.xp, max(0, threshold - session.xp))
        return "\n" + award_xp(session, reward)
    if effect.startswith("open_door:"):
        from kernel.world import doors  # noqa: PLC0415

        doors.open_gate(effect.split(":", 1)[1])  # the label already narrates the opening
    if effect.startswith("grant_rep:"):
        # `grant_rep:<order>:<amount>` -- a quest's deed earns standing with an Order (and spills
        # over its allies/rivals). The reputation web is how faction-gated content is unlocked.
        from kernel.world.reputation import grant  # noqa: PLC0415

        _, order, amount = effect.split(":", 2)
        rose = grant(session, order, int(amount))
        return f"\n{rose}" if rose else ""
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
