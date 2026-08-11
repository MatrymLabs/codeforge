"""CARD: exit_integrity -- find canonical exits without a usable reverse path.

Rooms form a directed graph, but a player must not be stranded by an accidental
one-way canonical exit. A seed can declare a deliberate one-way exit in its data;
this checker reports that decision separately from an accidental missing reverse.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CANONICAL_REVERSES = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "northeast": "southwest",
    "southwest": "northeast",
    "northwest": "southeast",
    "southeast": "northwest",
    "up": "down",
    "down": "up",
    "in": "out",
    "out": "in",
}
CANONICAL_DIRECTIONS = frozenset(CANONICAL_REVERSES)


@dataclass(frozen=True)
class Exit:
    """One canonical departure, named so a content author can repair it."""

    room: str
    direction: str
    to: str


@dataclass(frozen=True)
class ExitVerdict:
    """The visible distinction between a deliberate drop and a topology defect."""

    accidental: tuple[Exit, ...]
    declared: tuple[Exit, ...]

    @property
    def clean(self) -> bool:
        return not self.accidental

    def render(self) -> str:
        """Render every actionable edge, never hiding declared one-way passages."""
        lines: list[str] = []
        if self.accidental:
            lines.append("ACCIDENTAL one-way exits:")
            lines.extend(
                f"- {edge.room} --{edge.direction}--> {edge.to}" for edge in self.accidental
            )
        if self.declared:
            lines.append("Declared one-way exits:")
            lines.extend(f"- {edge.room} --{edge.direction}--> {edge.to}" for edge in self.declared)
        return "\n".join(lines) if lines else "Exit integrity: CLEAN"


def _has_reverse(
    rooms: Mapping[str, Mapping[str, Any]], room: str, direction: str, destination: str
) -> bool:
    destination_exits = rooms[destination].get("exits", {})
    if destination_exits.get(CANONICAL_REVERSES[direction]) == room:
        return True
    return direction == "out" and any(
        exit_direction not in CANONICAL_DIRECTIONS and exit_to == room
        for exit_direction, exit_to in destination_exits.items()
    )


def inspect_exits(rooms: Mapping[str, Mapping[str, Any]]) -> ExitVerdict:
    """Inspect a loaded room graph without duplicating the dangling-exit gate."""
    accidental: list[Exit] = []
    declared: list[Exit] = []
    for room, spec in rooms.items():
        exits = spec.get("exits", {})
        one_way = set(spec.get("one_way", ()))
        for direction, destination in exits.items():
            if direction not in CANONICAL_DIRECTIONS or destination not in rooms:
                continue
            edge = Exit(room, direction, destination)
            if direction in one_way:
                declared.append(edge)
            elif not _has_reverse(rooms, room, direction, destination):
                accidental.append(edge)
    return ExitVerdict(tuple(accidental), tuple(declared))


def check_paths(paths: Sequence[Path]) -> ExitVerdict:
    """Load each requested seed and combine its exit-integrity findings."""
    from kernel.world.seed import load_rooms

    accidental: list[Exit] = []
    declared: list[Exit] = []
    for path in paths:
        verdict = inspect_exits(load_rooms(path))
        accidental.extend(verdict.accidental)
        declared.extend(verdict.declared)
    return ExitVerdict(tuple(accidental), tuple(declared))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the real-seed gate, exiting nonzero only for accidental one-way exits."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[
            Path("content/seeds/first-forge/rooms.yaml"),
            Path("content/seeds/aethryn/rooms.yaml"),
        ],
    )
    args = parser.parse_args(argv)
    verdict = check_paths(args.paths)
    print(verdict.render())
    return 0 if verdict.clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
