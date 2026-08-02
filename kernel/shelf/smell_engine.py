"""CARD: smell_engine -- detect Fowler code smells in Python via ast + metrics, with refactorings.

Stage 1 of the CodeForge Corpus roadmap (RS-2026-08-01-corpus): the smell ->
refactoring "translation matrix". This is the DETECTION half - the part the report
rates highly automatable (metrics + AST). Each finding names its corpus smell id
(SMELL.*) and the mechanical refactoring that resolves it, but the engine only
SUGGESTS - it never rewrites. Transformation stays a gated suggestion (the report
is emphatic: an autonomous rewriter can silently change behavior).

Python-native: it uses the stdlib `ast` module (no tree-sitter needed for Python),
so the whole engine is dependency-free. Detectors (>= 10 smell types):
long-method, long-parameter-list, magic-number, large-class, deep-nesting,
high-complexity, too-many-returns, bare-except, swallowed-exception,
mutable-default-arg, boolean-flag-arg, duplicate-function-body.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

_ALLOWED_NUMBERS = frozenset({0, 1, 2, -1, -2, 100, 1000})  # common, non-magic


class SmellError(ValueError):
    """Raised when the source cannot be parsed."""


@dataclass(frozen=True)
class Thresholds:
    """Tunable metric limits (deliberately strict; raise per project)."""

    max_method_statements: int = 25
    max_params: int = 5
    max_class_methods: int = 20
    max_nesting: int = 4
    max_complexity: int = 10
    max_returns: int = 5


@dataclass(frozen=True)
class Smell:
    """One detected smell: its corpus id, where it is, and the refactoring that resolves it."""

    smell_id: str  # a corpus SMELL.* / ANTIPATTERN.* id
    name: str
    line: int
    where: str
    message: str
    refactoring: str


def _count_statements(node: ast.AST) -> int:
    return sum(1 for n in ast.walk(node) if isinstance(n, ast.stmt))


def _param_count(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    a = func.args
    names = [*a.posonlyargs, *a.args, *a.kwonlyargs]
    n = len(names)
    if names and names[0].arg in ("self", "cls"):
        n -= 1
    return n


def _returns(func: ast.AST) -> int:
    return sum(1 for n in ast.walk(func) if isinstance(n, ast.Return))


_BRANCHES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.With, ast.AsyncWith)


def _complexity(func: ast.AST) -> int:
    score = 1
    for n in ast.walk(func):
        if isinstance(n, _BRANCHES):
            score += 1
        elif isinstance(n, ast.BoolOp):
            score += len(n.values) - 1
        elif isinstance(n, ast.comprehension):
            score += 1 + len(n.ifs)
    return score


_NESTERS = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)


def _nesting_depth(node: ast.AST, depth: int = 0) -> int:
    best = depth
    for child in ast.iter_child_nodes(node):
        child_depth = depth + 1 if isinstance(child, _NESTERS) else depth
        best = max(best, _nesting_depth(child, child_depth))
    return best


def _is_mutable_literal(node: ast.expr | None) -> bool:
    return isinstance(node, (ast.List, ast.Dict, ast.Set))


def _check_function(
    func: ast.FunctionDef | ast.AsyncFunctionDef, t: Thresholds, out: list[Smell]
) -> None:
    name = func.name
    stmts = _count_statements(func)
    if stmts > t.max_method_statements:
        out.append(
            Smell(
                "SMELL.LONG_METHOD",
                "Long Method",
                func.lineno,
                name,
                f"{stmts} statements exceeds {t.max_method_statements}",
                "Extract Method",
            )
        )
    params = _param_count(func)
    if params > t.max_params:
        out.append(
            Smell(
                "SMELL.LONG_PARAMETER_LIST",
                "Long Parameter List",
                func.lineno,
                name,
                f"{params} parameters exceeds {t.max_params}",
                "Introduce Parameter Object",
            )
        )
    rets = _returns(func)
    if rets > t.max_returns:
        out.append(
            Smell(
                "SMELL.TOO_MANY_RETURNS",
                "Too Many Returns",
                func.lineno,
                name,
                f"{rets} return statements exceeds {t.max_returns}",
                "Consolidate Conditional / Extract Method",
            )
        )
    cx = _complexity(func)
    if cx > t.max_complexity:
        out.append(
            Smell(
                "SMELL.HIGH_COMPLEXITY",
                "High Cyclomatic Complexity",
                func.lineno,
                name,
                f"complexity {cx} exceeds {t.max_complexity}",
                "Decompose Conditional / Extract Method",
            )
        )
    depth = _nesting_depth(func)
    if depth > t.max_nesting:
        out.append(
            Smell(
                "SMELL.DEEP_NESTING",
                "Deep Nesting",
                func.lineno,
                name,
                f"nesting depth {depth} exceeds {t.max_nesting}",
                "Replace Nested Conditional with Guard Clauses",
            )
        )
    # mutable default + boolean flag argument
    for default in [*func.args.defaults, *func.args.kw_defaults]:
        if _is_mutable_literal(default):
            out.append(
                Smell(
                    "SMELL.MUTABLE_DEFAULT_ARG",
                    "Mutable Default Argument",
                    func.lineno,
                    name,
                    "a mutable literal default is shared across calls",
                    "Use None + create inside",
                )
            )
        if isinstance(default, ast.Constant) and isinstance(default.value, bool):
            out.append(
                Smell(
                    "SMELL.BOOLEAN_FLAG_ARG",
                    "Boolean Flag Argument",
                    func.lineno,
                    name,
                    "a boolean flag parameter hides two behaviors",
                    "Replace Parameter with Explicit Methods",
                )
            )


def _check_class(cls: ast.ClassDef, t: Thresholds, out: list[Smell]) -> None:
    methods = sum(1 for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
    if methods > t.max_class_methods:
        out.append(
            Smell(
                "ANTIPATTERN.GOD_OBJECT",
                "Large Class",
                cls.lineno,
                cls.name,
                f"{methods} methods exceeds {t.max_class_methods}",
                "Extract Class along responsibility seams",
            )
        )


def _check_module(tree: ast.Module, out: list[Smell]) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                out.append(
                    Smell(
                        "SMELL.BARE_EXCEPT",
                        "Bare Except",
                        node.lineno,
                        "<except>",
                        "a bare 'except:' hides every error",
                        "Catch a specific exception",
                    )
                )
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                out.append(
                    Smell(
                        "SMELL.SWALLOWED_EXCEPTION",
                        "Swallowed Exception",
                        node.lineno,
                        "<except>",
                        "except: pass silences the failure",
                        "Handle, log, or re-raise",
                    )
                )
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
            and node.value not in _ALLOWED_NUMBERS
        ):
            out.append(
                Smell(
                    "SMELL.MAGIC_NUMBER",
                    "Magic Number",
                    getattr(node, "lineno", 0),
                    "<expr>",
                    f"literal {node.value!r} lacks a name",
                    "Replace Magic Number with a Symbolic Constant",
                )
            )


def _check_duplicates(tree: ast.Module, out: list[Smell]) -> None:
    seen: dict[str, tuple[str, int]] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and _count_statements(node) >= 4
        ):
            body_key = "".join(ast.dump(s, annotate_fields=False) for s in node.body)
            if body_key in seen:
                first_name, first_line = seen[body_key]
                out.append(
                    Smell(
                        "SMELL.DUPLICATE_CODE",
                        "Duplicate Code",
                        node.lineno,
                        node.name,
                        f"body identical to '{first_name}' (line {first_line})",
                        "Extract a shared function",
                    )
                )
            else:
                seen[body_key] = (node.name, node.lineno)


def analyze(source: str, *, path: str = "", thresholds: Thresholds | None = None) -> list[Smell]:
    """Detect code smells in Python source. Returns findings sorted by line."""
    t = thresholds or Thresholds()
    try:
        tree = ast.parse(source, filename=path or "<source>")
    except SyntaxError as exc:
        raise SmellError(f"cannot parse {path or 'source'}: {exc}") from exc
    out: list[Smell] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _check_function(node, t, out)
        elif isinstance(node, ast.ClassDef):
            _check_class(node, t, out)
    _check_module(tree, out)
    _check_duplicates(tree, out)
    return sorted(out, key=lambda s: (s.line, s.smell_id))


def smell_ids() -> frozenset[str]:
    """Every corpus smell id this engine can detect (for coverage against the corpus)."""
    return frozenset(
        {
            "SMELL.LONG_METHOD",
            "SMELL.LONG_PARAMETER_LIST",
            "SMELL.TOO_MANY_RETURNS",
            "SMELL.HIGH_COMPLEXITY",
            "SMELL.DEEP_NESTING",
            "SMELL.MUTABLE_DEFAULT_ARG",
            "SMELL.BOOLEAN_FLAG_ARG",
            "ANTIPATTERN.GOD_OBJECT",
            "SMELL.BARE_EXCEPT",
            "SMELL.SWALLOWED_EXCEPTION",
            "SMELL.MAGIC_NUMBER",
            "SMELL.DUPLICATE_CODE",
        }
    )
