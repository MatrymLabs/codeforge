"""CARD: source_analyzer -- reverse-engineer a Python module into a validated model.

The first Reverse-Engineering Lab capability of the R&D Tech Lab directive ("the
Seed is the MUD"): ingest source, UNDERSTAND it, and emit a structured, honest
intermediate model the Seed (or a human) can inspect and correct - product
identity, entities (the data model), the public interface (API surface),
relationships (inheritance/composition), dependencies (imports), and the UNKNOWNS
it could not resolve. It never presents inferred structure as proven fact: every
model carries a confidence and an explicit list of what reduced it.

Clean-room, stdlib only (Python's own `ast`). Scope: a single Python module.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

# dynamic constructs that make static analysis unreliable (lower confidence + record as unknowns)
_DYNAMIC = {
    "exec": "exec() runs code the analyzer cannot see",
    "eval": "eval() evaluates code the analyzer cannot see",
    "__getattr__": "dynamic attribute access hides the real interface",
    "__getattribute__": "dynamic attribute access hides the real interface",
    "globals": "globals()/setattr-style mutation hides structure",
}


class AnalyzerError(ValueError):
    """Raised when the source cannot be parsed."""


@dataclass(frozen=True)
class Field:
    name: str
    annotation: str = ""  # the type as written (best-effort), or "" if untyped


@dataclass(frozen=True)
class Entity:
    """A data-carrying type (a dataclass, or a class with annotated fields)."""

    name: str
    line: int
    fields: tuple[Field, ...] = ()
    is_dataclass: bool = False
    frozen: bool = False


@dataclass(frozen=True)
class Interface:
    """A public callable/class the module exposes (the API surface)."""

    kind: str  # "function" | "class"
    name: str
    line: int
    params: tuple[str, ...] = ()


@dataclass(frozen=True)
class Model:
    """The validated intermediate model of one module - inspectable and correctable."""

    module: str
    identity: str  # the module's first docstring line (its stated purpose), or ""
    imports: tuple[str, ...] = ()
    entities: tuple[Entity, ...] = ()
    interface: tuple[Interface, ...] = ()
    relationships: tuple[tuple[str, str], ...] = ()  # (subclass, base) inheritance edges
    unknowns: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 1.0


def _ann(node: ast.expr | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except (
        ValueError,
        RecursionError,
    ):  # pragma: no cover - unparse is robust; never crash analysis
        return "?"


def _is_dataclass(cls: ast.ClassDef) -> tuple[bool, bool]:
    """(is_dataclass, frozen) from the @dataclass decorator, best-effort."""
    for dec in cls.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        name = getattr(target, "attr", getattr(target, "id", ""))
        if name == "dataclass":
            frozen = False
            if isinstance(dec, ast.Call):
                for kw in dec.keywords:
                    if kw.arg == "frozen" and isinstance(kw.value, ast.Constant):
                        frozen = bool(kw.value.value)
            return True, frozen
    return False, False


def _class_fields(cls: ast.ClassDef) -> tuple[Field, ...]:
    fields: list[Field] = []
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            fields.append(Field(stmt.target.id, _ann(stmt.annotation)))
    return tuple(fields)


def _params(func: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    a = func.args
    names = [arg.arg for arg in (*a.posonlyargs, *a.args, *a.kwonlyargs)]
    return tuple(n for n in names if n not in ("self", "cls"))


def _base_names(cls: ast.ClassDef) -> list[str]:
    out = []
    for base in cls.bases:
        name = getattr(base, "attr", getattr(base, "id", ""))
        if name and name != "object":
            out.append(name)
    return out


def analyze(source: str, *, module: str = "") -> Model:  # noqa: PLR0912
    """Extract the intermediate model of one Python module. Never raises on dynamic code;
    it lowers confidence and records the reason in `unknowns`."""
    try:
        tree = ast.parse(source, filename=module or "<source>")
    except SyntaxError as exc:
        raise AnalyzerError(f"cannot parse {module or 'source'}: {exc}") from exc  # noqa: TRY003

    identity = ast.get_docstring(tree) or ""
    identity = identity.splitlines()[0] if identity else ""

    imports: set[str] = set()
    entities: list[Entity] = []
    interface: list[Interface] = []
    relationships: list[tuple[str, str]] = []
    unknowns: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
            if any(alias.name == "*" for alias in node.names):
                unknowns.append(f"star import from {node.module or '?'} hides names")
        elif isinstance(node, ast.Name) and node.id in _DYNAMIC:
            unknowns.append(_DYNAMIC[node.id])

    # top-level classes and functions only (the module's declared surface)
    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef):
            is_dc, frozen = _is_dataclass(stmt)
            fields = _class_fields(stmt)
            if is_dc or fields:
                entities.append(Entity(stmt.name, stmt.lineno, fields, is_dc, frozen))
            if not stmt.name.startswith("_"):
                interface.append(Interface("class", stmt.name, stmt.lineno))
            for base in _base_names(stmt):
                relationships.append((stmt.name, base))
            if any(
                name in _DYNAMIC
                for name in (
                    m.name
                    for m in stmt.body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
            ):
                unknowns.append(f"{stmt.name} defines a dynamic dunder")
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and not stmt.name.startswith(
            "_"
        ):
            interface.append(Interface("function", stmt.name, stmt.lineno, _params(stmt)))

    unknowns = sorted(set(unknowns))
    # confidence: start full, dock for each distinct dynamic-construct unknown (never below 0.3)
    confidence = max(0.3, 1.0 - 0.1 * len(unknowns))
    return Model(
        module=module,
        identity=identity,
        imports=tuple(sorted(imports)),
        entities=tuple(entities),
        interface=tuple(interface),
        relationships=tuple(relationships),
        unknowns=tuple(unknowns),
        confidence=round(confidence, 2),
    )


def render(model: Model) -> str:
    """A human-readable rendering of the model (for inspection + correction)."""
    lines = [f"module: {model.module or '<source>'}  (confidence {model.confidence})"]
    if model.identity:
        lines.append(f"  identity: {model.identity}")
    if model.imports:
        lines.append(f"  depends on: {', '.join(model.imports)}")
    if model.entities:
        lines.append("  entities:")
        for e in model.entities:
            tag = "frozen dataclass" if e.frozen else "dataclass" if e.is_dataclass else "class"
            fields = ", ".join(
                f"{f.name}: {f.annotation}" if f.annotation else f.name for f in e.fields
            )
            lines.append(f"    - {e.name} ({tag}) {{{fields}}}")
    if model.interface:
        lines.append("  interface: " + ", ".join(f"{i.name}" for i in model.interface))
    if model.relationships:
        lines.append("  inherits: " + ", ".join(f"{a}->{b}" for a, b in model.relationships))
    if model.unknowns:
        lines.append("  UNKNOWNS (confidence reducers): " + "; ".join(model.unknowns))
    return "\n".join(lines)
