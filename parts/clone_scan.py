"""CARD: clone_scan -- find structurally duplicated logic across the codebase (AST shape hashing).

Upgrades pattern detection from name/docstring signals (the Harvest Lens) to real duplicate LOGIC:
it fingerprints each function by its AST SHAPE (node types only, ignoring identifiers and literals)
then groups functions sharing a shape and enough size. This is the reliable case: syntactic and
renamed (type-1/type-2) clones (Zhu et al. 2025); it does not claim to catch semantic clones. It
reads only and flags candidates a human reviews before extracting a shared part.
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from pathlib import Path

# Ignore trivial functions; only substantial duplicated logic is worth a look.
DEFAULT_MIN_NODES = 18


class CloneError(ValueError):
    """Source that could not be parsed."""


@dataclass(frozen=True)
class Occurrence:
    """One place a shared shape appears."""

    label: str  # the source's label (a filename)
    name: str  # the function name
    line: int
    size: int  # node count (a proxy for how much logic is duplicated)


@dataclass(frozen=True)
class CloneGroup:
    """A set of functions that share one AST shape."""

    signature: str
    occurrences: tuple[Occurrence, ...]


def shape(func: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    """A function's structural fingerprint: its AST node types, ignoring names and literals."""
    return tuple(type(node).__name__ for node in ast.walk(func))


def _signature(shape_tuple: tuple[str, ...]) -> str:
    return hashlib.sha256("|".join(shape_tuple).encode()).hexdigest()[:12]


def find_clones(sources: dict[str, str], *, min_nodes: int = DEFAULT_MIN_NODES) -> list[CloneGroup]:
    """Group functions across `sources` (label -> code) sharing an AST shape >= min_nodes."""
    buckets: dict[tuple[str, ...], list[Occurrence]] = {}
    for label, source in sources.items():
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise CloneError(f"could not parse {label}: {exc}") from exc
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                sig = shape(node)
                if len(sig) >= min_nodes:
                    occ = Occurrence(label, node.name, node.lineno, len(sig))
                    buckets.setdefault(sig, []).append(occ)
    groups = [
        CloneGroup(_signature(sig), tuple(occ)) for sig, occ in buckets.items() if len(occ) >= 2
    ]
    return sorted(groups, key=lambda g: (-g.occurrences[0].size, -len(g.occurrences)))


def scan_repo(min_nodes: int = DEFAULT_MIN_NODES, root: Path | None = None) -> list[CloneGroup]:
    """Structural clones within the parts library."""
    base = root if root is not None else Path(__file__).resolve().parent.parent
    sources = {p.name: p.read_text(encoding="utf-8") for p in sorted((base / "parts").glob("*.py"))}
    return find_clones(sources, min_nodes=min_nodes)


def render(groups: list[CloneGroup]) -> str:
    """A human-readable clone report."""
    if not groups:
        return "Clone scan: no structural duplicates found. The parts library is DRY."
    lines = ["Clone scan: structurally duplicated logic (candidates to extract):"]
    for g in groups:
        where = ", ".join(f"{o.label}:{o.line} {o.name}" for o in g.occurrences)
        lines.append(
            f"  [{g.signature}] x{len(g.occurrences)} (~{g.occurrences[0].size} nodes): {where}"
        )
    lines.append("A structural clone is a candidate for a shared part, reviewed before extracting.")
    return "\n".join(lines)


def clones(arg: str = "") -> str:
    """The `clones` verb: report structurally duplicated logic in the parts library."""
    min_nodes = DEFAULT_MIN_NODES
    arg = arg.strip()
    if arg:
        try:
            min_nodes = int(arg)
        except ValueError:
            return "Usage: clones [min-nodes]"
    return render(scan_repo(min_nodes))
