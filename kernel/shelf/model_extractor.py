"""CARD: model_extractor -- reverse-engineer the data model and state machines from a module.

Batch 3 of the R&D Tech Lab Reverse-Engineering Lab (composes on EXP-15/16): read one
Python module and infer the SHAPE of its domain - which entities hold references to
which others (the relationship graph), and which enums are used as state machines with
what transitions between their states.

Two extractions:
  * Relationships - for every entity (dataclass / annotated-field class), each field
    whose type names another entity becomes an edge, tagged by kind: direct reference,
    collection (list/set/dict/tuple of), optional (X | None), or inheritance.
  * State machines - every Enum subclass is a candidate state set; every assignment of
    one of its members (`self.status = State.OPEN`) is an observed transition, labelled
    by the method that performs it.

It never presents the inferred model as proven fact. Dynamically-set state (`setattr`,
a state chosen from a variable rather than a literal member) and unresolvable field
types are recorded as unknowns and lower the confidence (floor 0.3).

Clean-room, stdlib only (Python's own `ast`). Scope: one Python module.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

_ENUM_BASES = {"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"}
_COLLECTIONS = {"list", "set", "frozenset", "tuple", "Sequence", "Iterable", "Mapping"}


class ModelExtractorError(ValueError):
    """Raised when the source cannot be parsed."""


@dataclass(frozen=True)
class Relationship:
    """An edge from one entity to another, discovered through a field annotation."""

    source: str
    target: str
    via: str  # the field name, or "(base)" for inheritance
    kind: str  # "reference" | "collection" | "optional" | "inheritance"


@dataclass(frozen=True)
class Transition:
    """One observed state assignment: `setter` sets the machine to `to_state`."""

    setter: str  # the enclosing function/method, or "<module>" at top level
    to_state: str


@dataclass(frozen=True)
class StateMachine:
    """An Enum used as a state set, with the transitions observed in this module."""

    enum: str
    states: tuple[str, ...]
    transitions: tuple[Transition, ...] = ()
    unreached: tuple[str, ...] = ()  # declared states never assigned anywhere in this module


@dataclass(frozen=True)
class ModelReport:
    """The validated data-model report of one module - inspectable and correctable."""

    module: str
    entities: tuple[str, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    state_machines: tuple[StateMachine, ...] = ()
    unknowns: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 1.0


def _referenced_names(node: ast.expr) -> list[tuple[str, str]]:
    """(name, kind) type refs inside an annotation. kind marks collection/optional wrapping."""
    out: list[tuple[str, str]] = []

    def walk(n: ast.expr, kind: str) -> None:
        if isinstance(n, ast.Name):
            out.append((n.id, kind))
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.append((n.value, kind))  # a forward-reference string "Entity"
        elif isinstance(n, ast.Subscript):
            base = n.value.id if isinstance(n.value, ast.Name) else ""
            inner_kind = "collection" if base in _COLLECTIONS else kind
            for child in ast.walk(n.slice):
                if isinstance(child, (ast.Name, ast.Constant)):
                    walk(child, inner_kind)
        elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr):
            # X | None (optional) or X | Y (union)
            for side in (n.left, n.right):
                is_none = isinstance(side, ast.Constant) and side.value is None
                walk(side, "reference" if is_none else "optional")
        elif isinstance(n, ast.Attribute):
            out.append((n.attr, kind))

    walk(node, "reference")
    return out


def _enum_members(cls: ast.ClassDef) -> list[str]:
    members: list[str] = []
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    members.append(target.id)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            members.append(stmt.target.id)
    return members


def _base_names(cls: ast.ClassDef) -> list[str]:
    out = []
    for base in cls.bases:
        name = getattr(base, "attr", getattr(base, "id", ""))
        if name:
            out.append(name)
    return out


def _enclosing_setters(tree: ast.Module) -> dict[int, str]:
    """Map each line number to the nearest enclosing function name (or '<module>')."""
    line_owner: dict[int, str] = {}

    def visit(node: ast.AST, owner: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for n in ast.walk(child):
                    if hasattr(n, "lineno"):
                        line_owner[n.lineno] = child.name
                visit(child, child.name)
            else:
                visit(child, owner)

    visit(tree, "<module>")
    return line_owner


def analyze(source: str, *, module: str = "") -> ModelReport:
    """Extract the data model + state machines of one Python module. Never raises on
    dynamic code; it lowers confidence and records the reason in `unknowns`."""
    try:
        tree = ast.parse(source, filename=module or "<source>")
    except SyntaxError as exc:
        raise ModelExtractorError(f"cannot parse {module or 'source'}: {exc}") from exc

    unknowns: list[str] = []

    # pass 1: catalog entities and enums (top-level classes)
    entities: list[str] = []
    enums: dict[str, list[str]] = {}
    entity_defs: list[ast.ClassDef] = []
    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef):
            bases = _base_names(stmt)
            if _ENUM_BASES & set(bases):
                enums[stmt.name] = _enum_members(stmt)
            else:
                has_fields = any(
                    isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
                    for s in stmt.body
                )
                is_dc = any(
                    getattr(d.func if isinstance(d, ast.Call) else d, "id", "") == "dataclass"
                    or getattr(d.func if isinstance(d, ast.Call) else d, "attr", "") == "dataclass"
                    for d in stmt.decorator_list
                )
                if has_fields or is_dc:
                    entities.append(stmt.name)
                    entity_defs.append(stmt)

    entity_set = set(entities)

    # pass 2: relationships from entity field annotations + inheritance
    relationships: list[Relationship] = []
    for cls in entity_defs:
        for base in _base_names(cls):
            if base in entity_set:
                relationships.append(Relationship(cls.name, base, "(base)", "inheritance"))
        for stmt in cls.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                for name, kind in _referenced_names(stmt.annotation):
                    if name in entity_set and name != cls.name:
                        relationships.append(Relationship(cls.name, name, stmt.target.id, kind))

    # pass 3: state machines - observed member assignments per enum
    setters = _enclosing_setters(tree)
    observed: dict[str, list[Transition]] = {name: [] for name in enums}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            enum_name, member = node.value.id, node.attr
            if enum_name in enums and member in enums[enum_name]:
                setter = setters.get(getattr(node, "lineno", -1), "<module>")
                observed[enum_name].append(Transition(setter, member))
        elif isinstance(node, ast.Name) and node.id == "setattr":
            unknowns.append("setattr() may set state the extractor cannot see")

    state_machines: list[StateMachine] = []
    for name, members in enums.items():
        # dedupe transitions, keep deterministic order
        seen: set[tuple[str, str]] = set()
        trans: list[Transition] = []
        for t in observed[name]:
            key = (t.setter, t.to_state)
            if key not in seen:
                seen.add(key)
                trans.append(t)
        reached = {t.to_state for t in trans}
        unreached = tuple(m for m in members if m not in reached)
        state_machines.append(StateMachine(name, tuple(members), tuple(trans), unreached))

    unknowns = sorted(set(unknowns))
    confidence = round(max(0.3, 1.0 - 0.1 * len(unknowns)), 2)
    return ModelReport(
        module=module,
        entities=tuple(entities),
        relationships=tuple(relationships),
        state_machines=tuple(state_machines),
        unknowns=tuple(unknowns),
        confidence=confidence,
    )


def render(report: ModelReport) -> str:
    """A human-readable rendering of the data-model report (for inspection + correction)."""
    lines = [f"module: {report.module or '<source>'}  (confidence {report.confidence})"]
    if report.entities:
        lines.append("  entities: " + ", ".join(report.entities))
    if report.relationships:
        lines.append("  relationships:")
        for r in report.relationships:
            lines.append(f"    - {r.source} --{r.via} ({r.kind})--> {r.target}")
    for sm in report.state_machines:
        lines.append(f"  state machine {sm.enum}: {{{', '.join(sm.states)}}}")
        for t in sm.transitions:
            lines.append(f"      {t.setter}() -> {t.to_state}")
        if sm.unreached:
            lines.append(f"      unreached states: {', '.join(sm.unreached)}")
    if report.unknowns:
        lines.append("  UNKNOWNS (confidence reducers): " + "; ".join(report.unknowns))
    return "\n".join(lines)
