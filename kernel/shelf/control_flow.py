"""CARD: control_flow -- reverse-engineer each function's control-flow shape and exit points.

Batch 7 of the R&D Tech Lab Reverse-Engineering Lab (extends EXP-19): where the call
graph shows who-calls-whom, this reads the control flow INSIDE each function - the
branches, loops, exception handlers, the maximum nesting depth, the number of exit
points (returns/raises), and whether the function is written with early-return guard
clauses or deep nesting.

It answers "how does this function actually flow?" for a reviewer or a test author:
  * branch_points / loops / handlers - the decision surface.
  * max_depth - how deeply nested the logic gets.
  * exit_points - returns + raises (many exits = many paths to test).
  * guard_style - "guard-clauses" (early returns, shallow) vs "nested" (deep) vs "linear".

It never claims to have found every path. Dynamic control (a call that may not return, a
generator's suspension, exceptions from callees) is not modelled; the report says it maps
STATIC structure, and confidence reflects only parse success. It reports facts a human
reads, not a proof of reachability.

Clean-room, stdlib only (Python's own `ast`). Scope: one Python module's functions.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

_BRANCHES = (ast.If, ast.IfExp, ast.Match)
_LOOPS = (ast.For, ast.AsyncFor, ast.While)
_NESTERS = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.Match)


class ControlFlowError(ValueError):
    """Raised when the source cannot be parsed."""


@dataclass(frozen=True)
class FlowProfile:
    """The control-flow shape of one function."""

    qualname: str
    line: int
    branch_points: int  # if / conditional-expr / match
    loops: int
    handlers: int  # except clauses
    max_depth: int  # deepest nesting of control structures
    exit_points: int  # return + raise statements
    guard_style: str  # "linear" | "guard-clauses" | "nested"
    is_generator: bool  # contains yield / yield from


@dataclass(frozen=True)
class ControlFlowReport:
    """The validated control-flow report of one module."""

    module: str
    functions: tuple[FlowProfile, ...] = ()
    complex_functions: tuple[str, ...] = ()  # deep OR many-exit (review-first shortlist)
    unknowns: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 1.0


def _depth(node: ast.AST, depth: int = 0) -> int:
    best = depth
    for child in ast.iter_child_nodes(node):
        child_depth = depth + 1 if isinstance(child, _NESTERS) else depth
        best = max(best, _depth(child, child_depth))
    return best


def _count(func: ast.AST, types: tuple[type, ...]) -> int:
    return sum(1 for n in ast.walk(func) if isinstance(n, types))


def _direct_yield(func: ast.AST) -> bool:
    """yield that belongs to THIS function (not a nested def)."""
    found = False

    class V(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            pass  # do not descend into nested functions

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            pass

        def visit_Yield(self, node: ast.Yield) -> None:  # noqa: ARG002
            nonlocal found
            found = True

        def visit_YieldFrom(self, node: ast.YieldFrom) -> None:  # noqa: ARG002
            nonlocal found
            found = True

    for child in ast.iter_child_nodes(func):
        V().visit(child)
    return found


def _guard_style(
    func: ast.FunctionDef | ast.AsyncFunctionDef, max_depth: int, branches: int
) -> str:
    if branches == 0:
        return "linear"
    # early returns among the top-level statements signal guard-clause style
    early_returns = 0
    top = func.body
    for stmt in top[:-1]:  # a trailing return is the normal single exit, not a guard
        if isinstance(stmt, ast.If) and any(
            isinstance(s, (ast.Return, ast.Raise)) for s in stmt.body
        ):
            early_returns += 1
    if early_returns >= 1 and max_depth <= 2:  # noqa: PLR2004
        return "guard-clauses"
    return "nested" if max_depth >= 3 else "linear"  # noqa: PLR2004


def _profile(func: ast.FunctionDef | ast.AsyncFunctionDef, qual: str) -> FlowProfile:
    branch_points = _count(func, _BRANCHES)
    loops = _count(func, _LOOPS)
    handlers = _count(func, (ast.ExceptHandler,))
    max_depth = _depth(func)
    exits = _count(func, (ast.Return, ast.Raise))
    return FlowProfile(
        qualname=qual,
        line=func.lineno,
        branch_points=branch_points,
        loops=loops,
        handlers=handlers,
        max_depth=max_depth,
        exit_points=exits,
        guard_style=_guard_style(func, max_depth, branch_points),
        is_generator=_direct_yield(func),
    )


def analyze(
    source: str, *, module: str = "", deep_threshold: int = 4, exit_threshold: int = 5
) -> ControlFlowReport:
    """Reverse-engineer per-function control flow. Never raises on complex code; it maps
    static structure and says so."""
    try:
        tree = ast.parse(source, filename=module or "<source>")
    except SyntaxError as exc:
        raise ControlFlowError(f"cannot parse {module or 'source'}: {exc}") from exc  # noqa: TRY003

    profiles: list[FlowProfile] = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            profiles.append(_profile(stmt, stmt.name))
        elif isinstance(stmt, ast.ClassDef):
            for m in stmt.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    profiles.append(_profile(m, f"{stmt.name}.{m.name}"))

    complex_functions = tuple(
        p.qualname
        for p in profiles
        if p.max_depth >= deep_threshold or p.exit_points >= exit_threshold
    )
    return ControlFlowReport(
        module=module,
        functions=tuple(profiles),
        complex_functions=complex_functions,
        unknowns=(),
        confidence=1.0,
    )


def render(report: ControlFlowReport) -> str:
    """A human-readable rendering of the control-flow report."""
    lines = [f"control flow: {report.module or '<source>'}  ({len(report.functions)} functions)"]
    for p in report.functions:
        tag = (
            f"depth {p.max_depth}, {p.branch_points} branch, {p.loops} loop, "
            f"{p.exit_points} exit, {p.guard_style}"
        )
        gen = " [generator]" if p.is_generator else ""
        lines.append(f"    {p.qualname} (line {p.line}): {tag}{gen}")
    if report.complex_functions:
        lines.append("  REVIEW-FIRST (deep or many-exit): " + ", ".join(report.complex_functions))
    return "\n".join(lines)
