"""CARD: line_editor -- immutable copy-on-write multi-line text buffer for in-game composition.

Clean-room harvest of the in-game editor idea from Evennia's utils/eveditor.py
(BSD-3-Clause, https://github.com/evennia/evennia). No Evennia code is copied:
this is a stdlib-only reimplementation of the buffer concept (mail bodies, room
descriptions, boards) as a frozen dataclass where every edit returns a NEW Buffer.
The stored state is canonical; renderers never mutate it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


class EditorError(ValueError):
    """Raised loud when a 1-based line index falls outside the buffer."""


@dataclass(frozen=True)
class Buffer:
    """An immutable stack of text lines. Every edit yields a fresh Buffer.

    Line indices in the public API are 1-based, matching how a player counts
    lines shown by `render()`.
    """

    lines: tuple[str, ...] = ()

    def __len__(self) -> int:
        return len(self.lines)

    def _check_index(self, index: int) -> None:
        """Fail loud unless `index` is a valid 1-based position on an existing line."""
        if index < 1 or index > len(self.lines):
            raise EditorError(f"line {index} out of range for buffer of {len(self.lines)} line(s)")

    def append(self, line: str) -> Buffer:
        """Return a new Buffer with `line` added to the end."""
        return replace(self, lines=(*self.lines, line))

    def insert(self, index: int, line: str) -> Buffer:
        """Return a new Buffer with `line` inserted BEFORE 1-based `index`.

        Inserting at len+1 is allowed and appends (matches editor intuition).
        """
        if index < 1 or index > len(self.lines) + 1:
            raise EditorError(
                f"insert index {index} out of range for buffer of {len(self.lines)} line(s)"
            )
        pos = index - 1
        return replace(self, lines=(*self.lines[:pos], line, *self.lines[pos:]))

    def delete(self, index: int) -> Buffer:
        """Return a new Buffer with the 1-based `index` line removed."""
        self._check_index(index)
        pos = index - 1
        return replace(self, lines=(*self.lines[:pos], *self.lines[pos + 1 :]))

    def replace(self, old: str, new: str) -> Buffer:
        """Return a new Buffer with `old` substring swapped for `new` on every line."""
        return replace(self, lines=tuple(line.replace(old, new) for line in self.lines))

    def clear(self) -> Buffer:
        """Return a new empty Buffer."""
        return replace(self, lines=())

    def text(self) -> str:
        """Render the buffer body as a newline-joined string (what gets saved)."""
        return "\n".join(self.lines)

    def render(self) -> str:
        """Render numbered lines ('1: ...') for the editing view."""
        return "\n".join(f"{n}: {line}" for n, line in enumerate(self.lines, start=1))
