"""CARD: api_diff -- reverse-engineer the public API of two module versions and diff them.

Batch 4 of the R&D Tech Lab Reverse-Engineering Lab (composes on EXP-15): read the OLD
and NEW source of one module, extract each one's public surface (module-level functions
and classes + their public methods, with signatures), and report what CHANGED - split
into BREAKING changes (a consumer can stop compiling/working) and COMPATIBLE additions.

A change is BREAKING when it removes or narrows the contract a caller relies on:
removed symbol, removed public method, a required parameter added, a parameter removed
or renamed, or a parameter that lost its default. A change is COMPATIBLE when it only
adds capability: a new symbol/method, or a new parameter that carries a default.

It never presents the verdict as proven fact for behavior - it diffs the SIGNATURE
contract, which it can see, and says plainly what it cannot: a body change with an
identical signature is reported as `behavior_may_have_changed`, not "safe".

Clean-room, stdlib only (Python's own `ast`). Scope: one module, two versions.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


class ApiDiffError(ValueError):
    """Raised when either source cannot be parsed."""


@dataclass(frozen=True)
class Signature:
    """A callable's public parameter contract."""

    required: tuple[str, ...] = ()  # params with no default (order-significant)
    optional: tuple[str, ...] = ()  # params with a default
    star_args: bool = False  # accepts *args
    star_kwargs: bool = False  # accepts **kwargs


@dataclass(frozen=True)
class Symbol:
    """One public API member: a function, a class, or a class's public method."""

    kind: str  # "function" | "class" | "method"
    qualname: str  # "func" or "Class" or "Class.method"
    signature: Signature | None = None  # None for a bare class node


@dataclass(frozen=True)
class Change:
    """One diff finding, classified by compatibility impact."""

    impact: str  # "breaking" | "compatible" | "unknown"
    kind: str  # e.g. "removed_symbol", "added_required_param", "body_changed"
    qualname: str
    detail: str


@dataclass(frozen=True)
class DiffReport:
    """The validated API-diff report - inspectable and honest about what it cannot see."""

    module: str
    breaking: tuple[Change, ...] = ()
    compatible: tuple[Change, ...] = ()
    unknown: tuple[Change, ...] = ()
    unknowns: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 1.0

    @property
    def is_breaking(self) -> bool:
        return bool(self.breaking)


def _signature(func: ast.FunctionDef | ast.AsyncFunctionDef) -> Signature:
    a = func.args
    positional = [*a.posonlyargs, *a.args]
    n_defaults = len(a.defaults)
    required, optional = [], []
    for i, arg in enumerate(positional):
        if arg.arg in ("self", "cls"):
            continue
        # the last n_defaults positional args carry defaults
        if i >= len(positional) - n_defaults:
            optional.append(arg.arg)
        else:
            required.append(arg.arg)
    for i, arg in enumerate(a.kwonlyargs):
        if a.kw_defaults[i] is None:
            required.append(arg.arg)
        else:
            optional.append(arg.arg)
    return Signature(tuple(required), tuple(optional), a.vararg is not None, a.kwarg is not None)


def _public_surface(tree: ast.Module) -> tuple[dict[str, Symbol], dict[str, str]]:
    """Return {qualname: Symbol} and {qualname: body_hash} for the public API."""
    symbols: dict[str, Symbol] = {}
    bodies: dict[str, str] = {}
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and not stmt.name.startswith(
            "_"
        ):
            symbols[stmt.name] = Symbol("function", stmt.name, _signature(stmt))
            bodies[stmt.name] = ast.dump(ast.Module(body=stmt.body, type_ignores=[]))
        elif isinstance(stmt, ast.ClassDef) and not stmt.name.startswith("_"):
            symbols[stmt.name] = Symbol("class", stmt.name)
            for m in stmt.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                    not m.name.startswith("_") or m.name == "__init__"
                ):
                    q = f"{stmt.name}.{m.name}"
                    symbols[q] = Symbol("method", q, _signature(m))
                    bodies[q] = ast.dump(ast.Module(body=m.body, type_ignores=[]))
    return symbols, bodies


def _diff_signature(q: str, old: Signature, new: Signature, out: list[Change]) -> None:
    old_all = set(old.required) | set(old.optional)
    new_all = set(new.required) | set(new.optional)
    for removed in sorted(old_all - new_all):
        if not (new.star_kwargs or (removed in old.optional and new.star_kwargs)):
            out.append(Change("breaking", "removed_param", q, f"parameter '{removed}' removed"))
    for added in sorted(set(new.required) - old_all):
        out.append(
            Change("breaking", "added_required_param", q, f"new required parameter '{added}'")
        )
    for added in sorted(set(new.optional) - old_all):
        out.append(
            Change("compatible", "added_optional_param", q, f"new optional parameter '{added}'")
        )
    for lost in sorted(set(old.optional) & new_all):
        if lost in new.required:
            out.append(
                Change("breaking", "default_removed", q, f"parameter '{lost}' lost its default")
            )
    if old.star_kwargs and not new.star_kwargs:
        out.append(Change("breaking", "removed_kwargs", q, "no longer accepts **kwargs"))
    if old.star_args and not new.star_args:
        out.append(Change("breaking", "removed_varargs", q, "no longer accepts *args"))


def diff(old_source: str, new_source: str, *, module: str = "") -> DiffReport:
    """Diff the public API of two versions of one module. Never raises on a body change;
    it classifies signature changes and admits when only behavior may have moved."""
    try:
        old_tree = ast.parse(old_source, filename=f"{module or 'source'} (old)")
        new_tree = ast.parse(new_source, filename=f"{module or 'source'} (new)")
    except SyntaxError as exc:
        raise ApiDiffError(f"cannot parse {module or 'source'}: {exc}") from exc

    old_syms, old_bodies = _public_surface(old_tree)
    new_syms, new_bodies = _public_surface(new_tree)

    changes: list[Change] = []
    unknowns: list[str] = []

    for q in sorted(set(old_syms) - set(new_syms)):
        changes.append(Change("breaking", "removed_symbol", q, f"{old_syms[q].kind} '{q}' removed"))
    for q in sorted(set(new_syms) - set(old_syms)):
        changes.append(Change("compatible", "added_symbol", q, f"new {new_syms[q].kind} '{q}'"))

    for q in sorted(set(old_syms) & set(new_syms)):
        old_sym, new_sym = old_syms[q], new_syms[q]
        if old_sym.kind != new_sym.kind:
            changes.append(
                Change("breaking", "kind_changed", q, f"{old_sym.kind} became {new_sym.kind}")
            )
            continue
        if old_sym.signature and new_sym.signature:
            if old_sym.signature != new_sym.signature:
                _diff_signature(q, old_sym.signature, new_sym.signature, changes)
            elif old_bodies.get(q) != new_bodies.get(q):
                changes.append(
                    Change(
                        "unknown",
                        "body_changed",
                        q,
                        "signature identical; behavior may have changed",
                    )
                )
                unknowns.append(
                    f"{q}: body changed under an unchanged signature (behavior not verified)"
                )

    breaking = tuple(c for c in changes if c.impact == "breaking")
    compatible = tuple(c for c in changes if c.impact == "compatible")
    unknown = tuple(c for c in changes if c.impact == "unknown")
    unknowns = sorted(set(unknowns))
    confidence = round(max(0.3, 1.0 - 0.1 * len(unknowns)), 2)
    return DiffReport(module, breaking, compatible, unknown, tuple(unknowns), confidence)


def render(report: DiffReport) -> str:
    """A human-readable rendering of the diff (for release notes / review)."""
    verdict = "BREAKING" if report.is_breaking else "compatible"
    lines = [
        f"api diff: {report.module or '<module>'}  [{verdict}]  (confidence {report.confidence})"
    ]
    for label, group in (
        ("BREAKING", report.breaking),
        ("compatible", report.compatible),
        ("unknown", report.unknown),
    ):
        if group:
            lines.append(f"  {label}:")
            for c in group:
                lines.append(f"    - [{c.kind}] {c.qualname}: {c.detail}")
    if not (report.breaking or report.compatible or report.unknown):
        lines.append("  no public API changes")
    return "\n".join(lines)
