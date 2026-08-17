"""CARD: journey -- turn a compact intent (an ordered list of waypoints) into a full GameSpec: a
linear region and a travel-driven quest. The first content GENERATOR for the game pipeline.

game_linker (MOD-10.085) persists and validates a GameSpec; game_session (MOD-10.087) operates and
recovers it. Both take a fully-formed spec. This is the step BEFORE: it derives that spec from a
small, human-shaped intent -- "a journey through these waypoints" -- so a whole playable, durable,
recoverable region comes from a one-line description -- the Oregon-Trail archetype, generated:
a room per waypoint in order, and a quest whose steps fire on arrival, ending at the last stop.

Deterministic and pure: the same waypoints yield the same GameSpec (so the linked seed content is
reproducible). It knows only game_linker's spec dataclasses -- no world, no engine -- the authoring
layer, not the runtime. The generated spec is built to pass the Linker's own gates
(rooms reachable, quest terminal reachable, every on_enter a real room) and to be
operable by travel alone, so it drives game_session to RESUMED end to end.

Grammar before worlds: kernel/domains, composing game_linker's spec; kernel/seedlab imports neither.
Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import re

from kernel.domains.game_linker import GameSpec, QuestArc, QuestStep, RoomSpec

_LABEL = re.compile(r"^[a-z0-9_]+$")


class JourneyError(Exception):
    """A journey cannot be generated (no waypoints, or a non-snake_case label). Fails loud."""


def journey_region(
    region: str,
    waypoints: list[str],
    *,
    start: str = "trailhead",
    quest_id: str = "",
) -> GameSpec:
    """Generate a GameSpec for a linear journey: a `start` room, then one room per waypoint in order
    (each linked north/south to its neighbours), plus a travel-driven quest that fires on entering
    each waypoint and completes at the last. Fails loud (JourneyError) on no waypoints, a dup, or a
    label that is not lowercase_snake_case (the Linker would reject it too; caught early)."""
    if not region or not region.strip():
        raise JourneyError("a journey needs a non-empty region name")  # noqa: TRY003
    if not waypoints:
        raise JourneyError("a journey needs at least one waypoint")  # noqa: TRY003
    labels = [start, *waypoints]
    if len(set(labels)) != len(labels):
        raise JourneyError(f"journey room labels must be unique: {labels}")  # noqa: TRY003
    for label in labels:
        if not _LABEL.match(label):
            raise JourneyError(f"journey label {label!r} must be lowercase_snake_case")  # noqa: TRY003

    # Rooms: start -> waypoint[0] -> waypoint[1] -> ... , each linked to its neighbours.
    rooms: list[RoomSpec] = []
    for i, label in enumerate(labels):
        exits: dict[str, str] = {}
        if i + 1 < len(labels):
            exits["north"] = labels[i + 1]
        if i > 0:
            exits["south"] = labels[i - 1]
        rooms.append(RoomSpec(label=label, exits=exits))

    # Quest: setting_out --enter wp0--> leg_1 --enter wp1--> leg_2 --...--> arrived (the terminal).
    states = ["setting_out", *[f"leg_{i + 1}" for i in range(len(waypoints) - 1)], "arrived"]
    steps = tuple(
        QuestStep(
            state=states[i],
            event=f"reach_{i + 1}",
            to=states[i + 1],
            on_enter=waypoints[i],
        )
        for i in range(len(waypoints))
    )
    quest = QuestArc(
        id=quest_id or f"{region}_journey",
        start="setting_out",
        steps=steps,
        terminal=("arrived",),
        name=f"The {region.replace('_', ' ').title()} Journey",
    )
    return GameSpec(region=region, rooms=tuple(rooms), start=start, quest=quest)
