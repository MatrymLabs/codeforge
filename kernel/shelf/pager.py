"""CARD: pager -- paginate long text into fixed-height pages, wrapping on demand.

Clean-room harvest of the pagination idea from Evennia's utils/evmore.py
(BSD-3-Clause, https://github.com/evennia/evennia). No Evennia code is copied:
this is a stdlib-only reimplementation of the concept (split display lines into
pages of at most `height` rows, optionally wrapping long lines to `width` first).
"""

from __future__ import annotations

import textwrap


class PagerError(ValueError):
    """Raised loud when paging bounds are nonsensical (height < 1 or width < 1)."""


def _display_lines(text: str, width: int | None) -> list[str]:
    """Expand `text` into the display rows a terminal would actually show.

    When `width` is set, each source line is wrapped to at most `width` columns
    (blank lines are preserved as a single empty row rather than swallowed).
    """
    source_lines = text.split("\n")
    if width is None:
        return source_lines

    rows: list[str] = []
    for line in source_lines:
        if line == "":
            rows.append("")
            continue
        rows.extend(textwrap.wrap(line, width=width))
    return rows


def paginate(text: str, height: int, *, width: int | None = None) -> list[str]:
    """Split `text` into pages of at most `height` display lines.

    Inputs:
        text: the full body to paginate.
        height: max display rows per page (must be >= 1).
        width: optional column limit; long lines are wrapped before paging.

    Output:
        A list of page strings. Empty text yields exactly one empty page ([""]).

    Fails loud with PagerError when height < 1 or width < 1.
    """
    if height < 1:
        raise PagerError(f"height must be >= 1, got {height}")
    if width is not None and width < 1:
        raise PagerError(f"width must be >= 1, got {width}")

    if text == "":
        return [""]

    rows = _display_lines(text, width)
    pages: list[str] = []
    for start in range(0, len(rows), height):
        pages.append("\n".join(rows[start : start + height]))
    return pages or [""]


def page_count(text: str, height: int, *, width: int | None = None) -> int:
    """Return how many pages `paginate` would produce for the same inputs."""
    return len(paginate(text, height, width=width))
