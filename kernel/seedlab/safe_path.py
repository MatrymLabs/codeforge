"""CARD: safe_path -- refuse a caller-supplied name that would leave the root it was promised to.

The Seed stores address records by id: a Seed id, a model id, an artifact id. Every one of those
ids reaches the filesystem, and several of them arrive from a client frame. A store that builds
`root / seed_id` trusts the caller with the shape of a path, which is how `..` becomes a file
outside the store.

This module is the one place that judgement is made, so the four Seed stores stop each inventing
their own answer. It is a GATE: it does not sanitise and continue, it refuses.

Why refusal rather than sanitising. Rewriting `..` into `_` silently changes where a record lives,
so a caller asking for the wrong thing quietly gets the wrong file instead of an error. A store id
that is not a plain segment is a bug or an attack, and both deserve to fail loud and early.

Inputs:  a root directory, and one or more caller-supplied segments.
Outputs: a Path guaranteed to sit inside the resolved root, or PathEscape.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["PathEscape", "contained_path", "safe_segment"]


class PathEscape(ValueError):
    """A caller-supplied segment is not a plain name, or would leave its root."""


def safe_segment(value: str, *, what: str = "segment") -> str:
    """Return `value` when it is a plain filename component, else refuse.

    Refuses, in this order: an empty or whitespace-only name; `.` and `..`, which are traversal
    even though every character in them is otherwise legal; anything carrying a path separator
    (either platform's); an absolute path; and a NUL byte, which truncates a path inside libc.
    """
    if not value or not value.strip():
        raise PathEscape(f"{what} must not be empty")
    if value in (os.curdir, os.pardir):
        raise PathEscape(f"{what} must be a name, not a traversal: {value!r}")
    if "\x00" in value:
        raise PathEscape(f"{what} must not contain a NUL byte: {value!r}")
    if "/" in value or "\\" in value:
        raise PathEscape(f"{what} must not contain a path separator: {value!r}")
    if Path(value).is_absolute() or os.path.splitdrive(value)[0]:
        raise PathEscape(f"{what} must be relative: {value!r}")
    return value


def contained_path(root: Path | str, *segments: str, what: str = "segment") -> Path:
    """Join `segments` under `root` and prove the result stayed inside it.

    Two independent checks, deliberately. `safe_segment` rejects the shape of each segment before
    it touches the filesystem, and the resolved bounds check below catches whatever a future
    caller, a symlink, or a platform quirk slips past the first. Either one alone has been enough
    to miss a traversal somewhere in this codebase's history.
    """
    if not segments:
        raise PathEscape("at least one segment is required")
    base = Path(root).resolve()
    candidate = base
    for segment in segments:
        candidate = candidate / safe_segment(segment, what=what)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise PathEscape(f"path escapes its root: {resolved} is not under {base}") from exc
    return resolved
