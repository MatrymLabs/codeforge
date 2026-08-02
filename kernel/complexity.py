"""CARD: complexity -- measure cyclomatic complexity per function (the Analyze third fold).

Passing tests never means the code is good (Szych & Schwerk 2026): holistic evaluation needs static
quality metrics too. This tool computes McCabe cyclomatic complexity for every function with stdlib
`ast` (no dependency), flags the hot-spots over a threshold, and reports them: the third fold
beyond tests, lint, and coverage. It reads only; it never edits code. Research foundation:
docs/continuous_improvement.md.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

DEFAULT_THRESHOLD = 10  # McCabe's common "refactor candidate" line

# Each of these AST nodes is one decision point (a branch in the control-flow graph).
_BRANCH = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.Assert,
    ast.IfExp,
    ast.match_case,
)


class ComplexityError(ValueError):
    """Source that could not be parsed."""


@dataclass(frozen=True)
class FunctionComplexity:
    """One function's cyclomatic complexity and where it is defined."""

    name: str
    complexity: int
    line: int


def _own_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """Descendants of `node`, not descending into a nested function or class (each scored once)."""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        child = stack.pop()
        yield child
        if not isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            stack.extend(ast.iter_child_nodes(child))


def complexity_of(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """McCabe cyclomatic complexity of a function: 1 + its decision points."""
    score = 1
    for child in _own_nodes(func):
        if isinstance(child, _BRANCH):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += len(child.values) - 1  # each extra `and`/`or` operand is a branch
        elif isinstance(child, ast.comprehension):
            score += 1 + len(child.ifs)  # the implicit loop, plus each filter
    return score


def scan_source(source: str) -> list[FunctionComplexity]:
    """Complexity of every function and method in `source`, most complex first."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ComplexityError(f"could not parse source: {exc}") from exc
    found = [
        FunctionComplexity(node.name, complexity_of(node), node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    return sorted(found, key=lambda f: (-f.complexity, f.line))


def scan_repo(
    threshold: int = DEFAULT_THRESHOLD, root: Path | None = None
) -> list[tuple[str, FunctionComplexity]]:
    """Every function in the parts library at or above `threshold`, most complex first."""
    base = root if root is not None else Path(__file__).resolve().parent.parent
    hot: list[tuple[str, FunctionComplexity]] = []
    for path in sorted((base / "parts").glob("*.py")):
        for fc in scan_source(path.read_text(encoding="utf-8")):
            if fc.complexity >= threshold:
                hot.append((path.name, fc))
    return sorted(hot, key=lambda item: -item[1].complexity)


def render(hot: list[tuple[str, FunctionComplexity]], threshold: int = DEFAULT_THRESHOLD) -> str:
    """A human-readable complexity report."""
    if not hot:
        return f"Complexity: no function at or above {threshold}. The parts library is lean."
    lines = [f"Complexity hot-spots (cyclomatic >= {threshold}):"]
    lines += [f"  {fc.complexity:>3}  {fname}:{fc.line} {fc.name}" for fname, fc in hot]
    lines.append(
        "High complexity is a refactor candidate, not a failure (holistic eval, not pass/fail)."
    )
    return "\n".join(lines)


def complexity(arg: str = "") -> str:
    """The `complexity` verb: report the parts library's cyclomatic-complexity hot-spots."""
    threshold = DEFAULT_THRESHOLD
    arg = arg.strip()
    if arg:
        try:
            threshold = int(arg)
        except ValueError:
            return "Usage: complexity [threshold]"
    return render(scan_repo(threshold), threshold)
