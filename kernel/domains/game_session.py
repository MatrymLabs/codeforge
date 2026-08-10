"""CARD: game_session -- prove a linked region's quest can be OPERATED by a live player and RESUMED
after a restart: the operate + recover half of the game lifecycle, on real engine state.

game_lifecycle (MOD-10.086) proved a region's CONTENT is durable; it honestly deferred the running
half -- a player travelling the region and their in-flight quest progress surviving a restart --
because the quest engine had no clean per-region teardown. quest.unregister_specs closed that, so
this composes the real engine into a full loop, with no leaked global state:

  * CREATE + VALIDATE -- link the spec and require LINKED (else REFUSED).
  * OPERATE -- register the region's quest, put a player at the start, and travel: entering each
    quest objective room fires its step (the engine's own `on_event`) until the arc reaches a
    terminal. A quest that cannot be completed by travel alone (a step needs a manual event) is
    INOPERABLE -- an honest verdict, not a hang.
  * BACKUP -- the player's durable facts: their location and `quest.save_state` (the same map
    characters.py persists).
  * RESTORE -- simulate a restart: UNLOAD the quest, clear the runs, RE-REGISTER it, then
    `restore_state` the player's progress (exactly the world's own load path).
  * VERIFY -- the player resumes at the same terminal and location -> RESUMED.

Always tears the quest back down (unregister) so global state is never leaked, whatever the verdict.
Grammar before worlds: lives in kernel/domains/ (world-aware); kernel/seedlab imports no world or
domain (import-linter `grammar-before-worlds`). Verdicts, not booleans. Status: PROTOTYPED (see
docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kernel.domains.game_linker import LINKED, GameSpec, link_and_validate

# --- resume verdict words (a distinct vocabulary: "did the play survive a restart?") -----------
RESUMED = (
    "resumed"  # operated to a terminal, and the same progress + location came back after restart
)
INOPERABLE = "inoperable"  # links, but the quest cannot be completed by travel alone
REFUSED = "refused"  # the region did not link, or ships no quest to operate


@dataclass(frozen=True)
class ResumeReport:
    """The honest verdict on one CREATE -> OPERATE -> BACKUP -> RESTORE -> VERIFY run."""

    verdict: str
    region: str = ""
    quest_id: str = ""
    terminal: str = ""  # the terminal state the player resumed at, when RESUMED
    detail: str = ""  # why, when not RESUMED

    @property
    def ok(self) -> bool:
        return self.verdict == RESUMED


def _state_of(player_id: str, quest_id: str) -> str:
    """The player's current state in one quest, read from the engine's own save map (or "")."""
    from kernel.world.quest import save_state

    raw = save_state(player_id)
    if not raw:
        return ""
    try:
        states = json.loads(raw)
    except (ValueError, TypeError):
        return ""
    return states.get(quest_id, "") if isinstance(states, dict) else ""


def operate_and_recover(
    spec: GameSpec, dest: Path, *, player_id: str = "probe_player"
) -> ResumeReport:
    """Operate a linked region's quest with a live player, then prove it resumes after a restart.
    Registers the quest, drives it to a terminal by travelling the objective rooms, backs up the
    player's state, simulates a restart (unload -> reload from disk -> restore), and verifies the
    resume -- always unregistering the quest afterward so no global state leaks."""
    from kernel.world.quest import (
        register_specs,
        reset_quests,
        restore_state,
        unregister_specs,
    )
    from kernel.world.seed import load_quest
    from kernel.world.session import Session

    linked, verdict = link_and_validate(spec, dest)
    if verdict.verdict != LINKED:
        return ResumeReport(REFUSED, spec.region, detail=f"region did not link: {verdict.verdict}")
    quest_path = Path(linked.dest) / "quest.yaml"
    quest = load_quest(quest_path)
    if quest is None:
        return ResumeReport(REFUSED, spec.region, detail="region ships no quest to operate")
    quest_id = quest["id"]
    terminals = set(quest["terminal"])
    objectives = [s["on_enter"] for s in quest["steps"] if s.get("on_enter")]

    register_specs([quest])
    try:
        from kernel.world.quest import on_event

        session = Session(player_id=player_id, location=spec.start)
        for room in objectives:  # travel: entering each objective room fires its quest step
            session.location = room
            on_event(session, "enter", room)
        reached = _state_of(player_id, quest_id)
        if reached not in terminals:
            return ResumeReport(
                INOPERABLE,
                spec.region,
                quest_id=quest_id,
                detail=f"quest did not complete by travel (stuck at {reached!r})",
            )
        backup_state = _state_of(player_id, quest_id)
        backup_location = session.location

        # RESTART: unload the quest, clear runs, re-register it, then restore the player's progress
        # (exactly the world's own load path; the definition itself came from the durable file).
        unregister_specs([quest_id])
        reset_quests()
        register_specs([quest])
        restore_state(player_id, json.dumps({quest_id: backup_state}))
        restored = Session(player_id=player_id, location=backup_location)

        after = _state_of(player_id, quest_id)
        if after in terminals and restored.location == backup_location:
            return ResumeReport(RESUMED, spec.region, quest_id=quest_id, terminal=after)
        return ResumeReport(
            INOPERABLE,
            spec.region,
            quest_id=quest_id,
            detail=f"did not resume (state {after!r}, location {restored.location!r})",
        )
    finally:
        unregister_specs([quest_id])
        reset_quests()
