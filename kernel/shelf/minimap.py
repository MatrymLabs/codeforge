"""CARD: minimap -- render a small ASCII minimap of nearby rooms from a room graph.

Clean-room, pattern-not-code harvest from Evennia contrib grid/ingame_map_display
(BSD-3-Clause). We reuse the *idea* (walk exits, place neighbours on a 2D grid,
draw bracketed cells with dash/pipe connectors), not any Evennia source. No
Evennia code, names, or data structures were copied.

Model: a room graph maps each room id to its exits, an exit being a compass
direction pointing at a neighbour room id. We BFS out from a center room via the
four cardinals (n, s, e, w), place each reached room on an integer (x, y) grid,
then paint a character canvas: center is `[@]`, other rooms `[ ]`, horizontal
exits become `-`, vertical exits become `|`. Optional up/down (u, d) exits are
not placed on the 2D plane; their presence is noted in a footer line.

Convention: n = up = row - 1, s = down = row + 1, e = col + 1, w = col - 1.
"""

from __future__ import annotations

from collections import deque

Graph = dict[str, dict[str, str]]

# Cardinal directions we place on the 2D grid, and their (dx, dy) steps.
# y grows downward (screen rows), so north is -y.
_DELTA: dict[str, tuple[int, int]] = {
    "n": (0, -1),
    "s": (0, 1),
    "e": (1, 0),
    "w": (-1, 0),
}

# Grid geometry: each room cell is 3 chars wide (`[x]`); one connector column
# sits between horizontally adjacent cells, one connector line between rows.
_CELL_W = 4  # 3 for the bracketed cell + 1 for the horizontal connector slot
_ROW_H = 2  # 1 for the room line + 1 for the vertical connector line


class MinimapError(ValueError):
    """Raised loud and early when a graph or request is malformed."""


def render(graph: Graph, center: str, *, radius: int = 2) -> str:
    """Draw an ASCII minimap of rooms within `radius` cardinal steps of `center`.

    Inputs:
      graph  -- room_id -> {direction: neighbour_room_id}; directions in
                {"n", "s", "e", "w"} (plus optional "u", "d").
      center -- the room id drawn as `[@]` at the middle of the map.
      radius -- how many cardinal steps out to draw (>= 0; 0 draws only center).

    Returns a deterministic multi-line string.

    Fails loud (MinimapError) when: radius < 0, center is absent from the graph,
    or any exit points at a room id not present in the graph (a dangling exit).
    """
    if radius < 0:
        raise MinimapError(f"radius must be >= 0, got {radius}")  # noqa: TRY003
    if center not in graph:
        raise MinimapError(f"center room {center!r} is not in the graph")  # noqa: TRY003

    # Fail loud on any dangling exit anywhere in the graph: an internally
    # inconsistent map is a defect, not something to paper over silently.
    for room_id, exits in graph.items():
        for direction, target in exits.items():
            if target not in graph:
                raise MinimapError(  # noqa: TRY003
                    f"dangling exit: room {room_id!r} exit {direction!r} "
                    f"points at unknown room {target!r}"
                )

    coords = _walk(graph, center, radius)
    canvas = _paint(graph, center, coords)

    lines = ["".join(row).rstrip() for row in canvas]
    rendered = "\n".join(lines)

    if any("u" in graph[rid] or "d" in graph[rid] for rid in coords):
        rendered += "\n(u/d exits present, not shown on 2D map)"
    return rendered


def _walk(graph: Graph, center: str, radius: int) -> dict[str, tuple[int, int]]:
    """BFS from center via cardinals; first (shortest) path fixes each coord."""
    coords: dict[str, tuple[int, int]] = {center: (0, 0)}
    depth: dict[str, int] = {center: 0}
    queue: deque[str] = deque([center])

    while queue:
        current = queue.popleft()
        if depth[current] >= radius:
            continue
        cx, cy = coords[current]
        for direction in ("n", "s", "e", "w"):  # fixed order -> deterministic
            neighbour = graph[current].get(direction)
            if neighbour is None or neighbour in coords:
                continue
            dx, dy = _DELTA[direction]
            coords[neighbour] = (cx + dx, cy + dy)
            depth[neighbour] = depth[current] + 1
            queue.append(neighbour)

    return coords


def _paint(graph: Graph, center: str, coords: dict[str, tuple[int, int]]) -> list[list[str]]:
    """Place bracketed cells and their connectors on a blank character canvas."""
    xs = [x for x, _ in coords.values()]
    ys = [y for _, y in coords.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    cols = max_x - min_x + 1
    rows = max_y - min_y + 1
    width = cols * _CELL_W - 1
    height = rows * _ROW_H - 1
    canvas: list[list[str]] = [[" "] * width for _ in range(height)]

    def anchor(x: int, y: int) -> tuple[int, int]:
        """Return (line, col) of the `[` that opens the cell at grid (x, y)."""
        return (y - min_y) * _ROW_H, (x - min_x) * _CELL_W

    for room_id, (x, y) in coords.items():
        line, col = anchor(x, y)
        canvas[line][col] = "["
        canvas[line][col + 1] = "@" if room_id == center else " "
        canvas[line][col + 2] = "]"

    # sorted() keeps connector painting order stable and reproducible.
    for room_id in sorted(coords):
        x, y = coords[room_id]
        line, col = anchor(x, y)
        for direction in ("n", "s", "e", "w"):
            neighbour = graph[room_id].get(direction)
            if neighbour is None or neighbour not in coords:
                continue
            if direction == "e":
                canvas[line][col + 3] = "-"
            elif direction == "w":
                canvas[line][col - 1] = "-"
            elif direction == "n":
                canvas[line - 1][col + 1] = "|"
            elif direction == "s":
                canvas[line + 1][col + 1] = "|"

    return canvas
