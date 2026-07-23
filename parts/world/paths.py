"""CARD: paths -- resolve a path from an environment override or a default, in one place.

The env-override path pattern (read `$VAR`; if set, use it expanded; else a default) was copied
into several parts (db, hardware, store_index, assessment) - a duplication the clone scan flagged.
This is
that pattern once: the default is resolved at the call site (so `Path(__file__)` anchors correctly),
and only the override-vs-default choice lives here.
"""

from __future__ import annotations

import os
from pathlib import Path


def resolved_path(env_var: str, default: Path) -> Path:
    """The path from `$env_var` (expanded) if set and non-empty, otherwise `default`."""
    override = os.environ.get(env_var)
    return Path(override).expanduser() if override else default
