"""CARD: call_graph -- reverse-engineer a module's internal call graph, dead code, and hotspots.

Batch 5 of the R&D Tech Lab Reverse-Engineering Lab (composes on EXP-15/16/17): read one
Python module and infer WHO CALLS WHOM inside it - the call edges between the module's
own functions and methods, the entrypoints (public, called by nothing internal), the
likely-dead code (private and called by nothing), and the hotspots (called from the most
places).

Two structural findings a reviewer wants first:
  * dead code - a PRIVATE function/method that no other function in the module calls
    (a public one may be an API entry, so it is entrypoint, not dead).
  * hotspots - the internal callables with the highest in-degree (change them carefully).

It never presents "dead" as proven fact. Dynamic dispatch (`getattr`, a call through a
variable, a decorator that may register the function) is recorded as an unknown and
lowers confidence - a function reached only dynamically would look dead but is not, so
the report says where it is blind rather than deleting anything.

Clean-room, stdlib only (Python's own `ast`). Scope: one Python module.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


class CallGraphError(ValueError):
    """Raised when the source cannot be parsed."""


@dataclass(frozen=True)
class CallEdge:
    """`caller` calls `callee` (both are this module's own callables)."""

    caller: str
    callee: str


@dataclass(frozen=True)
class Callable:
    """One function/method defined in the module, with its call degrees."""

    qualname: str  # "func" or "Class.method"
    kind: str  # "function" | "method"
    is_public: bool
    in_degree: int = 0  # how many internal callables call it
    out_degree: int = 0  # how many distinct internal callables it calls


@dataclass(frozen=True)
class CallGraphReport:
    """The validated call-graph report - inspectable and honest about dynamic blindness."""

    module: str
    callables: tuple[Callable, ...] = ()
    edges: tuple[CallEdge, ...] = ()
    entrypoints: tuple[str, ...] = ()  # public, no internal caller
    dead_code: tuple[str, ...] = ()  # private, no internal caller (candidate only)
    hotspots: tuple[str, ...] = ()  # highest in-degree
    recursive: tuple[str, ...] = ()  # calls itself
    unknowns: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 1.0


def _defs(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Map qualname -> def node for every top-level function and one-level method."""
    out: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[stmt.name] = stmt
        elif isinstance(stmt, ast.ClassDef):
            for m in stmt.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out[f"{stmt.name}.{m.name}"] = m
    return out


def _called_names(func: ast.AST) -> tuple[set[str], set[str], list[str]]:
    """(bare names called, attribute methods called, dynamic-dispatch reasons) inside a function."""
    bare: set[str] = set()
    attrs: set[str] = set()
    dynamic: list[str] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                if target.id in ("getattr", "setattr"):
                    dynamic.append(f"{target.id}() dispatch hides the real callee")
                else:
                    bare.add(target.id)
            elif isinstance(target, ast.Attribute):
                # self.method(...) or obj.method(...) -> record the method name
                attrs.add(target.attr)
    return bare, attrs, dynamic


def analyze(source: str, *, module: str = "", hotspot_count: int = 5) -> CallGraphReport:  # noqa: PLR0912
    """Reverse-engineer the internal call graph of one module. Never raises on dynamic
    dispatch; it lowers confidence and records where it cannot see the callee."""
    try:
        tree = ast.parse(source, filename=module or "<source>")
    except SyntaxError as exc:
        raise CallGraphError(f"cannot parse {module or 'source'}: {exc}") from exc  # noqa: TRY003

    defs = _defs(tree)
    # index simple names -> qualnames. A method `run` maps from both "run" and "Class.run".
    by_simple: dict[str, list[str]] = {}
    for q in defs:
        simple = q.split(".")[-1]
        by_simple.setdefault(simple, []).append(q)

    edges: set[tuple[str, str]] = set()
    unknowns: list[str] = []
    recursive: set[str] = set()

    for q, node in defs.items():
        bare, attrs, dynamic = _called_names(node)
        for reason in dynamic:
            unknowns.append(f"{q}: {reason}")
        # a bare call `foo()` resolves to a top-level function foo if defined
        for name in bare:
            if name in defs:  # top-level function name == qualname
                if name == q:
                    recursive.add(q)
                else:
                    edges.add((q, name))
        # a method call `self.foo()` / `obj.foo()` resolves to any method named foo
        for name in attrs:
            for callee in by_simple.get(name, ()):
                if "." in callee:  # only resolve to methods (attribute calls are on objects)
                    if callee == q:
                        recursive.add(q)
                    else:
                        edges.add((q, callee))

    # any simple name loaded ANYWHERE in the module (dispatch tables, callbacks,
    # decorators, module-level calls) counts as "used" - so a registered handler is
    # not mistaken for dead code. This is the key false-positive guard.
    referenced: set[str] = {
        n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    }
    attr_referenced: set[str] = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}

    in_deg = {q: 0 for q in defs}  # noqa: C420
    out_deg = {q: 0 for q in defs}  # noqa: C420
    for _caller, callee in edges:
        in_deg[callee] += 1
    for caller in defs:
        out_deg[caller] = len({d for c, d in edges if c == caller})

    def is_public(q: str) -> bool:
        return not q.split(".")[-1].startswith("_")  # noqa: PLC0207

    def is_dunder(q: str) -> bool:
        simple = q.split(".")[-1]  # noqa: PLC0207
        return simple.startswith("__") and simple.endswith("__")

    callables = tuple(
        Callable(q, "method" if "." in q else "function", is_public(q), in_deg[q], out_deg[q])
        for q in sorted(defs)
    )

    def is_referenced(q: str) -> bool:
        """The callable's name appears somewhere beyond a resolved internal call edge."""
        simple = q.split(".")[-1]  # noqa: PLC0207
        return simple in referenced or simple in attr_referenced

    entrypoints = tuple(sorted(q for q in defs if in_deg[q] == 0 and is_public(q)))
    # dead = private, no internal caller, not recursive, AND its name is referenced nowhere
    # (a name used in a dispatch table / callback / decorator is NOT dead - honesty guard)
    dead_code = tuple(
        sorted(
            q
            for q in defs
            if in_deg[q] == 0
            and not is_public(q)
            and not is_dunder(q)  # dunders are called implicitly (construction, operators)
            and q not in recursive
            and not is_referenced(q)
        )
    )
    ranked = sorted(defs, key=lambda q: (-in_deg[q], q))
    hotspots = tuple(q for q in ranked[:hotspot_count] if in_deg[q] > 0)

    unknowns = sorted(set(unknowns))
    # dynamic dispatch means "dead" is uncertain; dock per distinct unknown, floor 0.3
    confidence = round(max(0.3, 1.0 - 0.1 * len(unknowns)), 2)
    return CallGraphReport(
        module=module,
        callables=callables,
        edges=tuple(sorted((CallEdge(c, d) for c, d in edges), key=lambda e: (e.caller, e.callee))),
        entrypoints=entrypoints,
        dead_code=dead_code,
        hotspots=hotspots,
        recursive=tuple(sorted(recursive)),
        unknowns=tuple(unknowns),
        confidence=confidence,
    )


def render(report: CallGraphReport) -> str:
    """A human-readable rendering of the call graph (for review + refactoring)."""
    header = (
        f"call graph: {report.module or '<source>'}  "
        f"({len(report.callables)} callables, {len(report.edges)} edges, conf {report.confidence})"
    )
    lines = [header]
    if report.hotspots:
        lines.append("  hotspots (most-called): " + ", ".join(report.hotspots))
    if report.entrypoints:
        lines.append(
            f"  entrypoints ({len(report.entrypoints)}): " + ", ".join(report.entrypoints[:8])
        )
    if report.recursive:
        lines.append("  recursive: " + ", ".join(report.recursive))
    if report.dead_code:
        lines.append("  DEAD-CODE CANDIDATES (private, uncalled): " + ", ".join(report.dead_code))
    else:
        lines.append("  dead-code candidates: none")
    if report.unknowns:
        lines.append("  UNKNOWNS (confidence reducers): " + "; ".join(report.unknowns))
    return "\n".join(lines)
