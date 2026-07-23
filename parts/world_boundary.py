"""CARD: world_boundary -- prove the World Package (Layer 2) imports no platform (Layer 1) module.

The game world -- rooms, combat, jobs, progression, accounts -- is Layer 2: the runtime a shipped
game actually needs. The manufacturing platform (Layer 1: blueprint, cast, veritas, pm, career, the
assurance stack) is built ON the world (it imports the world to catalog, serve, and audit it), but
the world must NOT depend on the platform -- so a game can ship without the dev-tools workshop.
`cast` already pours a world standalone; this Lens keeps the World Package's import graph free of
the platform, so that independence is enforced, not merely current. A violation re-couples the game
to the workshop and quietly breaks the "two outputs" separation.

The World Package is a physical directory (`parts/world/`), the way the Hardware Store shelf is a
directory. WORLD_MODULES is discovered from that directory -- the world IS its folder, so the set
cannot drift from a hand-maintained list. A game module may import other world modules
(`parts.world.*`) and the shelf (Layer 3, `parts.shelf.*`); importing anything else in `parts/` is a
platform reach. Reads and reports; it mutates nothing. Empty list == the boundary holds.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _world_dir(root: Path | None = None) -> Path:
    return (root if root is not None else _ROOT) / "parts" / "world"


def _discover_world(root: Path | None = None) -> frozenset[str]:
    """The World Package's modules, read straight from `parts/world/` (the world is its dir)."""
    d = _world_dir(root)
    if not d.is_dir():
        return frozenset()
    return frozenset(p.stem for p in d.glob("*.py") if p.stem != "__init__")


# The World Package: every module physically filed under parts/world/. Discovered, not declared, so
# a new game module is a member the moment it lands in the directory -- no list to keep in sync.
WORLD_MODULES = _discover_world()


class WorldBoundaryError(ValueError):
    """A world module could not be parsed. Fail loud: an unreadable module cannot be cleared."""


def _parts_imports(source: str, where: str) -> set[str]:
    """The world-relative name of every `parts.*` import: `parts.world.X` -> 'X' (the intra-world
    module), `parts.shelf.*` -> 'shelf', any other `parts.Y` -> 'Y' (a platform reach)."""
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
            if len(parts) < 2:
                continue
            if parts[1] == "shelf":
                found.add("shelf")
            elif parts[1] == "world":
                found.add(
                    parts[2] if len(parts) >= 3 else "world"
                )  # unwrap to the intra-world module
            else:
                found.add(parts[1])
    return found


def _is_platform(module: str) -> bool:
    """A parts import that is neither the shelf (Layer 3) nor a World Package module is platform."""
    return module != "shelf" and module not in WORLD_MODULES


def world_import_violations(root: Path | None = None) -> dict[str, list[str]]:
    """Map each World Package module to the platform modules it wrongly imports (empty == clean).

    A world module may import other world modules and the shelf; importing any other `parts.*`
    module re-couples the game to the manufacturing platform, which this reports."""
    base = _world_dir(root)
    if not base.is_dir():
        return {}
    violations: dict[str, list[str]] = {}
    for path in sorted(base.glob("*.py")):
        if path.stem == "__init__":
            continue
        platform = sorted(
            m
            for m in _parts_imports(path.read_text(encoding="utf-8"), str(path))
            if _is_platform(m)
        )
        if platform:
            violations[path.stem] = platform
    return violations


def world_boundary_gaps(root: Path | None = None) -> list[str]:
    """The violations as `module: imports platform part(s) x, y` lines (empty == clean).

    The ritual-facing shape: one line per offending world module, so a regression that re-couples
    the game to the workshop surfaces in `make repo-integrity`, not later."""
    violations = world_import_violations(root)
    return [
        f"{name}: imports platform part(s) {', '.join(mods)}" for name, mods in violations.items()
    ]
