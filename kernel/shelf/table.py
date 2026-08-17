"""CARD: table -- render rows of cells as an aligned ASCII table (auto width, wrap, alignment).

Harvested (clean-room, pattern-not-code) from Evennia's utils/evtable.py (BSD-3-Clause): the
reusable column-table renderer codeforge lacks. Today codeforge hand-aligns columns in every verb
(who-lists, inventory, shop/auction/bank listings, `pm status`) and the only table-like code is the
bespoke fixed-width score_sheet. This is the smallest useful core: headers + rows -> a bordered,
auto-width, per-column-aligned monospace table, with optional per-column max width + word wrap.

Pure projection (state canonical, text a projection): `render` takes data and returns a string,
never
touches world state. Stdlib only (no unicode-width lib: ASCII/BMP monospace assumed, documented).

  render(rows, *, headers=None, align=..., max_widths=..., border=True) -> str
"""

from __future__ import annotations

from dataclasses import dataclass
from textwrap import wrap

LEFT, RIGHT, CENTER = "left", "right", "center"
_ALIGNS = frozenset({LEFT, RIGHT, CENTER})


class TableError(ValueError):
    """Raised loud and early on ragged rows, a bad alignment token, or a non-positive max width."""


def _pad(cell: str, width: int, align: str) -> str:
    if align == RIGHT:
        return cell.rjust(width)
    if align == CENTER:
        return cell.center(width)
    return cell.ljust(width)


def _wrap_cell(cell: str, width: int | None) -> list[str]:
    """Split a cell into display lines, wrapping at `width` if set. Blank cell -> one empty line."""
    if width is None:
        return cell.split("\n") if "\n" in cell else [cell]
    lines: list[str] = []
    for para in cell.split("\n"):
        lines.extend(wrap(para, width) or [""])
    return lines or [""]


@dataclass(frozen=True)
class _Col:
    align: str
    max_width: int | None


def _columns(
    ncols: int,
    align: str | list[str],
    max_widths: int | list[int | None] | None,
) -> list[_Col]:
    """Normalize per-column align + max_width into one spec per column. Fails loud on bad input."""
    aligns = [align] * ncols if isinstance(align, str) else list(align)
    if len(aligns) != ncols:
        raise TableError(f"align has {len(aligns)} entries but there are {ncols} columns")  # noqa: TRY003
    for a in aligns:
        if a not in _ALIGNS:
            raise TableError(f"align must be one of {sorted(_ALIGNS)} (got {a!r})")  # noqa: TRY003

    if max_widths is None or isinstance(max_widths, int):
        widths: list[int | None] = [max_widths] * ncols
    else:
        widths = list(max_widths)
        if len(widths) != ncols:
            raise TableError(f"max_widths has {len(widths)} entries but there are {ncols} columns")  # noqa: TRY003
    for w in widths:
        if w is not None and w < 1:
            raise TableError(f"max_width must be >= 1 or None (got {w})")  # noqa: TRY003
    return [_Col(a, w) for a, w in zip(aligns, widths, strict=True)]


def render(
    rows: list[list[str]],
    *,
    headers: list[str] | None = None,
    align: str | list[str] = LEFT,
    max_widths: int | list[int | None] | None = None,
    border: bool = True,
) -> str:
    """Render `rows` (each a list of cell strings) as an aligned monospace table.

    headers: an optional header row (underlined by a separator). align: one token for all columns or
    one per column (left|right|center). max_widths: cap a column's width and word-wrap over-long
    cells (one value for all, or one per column, or None for no cap). border: draw the outer box +
    column separators. Raises TableError on ragged rows or bad spec (never renders a lie)."""
    all_rows = ([headers] if headers is not None else []) + rows
    if not all_rows:
        return ""
    ncols = len(all_rows[0])
    for i, row in enumerate(all_rows):
        if len(row) != ncols:
            raise TableError(f"row {i} has {len(row)} cells but the table has {ncols} columns")  # noqa: TRY003

    cols = _columns(ncols, align, max_widths)

    # wrap every cell into physical lines, then size each column to its widest line (<= max_width)
    wrapped_headers = (
        [[_wrap_cell(c, cols[j].max_width) for j, c in enumerate(headers)]]
        if headers is not None
        else []
    )
    wrapped_rows = [[_wrap_cell(c, cols[j].max_width) for j, c in enumerate(row)] for row in rows]
    widths = [0] * ncols
    for block in wrapped_headers + wrapped_rows:
        for j, cell_lines in enumerate(block):
            widths[j] = max(widths[j], *(len(line) for line in cell_lines))

    def render_block(block: list[list[str]]) -> list[str]:
        height = max(len(cell) for cell in block)
        out = []
        for r in range(height):
            cells = [
                _pad(block[j][r] if r < len(block[j]) else "", widths[j], cols[j].align)
                for j in range(ncols)
            ]
            out.append(("| " + " | ".join(cells) + " |") if border else "  ".join(cells))
        return out

    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+" if border else None
    lines: list[str] = []
    if border and sep is not None:
        lines.append(sep)
    if wrapped_headers:
        lines.extend(render_block(wrapped_headers[0]))
        lines.append(sep if border and sep is not None else "  ".join("-" * w for w in widths))
    for block in wrapped_rows:
        lines.extend(render_block(block))
    if border and sep is not None:
        lines.append(sep)
    return "\n".join(lines)
