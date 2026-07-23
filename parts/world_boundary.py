"""CARD: world_boundary -- prove the World Package (Layer 2) imports no platform (Layer 1) module.

The game world -- rooms, combat, jobs, progression, accounts -- is Layer 2: the runtime a shipped
game actually needs. The manufacturing platform (Layer 1: blueprint, cast, veritas, pm, career, the
assurance stack) is built ON the world (it imports the world to catalog, serve, and audit it), but
the world must NOT depend on the platform -- so a game can ship without the dev-tools workshop.
`cast` already pours a world standalone; this Lens keeps the World Package's import graph free of
the platform, so that independence is enforced, not merely current. A violation re-couples the game
to the workshop and quietly breaks the "two outputs" separation.

The World Package is a DECLARED set (WORLD_MODULES) -- the transitive import closure of the game
runtime, the way the Hardware Store shelf is a directory. A game module may import other world
modules and the shelf (Layer 3, the shared reusable cores); importing anything else in `parts/` is a
platform reach. Reads and reports; it mutates nothing. Empty list == the boundary holds.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# The World Package: the game runtime's transitive import closure. Declared, like the shelf is a
# dir. A new game module belongs here; the completeness check (test twin) pins that this set is the
# real closure of the game seed, so it cannot silently drift.
WORLD_MODULES = frozenset(
    {
        "accounts",
        "aggression",
        "character_view",
        "characters",
        "chime",
        "combat",
        "combat_clock",
        "db",
        "derived",
        "doors",
        "encounter_log",
        "engineer",
        "equipment",
        "events",
        "frames",
        "items",
        "job_progress",
        "jobs",
        "npcs",
        "paths",
        "progression",
        "progression_awards",
        "quest",
        "ranks",
        "resources",
        "score_sheet",
        "score_sheet_model",
        "seed",
        "session",
        "stat_rules",
        "world",
        "world_manifest",
        "zones",
    }
)


class WorldBoundaryError(ValueError):
    """A world module could not be parsed. Fail loud: an unreadable module cannot be cleared."""


def _parts_imports(source: str, where: str) -> set[str]:
    """The leaf name of every `parts.*` module a source imports; `parts.shelf.*` -> 'shelf'."""
    try:
        tree = ast.parse(source, filename=where)
    except SyntaxError as exc:
        raise WorldBoundaryError(f"cannot parse {where}: {exc}") from exc
    found: set[str] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("parts"):
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [a.name for a in node.names if a.name.startswith("parts")]
        for name in names:
            parts = name.split(".")
            if len(parts) >= 2:
                found.add("shelf" if parts[1] == "shelf" else parts[1])
    return found


def _is_platform(module: str) -> bool:
    """A parts import that is neither the shelf (Layer 3) nor a World Package module is platform."""
    return module != "shelf" and module not in WORLD_MODULES


def world_import_violations(root: Path | None = None) -> dict[str, list[str]]:
    """Map each World Package module to the platform modules it wrongly imports (empty == clean).

    A world module may import other world modules and the shelf; importing any other `parts.*`
    module re-couples the game to the manufacturing platform, which this reports."""
    base = (root if root is not None else _ROOT) / "parts"
    violations: dict[str, list[str]] = {}
    for module in sorted(WORLD_MODULES):
        path = base / f"{module}.py"
        if not path.is_file():
            continue
        platform = sorted(
            m
            for m in _parts_imports(path.read_text(encoding="utf-8"), str(path))
            if _is_platform(m)
        )
        if platform:
            violations[module] = platform
    return violations


def world_boundary_gaps(root: Path | None = None) -> list[str]:
    """The violations as `module: imports platform part(s) x, y` lines (empty == clean).

    The ritual-facing shape: one line per offending world module, so a regression that re-couples
    the game to the workshop surfaces in `make repo-integrity`, not later."""
    violations = world_import_violations(root)
    return [
        f"{name}: imports platform part(s) {', '.join(mods)}" for name, mods in violations.items()
    ]
