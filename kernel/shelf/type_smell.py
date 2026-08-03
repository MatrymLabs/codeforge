"""CARD: type_smell -- detect risky type-related practices (type smells) via ast.

Reverse-engineered (RD-2026-0001) from the "Python Coding Practices: A Scholarly Survey
(2021-2026)" thread on risky type-related practices - grounded in Magalhaes & Montandon (2026),
"Understanding Type Hints in Python Libraries and Frameworks" (ICPC 2026): 91% of popular
libraries carry SOME hints but typically cover only ~13.6% of code, and inconsistent parameter
typing is a real, hard-to-find defect source. The structural smell engine (smell_engine.py)
covers Fowler smells; this is its TYPE-HYGIENE sibling - the same `analyze(source) -> findings`
shape, a `TYPE_SMELL.*` corpus namespace, SUGGEST-ONLY.

Detectors:
- TYPE_SMELL.UNTYPED_PUBLIC_API - a public function with parameters but no annotations at all
  (no param types, no return type): the type system is switched off for a public surface.
- TYPE_SMELL.PARTIAL_ANNOTATION - a public function partly annotated (some param/return slots
  typed, others not): a half-done signature, which mypy --strict would reject.
- TYPE_SMELL.ANY_ON_PUBLIC - `Any` on a public function's parameter or return: a silent opt-out
  that propagates untyped values past the boundary.
- TYPE_SMELL.INCONSISTENT_PARAM_TYPE - one parameter NAME annotated with two different types
  across the module (the survey's core finding): a strong confusion signal for a reader.

Honesty contract (inherited from the Reverse-Engineering Lab): SINGLE-MODULE, SYNTACTIC scope.
It does not resolve imported aliases, honor `if TYPE_CHECKING`, or prove a type wrong - two
different annotations for one name may both be correct in context. Private names (leading `_`,
which also covers dunders) and the leading `self`/`cls` are out of scope. SUGGEST-ONLY: a human
confirms every finding.

Clean-room, stdlib only (`ast`).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


class TypeSmellError(ValueError):
    """Raised when the source cannot be parsed."""


@dataclass(frozen=True)
class TypeSmell:
    """One detected type smell: its corpus id, where it is, and the fix that resolves it."""

    smell_id: str  # a corpus TYPE_SMELL.* id
    name: str  # the function (or parameter) it concerns
    line: int
    where: str  # a human-readable location, e.g. "def parse_row(...)"
    message: str
    suggestion: str


def _is_public(name: str) -> bool:
    """Public = not a leading-underscore name (which also filters dunders like __init__)."""
    return not name.startswith("_")


def _real_params(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
    """The parameters that carry a type obligation: positional + keyword-only + *args/**kwargs,
    minus a leading self/cls (an instance/class method's receiver is not annotated)."""
    args = func.args
    params: list[ast.arg] = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    if params and params[0].arg in ("self", "cls"):
        params = params[1:]
    if args.vararg is not None:
        params.append(args.vararg)
    if args.kwarg is not None:
        params.append(args.kwarg)
    return params


def _mentions_any(annotation: ast.expr | None) -> bool:
    """True if an annotation names `Any` (bare, `typing.Any`, or nested like `list[Any]`)."""
    if annotation is None:
        return False
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name) and node.id == "Any":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "Any":
            return True
    return False


def _annotation_str(annotation: ast.expr | None) -> str | None:
    """The source text of an annotation (for cross-function comparison), or None if absent."""
    if annotation is None:
        return None
    return ast.unparse(annotation)


def _signature(func: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    names = ", ".join(p.arg for p in _real_params(func))
    return f"def {func.name}({names})"


def _check_function(func: ast.FunctionDef | ast.AsyncFunctionDef, out: list[TypeSmell]) -> None:
    if not _is_public(func.name):
        return
    params = _real_params(func)
    where = _signature(func)

    # ANY_ON_PUBLIC: independent of completeness - Any anywhere on a public signature.
    any_slots = [p.arg for p in params if _mentions_any(p.annotation)]
    if _mentions_any(func.returns):
        any_slots.append("return")
    if any_slots:
        out.append(
            TypeSmell(
                "TYPE_SMELL.ANY_ON_PUBLIC",
                func.name,
                func.lineno,
                where,
                f"`Any` on public {', '.join(any_slots)}: values pass the boundary untyped",
                "replace Any with the real type, or a Protocol/TypeVar if it is truly generic",
            )
        )

    if not params:
        return  # no parameters -> no param-completeness obligation in this lens

    annotated_params = sum(1 for p in params if p.annotation is not None)
    return_annotated = func.returns is not None
    total = len(params) + 1  # +1 for the return slot
    annotated = annotated_params + (1 if return_annotated else 0)

    if annotated == 0:
        out.append(
            TypeSmell(
                "TYPE_SMELL.UNTYPED_PUBLIC_API",
                func.name,
                func.lineno,
                where,
                f"public function has {len(params)} parameter(s) and no type annotations",
                "annotate every parameter and the return; a typed public API is the contract",
            )
        )
    elif annotated < total:
        missing = [p.arg for p in params if p.annotation is None]
        if not return_annotated:
            missing.append("return")
        out.append(
            TypeSmell(
                "TYPE_SMELL.PARTIAL_ANNOTATION",
                func.name,
                func.lineno,
                where,
                f"half-annotated signature; missing: {', '.join(missing)}",
                "complete the annotations - a partial signature is what mypy --strict rejects",
            )
        )


def _check_inconsistent_params(tree: ast.AST, out: list[TypeSmell]) -> None:
    """One parameter NAME carrying two different annotations across the module's public
    functions is the survey's core 'risky type practice' - flag it once, at first sight."""
    seen: dict[str, tuple[str, int, str]] = {}  # name -> (annotation_str, line, where)
    reported: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not _is_public(
            node.name
        ):
            continue
        where = _signature(node)
        for p in _real_params(node):
            ann = _annotation_str(p.annotation)
            if ann is None:
                continue
            if p.arg not in seen:
                seen[p.arg] = (ann, p.lineno, where)
            elif seen[p.arg][0] != ann and p.arg not in reported:
                first_ann, first_line, _ = seen[p.arg]
                reported.add(p.arg)
                out.append(
                    TypeSmell(
                        "TYPE_SMELL.INCONSISTENT_PARAM_TYPE",
                        p.arg,
                        first_line,
                        where,
                        f"parameter `{p.arg}` is `{first_ann}` (line {first_line}) but `{ann}` "
                        f"(line {p.lineno}): one name, two types confuses every reader",
                        "unify the type, or rename one parameter so the two meanings are distinct",
                    )
                )


def analyze(source: str, *, path: str = "") -> list[TypeSmell]:
    """Detect type smells in Python source. Returns findings sorted by (line, id).

    source: the module text. path: a label used only in the parse error message.
    Raises TypeSmellError if the source will not parse (fail loud, like smell_engine).
    """
    try:
        tree = ast.parse(source, filename=path or "<source>")
    except SyntaxError as exc:
        raise TypeSmellError(f"cannot parse {path or 'source'}: {exc}") from exc
    out: list[TypeSmell] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _check_function(node, out)
    _check_inconsistent_params(tree, out)
    return sorted(out, key=lambda s: (s.line, s.smell_id))


def smell_ids() -> frozenset[str]:
    """Every corpus type-smell id this lens can detect (for coverage against the corpus)."""
    return frozenset(
        {
            "TYPE_SMELL.UNTYPED_PUBLIC_API",
            "TYPE_SMELL.PARTIAL_ANNOTATION",
            "TYPE_SMELL.ANY_ON_PUBLIC",
            "TYPE_SMELL.INCONSISTENT_PARAM_TYPE",
        }
    )


def render(smells: list[TypeSmell]) -> str:
    """A human-readable rendering (SUGGEST-ONLY: a reader decides)."""
    if not smells:
        return "type_smell: [CLEAN] no type smells detected"
    lines = [f"type_smell: {len(smells)} finding(s) - suggest-only, a human confirms"]
    for s in smells:
        lines.append(f"  L{s.line} [{s.smell_id}] {s.where}: {s.message}")
        lines.append(f"        -> {s.suggestion}")
    return "\n".join(lines)
