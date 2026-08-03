"""CARD: game_linker -- the game domain's Linker: a validated GameSpec becomes REAL, persistent seed
content (a region of rooms), validated by loading it through the engine's own world loader.

The missing bridge. The seedlab pipeline stops at a lifecycle record (a Seed that SELECTED the game
module); nothing turned a spec into a runnable world. This is that step for the integrated,
persistent MMORPG (no instancing): a GameSpec describing a region emits `rooms.yaml` -- canonical
seed content a Seed boots and that survives restart by construction -- and the Linker VALIDATES it
loading through the real `kernel.world.seed.load_rooms` (inheriting the engine's own gates: label
format, duplicate labels, dangling exits) plus a reachability walk from the start room.

Same emit-then-validate-by-running discipline as the CLI generator (cli_generator.py in seedlab),
but the target is a game world, and validation is the live world loader rather than a subprocess.

Grammar before worlds, from the game side: this lives in kernel/domains/ (world-aware) and imports
kernel/world/ -- which the neutral platform (kernel/seedlab) is forbidden to do (import-linter
contract `grammar-before-worlds`). A classroom Seed never loads this. The world loader is imported
lazily so merely importing this module stays light. Verdicts, not booleans: LINKED (loads AND every
room reachable) / UNREACHABLE (loads but orphan rooms) / REFUSED (the loader rejected the content).
Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --- verdict words (a distinct vocabulary: "can this region become a live world?") -------------
LINKED = "linked"  # the emitted content loads AND every room is reachable from the start
UNREACHABLE = "unreachable"  # loads, but one or more rooms cannot be reached from the start
REFUSED = "refused"  # the engine's own world loader rejected the content (dangling exit, bad label)


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
class GameSpec:
    """A region of the persistent world, stated as data: a `region` name, its `rooms`, and the
    `start` room a player enters at (the anchor reachability is measured from)."""

    region: str
    rooms: tuple[RoomSpec, ...]
    start: str


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


@dataclass(frozen=True)
class RegionVerdict:
    """The Linker's honest verdict on an emitted region."""

    verdict: str
    rooms: int = 0
    unreachable: tuple[str, ...] = ()  # rooms with no path from the start (verdict UNREACHABLE)
    error: str = ""  # the loader's message when the content was REFUSED

    @property
    def ok(self) -> bool:
        return self.verdict == LINKED


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rooms_yaml(spec: GameSpec) -> str:
    """Render the region as `rooms.yaml` the engine's loader accepts. Deterministic: the same
    spec yields byte-identical output (labels sorted; only set fields emitted)."""
    import yaml  # a real dep (the world loader uses it); imported here to keep the module light

    body: dict[str, Any] = {}
    for room in spec.rooms:
        fields: dict[str, Any] = {}
        if room.name:
            fields["name"] = room.name
        if room.desc:
            fields["desc"] = room.desc
        if room.exits:
            fields["exits"] = dict(room.exits)
        body[room.label] = fields or None  # a bare label is a valid room
    return yaml.safe_dump(body, sort_keys=True, allow_unicode=True, default_flow_style=False)


def link_region(spec: GameSpec, dest: Path) -> LinkedRegion:
    """Emit a region as canonical seed content (`rooms.yaml`) into an empty `dest`. Reproducible +
    checksummed. Fails loud (GameLinkError) on an empty spec or a start naming no room --
    there is nothing to link. Content validity (exits, labels, reachability) is judged separately by
    `validate_region`, through the engine's own loader."""
    if not spec.region or not spec.region.strip():
        raise GameLinkError("a game spec needs a non-empty region name to link")
    if not spec.rooms:
        raise GameLinkError("a game spec needs at least one room to link a region")
    labels = [r.label for r in spec.rooms]
    if spec.start not in labels:
        raise GameLinkError(f"start room {spec.start!r} is not one of the region's rooms")
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    content = _rooms_yaml(spec)
    (dest / "rooms.yaml").write_text(content, encoding="utf-8")
    checksums = {"rooms.yaml": _sha256(content)}
    return LinkedRegion(
        region=spec.region,
        dest=str(dest),
        start=spec.start,
        files=["rooms.yaml"],
        checksums=checksums,
        rooms_linked=len(spec.rooms),
    )


def _reachable(rooms: dict[str, Any], start: str) -> set[str]:
    """Rooms reachable from `start` by walking exits (BFS over the loaded room graph)."""
    seen = {start}
    queue: deque[str] = deque([start])
    while queue:
        here = queue.popleft()
        for dest in rooms[here]["exits"].values():
            if dest not in seen:
                seen.add(dest)
                queue.append(dest)
    return seen


def validate_region(linked: LinkedRegion) -> RegionVerdict:
    """Judge an emitted region by loading it through the REAL world loader and walking reachability.
    REFUSED if the loader rejects the content (dangling exit, bad/duplicate label); UNREACHABLE if
    some room has no path from the start; LINKED when it loads and the whole region is reachable."""
    from kernel.world.seed import SeedError, load_rooms  # lazy: world code stays out of import time

    try:
        rooms = load_rooms(Path(linked.dest) / "rooms.yaml")
    except SeedError as exc:
        return RegionVerdict(REFUSED, error=str(exc))
    reached = _reachable(rooms, linked.start)
    orphans = tuple(sorted(set(rooms) - reached))
    if orphans:
        return RegionVerdict(UNREACHABLE, rooms=len(rooms), unreachable=orphans)
    return RegionVerdict(LINKED, rooms=len(rooms))


def link_and_validate(spec: GameSpec, dest: Path) -> tuple[LinkedRegion, RegionVerdict]:
    """Convenience: emit the region, then judge it. The two-step surface stays available so a caller
    can inspect the artifact before validating."""
    linked = link_region(spec, dest)
    return linked, validate_region(linked)
