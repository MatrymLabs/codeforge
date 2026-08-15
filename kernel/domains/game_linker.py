"""CARD: game_linker -- the game domain's Linker: a validated GameSpec becomes REAL, persistent seed
content (a region of rooms, plus an optional quest arc), validated through the engine's own
world + quest loaders.

The missing bridge. The seedlab pipeline stops at a lifecycle record (a Seed that SELECTED the game
module); nothing turned a spec into a runnable world. This is that step for the integrated,
persistent MMORPG (no instancing): a GameSpec emits `rooms.yaml` (+ `quest.yaml` when a quest is
given) -- canonical seed content a Seed boots and that survives restart by construction -- and the
Linker VALIDATES it by loading through the real `kernel.world.seed.load_rooms` / `load_quest`
(inheriting the engine's own gates) plus two cross-cutting checks the loaders don't do alone:
room reachability from the start, and (for a quest) that every `on_enter` names a real room in the
region and that a terminal state is reachable from the quest's start.

Same emit-then-validate-by-running discipline as the CLI generator (cli_generator.py in seedlab),
but the target is a game world and the validators are the live loaders rather than a subprocess.

Grammar before worlds, from the game side: this lives in kernel/domains/ (world-aware) and imports
kernel/world/ -- which the neutral platform (kernel/seedlab) is forbidden to do (import-linter
contract `grammar-before-worlds`). A classroom Seed never loads this. World code is imported lazily
so merely importing this module stays light. Verdicts, not booleans: LINKED (loads AND everything
reachable) / UNREACHABLE (loads but an orphan room or an unreachable quest terminal) / REFUSED (a
loader rejected the content, or a quest `on_enter` names no room). Status: PROTOTYPED (see
docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --- verdict words (a distinct vocabulary: "can this region become a live world?") -------------
LINKED = "linked"  # loads AND every room + (if present) the quest terminal is reachable
UNREACHABLE = "unreachable"  # loads, but an orphan room or an unreachable quest terminal/state
REFUSED = "refused"  # a loader rejected the content, or a quest `on_enter` names no room


class GameLinkError(Exception):
    """A GameSpec cannot be linked (structurally empty, or a start naming no room). Fails loud."""


@dataclass(frozen=True)
class RoomSpec:
    """One room in a region: a permanent lowercase_snake_case `label`, optional `name`/`desc`
    (the loader defaults them), and `exits` mapping a direction to another room's label."""

    label: str
    name: str = ""
    desc: str = ""
    exits: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class QuestStep:
    """One transition of a quest's state machine: in `state`, on `event`, go `to`. Optional `effect`
    (e.g. award_xp) and `on_enter` (a room label whose entry fires this step) bind it to a room."""

    state: str
    event: str
    to: str
    effect: str = ""
    on_enter: str = ""  # a room label; entering it fires this transition


@dataclass(frozen=True)
class QuestArc:
    """A region's optional story arc, as data: an `id`, a `start` state, ordered `steps`, the
    `terminal` states that end it, per-state `labels` (text), and a completion `reward_xp`."""

    id: str
    start: str
    steps: tuple[QuestStep, ...]
    terminal: tuple[str, ...] = ()
    labels: dict[str, str] = field(default_factory=dict)
    name: str = ""
    reward_xp: int = 50


@dataclass(frozen=True)
class GameSpec:
    """A region of the persistent world, stated as data: a `region` name, its `rooms`, the `start`
    room a player enters at, and an optional `quest` arc bound to those rooms."""

    region: str
    rooms: tuple[RoomSpec, ...]
    start: str
    quest: QuestArc | None = None


@dataclass(frozen=True)
class LinkedRegion:
    """The record of an emitted region: what was written, where, and its integrity (checksums), so a
    Seed can boot it and a later run can prove it is byte-identical."""

    region: str
    dest: str
    start: str
    files: list[str]  # emitted relpaths, sorted
    checksums: dict[str, str]  # relpath -> sha256
    rooms_linked: int
    has_quest: bool = False


@dataclass(frozen=True)
class RegionVerdict:
    """The Linker's honest verdict on an emitted region (and its quest, if any)."""

    verdict: str
    rooms: int = 0
    unreachable: tuple[str, ...] = ()  # orphan rooms, or unreachable quest states/terminals
    error: str = ""  # the loader's message, or the reason, when REFUSED
    quest: bool = False  # whether a quest arc was present and validated

    @property
    def ok(self) -> bool:
        return self.verdict == LINKED


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _dump(data: Any, *, sort_keys: bool = True) -> str:
    """Deterministic YAML block style -- same spec yields byte-identical output. `sort_keys` off
    preserves a caller's chosen order (rooms emit the start FIRST; the rest stay alphabetical)."""
    import yaml  # a real dep (the loaders use it); imported here to keep the module light

    return yaml.safe_dump(data, sort_keys=sort_keys, allow_unicode=True, default_flow_style=False)


def _rooms_yaml(spec: GameSpec) -> str:
    """Render the region as `rooms.yaml` the engine's loader accepts (only set fields emitted). The
    START room is emitted FIRST so the seed spawns there: the engine's spawn is the first room in
    rooms.yaml (world.START_ROOM = next(iter(WORLD))), so a bootable seed must list start first."""
    by_label = {room.label: room for room in spec.rooms}
    ordered = [spec.start, *sorted(label for label in by_label if label != spec.start)]
    body: dict[str, Any] = {}
    for label in ordered:
        room = by_label[label]
        fields: dict[str, Any] = {}
        if room.name:
            fields["name"] = room.name
        if room.desc:
            fields["desc"] = room.desc
        if room.exits:
            fields["exits"] = dict(room.exits)
        body[label] = fields or None  # a bare label is a valid room
    return _dump(body, sort_keys=False)  # preserve start-first ordering


def _quest_yaml(quest: QuestArc) -> str:
    """Render the quest as `quest.yaml` the engine's `load_quest` accepts (step order kept)."""
    steps: list[dict[str, Any]] = []
    for step in quest.steps:
        raw: dict[str, Any] = {"state": step.state, "event": step.event, "to": step.to}
        if step.effect:
            raw["effect"] = step.effect
        if step.on_enter:
            raw["on_enter"] = step.on_enter
        steps.append(raw)
    data: dict[str, Any] = {"id": quest.id, "start": quest.start, "steps": steps}
    if quest.name:
        data["name"] = quest.name
    data["reward_xp"] = quest.reward_xp
    if quest.terminal:
        data["terminal"] = list(quest.terminal)
    if quest.labels:
        data["labels"] = dict(quest.labels)
    return _dump(data)


def link_region(spec: GameSpec, dest: Path) -> LinkedRegion:
    """Emit a region as canonical seed content (`rooms.yaml`, plus `quest.yaml` for a quest)
    into `dest`. Reproducible + checksummed. Fails loud (GameLinkError) on an empty spec or a start
    naming no room. Content validity (exits, labels, reachability, quest integrity) is judged
    separately by `validate_region`, through the engine's own loaders."""
    if not spec.region or not spec.region.strip():
        raise GameLinkError("a game spec needs a non-empty region name to link")
    if not spec.rooms:
        raise GameLinkError("a game spec needs at least one room to link a region")
    labels = [r.label for r in spec.rooms]
    if spec.start not in labels:
        raise GameLinkError(f"start room {spec.start!r} is not one of the region's rooms")
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {"rooms.yaml": _rooms_yaml(spec)}
    if spec.quest is not None:
        files["quest.yaml"] = _quest_yaml(spec.quest)
    for rel, content in files.items():
        (dest / rel).write_text(content, encoding="utf-8")
    return LinkedRegion(
        region=spec.region,
        dest=str(dest),
        start=spec.start,
        files=sorted(files),
        checksums={rel: _sha256(content) for rel, content in files.items()},
        rooms_linked=len(spec.rooms),
        has_quest=spec.quest is not None,
    )


def _reachable(graph: dict[str, set[str]], start: str) -> set[str]:
    """Nodes reachable from `start` by walking directed edges (BFS)."""
    seen = {start}
    queue: deque[str] = deque([start])
    while queue:
        here = queue.popleft()
        for nxt in graph.get(here, ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def _judge_quest(quest: Any, room_labels: set[str], rooms: int) -> RegionVerdict:
    """Judge a loaded quest against the region: every `on_enter` names a real room (else REFUSED),
    and a terminal state must be reachable from the quest's start (else UNREACHABLE)."""
    dangling = sorted(
        {
            s["on_enter"]
            for s in quest["steps"]
            if s.get("on_enter") and s["on_enter"] not in room_labels
        }
    )
    if dangling:
        named = ", ".join(dangling)
        return RegionVerdict(
            REFUSED, rooms=rooms, error=f"quest on_enter names no room: {named}", quest=True
        )
    graph: dict[str, set[str]] = {}
    for step in quest["steps"]:
        graph.setdefault(step["state"], set()).add(step["to"])
    reached = _reachable(graph, quest["start"])
    terminals = set(quest["terminal"])
    if terminals and not (terminals & reached):
        return RegionVerdict(
            UNREACHABLE,
            rooms=rooms,
            unreachable=tuple(sorted(terminals)),
            error="no quest terminal is reachable from the start",
            quest=True,
        )
    return RegionVerdict(LINKED, rooms=rooms, quest=True)


def validate_region(linked: LinkedRegion) -> RegionVerdict:
    """Judge an emitted region by loading it through the REAL loaders. REFUSED if a loader rejects
    the content (dangling exit, bad label, malformed quest) or a quest `on_enter` names no room;
    UNREACHABLE if a room is orphaned or no quest terminal is reachable; else LINKED."""
    from kernel.world.seed import (
        BlueprintError,
        load_quest,
        load_rooms,
    )  # lazy: world out of import time

    dest = Path(linked.dest)
    try:
        rooms = load_rooms(dest / "rooms.yaml")
    except BlueprintError as exc:
        return RegionVerdict(REFUSED, error=str(exc))
    room_graph = {label: set(room["exits"].values()) for label, room in rooms.items()}
    orphans = tuple(sorted(set(rooms) - _reachable(room_graph, linked.start)))
    if orphans:
        return RegionVerdict(
            UNREACHABLE, rooms=len(rooms), unreachable=orphans, error="orphan rooms"
        )
    try:
        quest = load_quest(dest / "quest.yaml")
    except BlueprintError as exc:
        return RegionVerdict(REFUSED, rooms=len(rooms), error=f"quest: {exc}", quest=True)
    if quest is None:
        return RegionVerdict(LINKED, rooms=len(rooms))
    return _judge_quest(quest, set(rooms), len(rooms))


def link_and_validate(spec: GameSpec, dest: Path) -> tuple[LinkedRegion, RegionVerdict]:
    """Convenience: emit the region, then judge it. The two-step surface stays available so a caller
    can inspect the artifact before validating."""
    linked = link_region(spec, dest)
    return linked, validate_region(linked)
