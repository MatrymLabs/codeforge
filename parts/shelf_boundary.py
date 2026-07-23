"""CARD: shelf_boundary -- prove the Hardware Store shelf imports no engine part.

The shelf (`parts/shelf/`) is Layer 3: reusable, engine-agnostic cores. Their whole value is that
the dependency arrow points ONE way -- the engine (`parts/`) may import the shelf, but a shelf core
must never reach back into the engine (only stdlib + other shelf cores). That invariant was true the
day the cores were extracted; this Lens keeps it true, by reading every shelf module's AST and
reporting any import of a non-shelf `parts.*` module. A violation is a real regression: it
re-couples a "reusable" core to CodeForge and quietly breaks the reuse claim.

Reads and reports; it mutates nothing. Empty list == the shelf is clean.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


class ShelfBoundaryError(ValueError):
    """A shelf module could not be parsed. Fail loud: an unreadable core cannot be cleared."""


def _parts_imports(source: str, where: str) -> set[str]:
    """Every `parts.*` module a source file imports (both `import parts.x` and `from parts.x`)."""
    try:
        tree = ast.parse(source, filename=where)
    except SyntaxError as exc:
        raise ShelfBoundaryError(f"cannot parse {where}: {exc}") from exc
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "parts" or node.module.startswith("parts.")):
                found.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "parts" or alias.name.startswith("parts."):
                    found.add(alias.name)
    return found


def _is_engine(module: str) -> bool:
    """True if a `parts.*` module is an ENGINE module, i.e. not the shelf itself or a shelf core."""
    return module != "parts.shelf" and not module.startswith("parts.shelf.")


def shelf_import_violations(shelf_dir: Path | None = None) -> dict[str, list[str]]:
    """Map each shelf module to the engine `parts.*` modules it wrongly imports (empty == clean).

    A shelf core may import stdlib and other shelf cores (`parts.shelf.*`); importing any other
    `parts.*` module is a boundary violation, because it re-couples the core to the engine."""
    base = shelf_dir if shelf_dir is not None else _ROOT / "parts" / "shelf"
    violations: dict[str, list[str]] = {}
    for module in sorted(base.glob("*.py")):
        if module.name == "__init__.py":
            continue
        engine = sorted(
            m
            for m in _parts_imports(module.read_text(encoding="utf-8"), str(module))
            if _is_engine(m)
        )
        if engine:
            violations[module.name] = engine
    return violations


def shelf_boundary_gaps(root: Path | None = None) -> list[str]:
    """The boundary violations as `module: imports engine part(s) x, y` lines (empty == clean).

    The ritual-facing shape: one line per offending shelf core, so a regression that re-couples the
    shelf to the engine is surfaced in `make repo-integrity`, not discovered later."""
    base = root if root is not None else _ROOT
    violations = shelf_import_violations(base / "parts" / "shelf")
    return [
        f"{name}: imports engine part(s) {', '.join(mods)}" for name, mods in violations.items()
    ]
