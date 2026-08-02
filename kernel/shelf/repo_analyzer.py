"""CARD: repo_analyzer -- reverse-engineer a Python package into a validated architecture model.

Batch 2 of the R&D Tech Lab Reverse-Engineering Lab (composes on EXP-15's
per-module source_analyzer): ingest a whole package, resolve its INTERNAL import
graph, and infer the architecture the code actually has - the dependency edges,
the import cycles, the layering, the hub modules (high fan-in), the entrypoints
(nothing imports them), and the leaves (they import nothing internal).

It never presents the inferred architecture as proven fact. Every model carries a
confidence and an explicit list of what reduced it (dynamic imports the analyzer
cannot follow, unparseable modules, unresolved edges). Import cycles are reported,
not hidden - a cycle is a real architectural finding, not an error.

Clean-room, stdlib only (Python's own `ast`). Scope: one package's *.py modules.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

# dynamic-import constructs the analyzer cannot statically follow (edges it must admit it missed)
_DYNAMIC_IMPORT = {
    "__import__": "__import__() loads a module the analyzer cannot follow",
    "import_module": "importlib.import_module() loads a module the analyzer cannot follow",
}


class RepoAnalyzerError(ValueError):
    """Raised when the input is malformed (not when a single module fails to parse)."""


@dataclass(frozen=True)
class Node:
    """One internal module and its position in the graph."""

    module: str  # dotted internal name, e.g. "pkg.sub.thing"
    fan_in: int = 0  # how many internal modules import it (a hub if high)
    fan_out: int = 0  # how many internal modules it imports
    parse_ok: bool = True  # False if the module could not be parsed (still a node)


@dataclass(frozen=True)
class Edge:
    """A resolved internal dependency: `src` imports `dst`."""

    src: str
    dst: str


@dataclass(frozen=True)
class RepoModel:
    """The validated architecture model of one package - inspectable and correctable."""

    package: str
    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()
    cycles: tuple[tuple[str, ...], ...] = ()  # each a strongly-connected group (>1 member)
    entrypoints: tuple[str, ...] = ()  # nothing internal imports them (fan_in == 0)
    leaves: tuple[str, ...] = ()  # import nothing internal (fan_out == 0)
    hubs: tuple[str, ...] = ()  # highest fan-in (most depended-upon)
    externals: tuple[str, ...] = ()  # top-level packages imported but not internal
    unknowns: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 1.0


def _resolve_relative(importer: str, level: int, tail: str | None) -> str | None:
    """Resolve `from ..x import y` in `importer` to a dotted module. None if it escapes the top."""
    parts = importer.split(".")
    # a module `pkg.a` at level 1 is relative to package `pkg`; drop `level` trailing names
    if level > len(parts):
        return None
    base = parts[: len(parts) - level]
    if tail:
        base = base + tail.split(".")
    return ".".join(base) if base else None


def _imported_modules(source: str, importer: str) -> tuple[list[str], list[str]]:
    """(candidate dotted targets, unknown reasons) for one module's imports.

    Targets are the fully-dotted module names an import *could* refer to; the caller
    keeps only those that match a known internal module.
    """
    targets: list[str] = []
    unknowns: list[str] = []
    tree = ast.parse(source, filename=importer)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import
                resolved = _resolve_relative(importer, node.level, node.module)
                if resolved is None:
                    unknowns.append(f"{importer}: relative import escapes the package root")
                    continue
                # `from .pkg import a, b` -> module is `resolved`; each name may be a submodule
                targets.append(resolved)
                targets.extend(
                    f"{resolved}.{alias.name}" for alias in node.names if alias.name != "*"
                )
                if any(a.name == "*" for a in node.names):
                    unknowns.append(f"{importer}: star import hides which names are used")
            elif node.module:
                targets.append(node.module)
                targets.extend(
                    f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*"
                )
        elif isinstance(node, ast.Name) and node.id in _DYNAMIC_IMPORT:
            unknowns.append(f"{importer}: {_DYNAMIC_IMPORT[node.id]}")
        elif isinstance(node, ast.Attribute) and node.attr in _DYNAMIC_IMPORT:
            unknowns.append(f"{importer}: {_DYNAMIC_IMPORT[node.attr]}")
    return targets, unknowns


def _tarjan_scc(adj: dict[str, set[str]]) -> list[tuple[str, ...]]:
    """Strongly-connected components (Tarjan). Returns only groups with a real cycle."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    counter = [0]
    out: list[tuple[str, ...]] = []

    def strong(v: str) -> None:
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in adj.get(v, ()):  # iterate deterministically below via sorted adjacency
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            # a component is a cycle if it has >1 node, or a node that imports itself
            if len(comp) > 1 or v in adj.get(v, set()):
                out.append(tuple(sorted(comp)))

    for v in sorted(adj):
        if v not in index:
            strong(v)
    return out


def analyze_repo(modules: dict[str, str], *, package: str = "", hub_count: int = 5) -> RepoModel:
    """Reverse-engineer an architecture model from {module_name: source}. Pure and testable.

    `modules` maps a dotted internal module name to its source text. Nothing else is
    treated as internal; any import that does not resolve to a key is external.
    """
    if not isinstance(modules, dict):
        raise RepoAnalyzerError("modules must be a dict of {module_name: source}")
    internal = set(modules)
    edges: set[tuple[str, str]] = set()
    externals: set[str] = set()
    unknowns: list[str] = []
    parse_ok: dict[str, bool] = {}

    for name, source in sorted(modules.items()):
        try:
            targets, mod_unknowns = _imported_modules(source, name)
        except SyntaxError as exc:
            parse_ok[name] = False
            unknowns.append(f"{name}: could not parse ({exc.msg})")
            continue
        parse_ok[name] = True
        unknowns.extend(mod_unknowns)
        for target in targets:
            if target in internal:
                if target != name:
                    edges.add((name, target))
            else:
                top = target.split(".")[0]
                if top not in internal and not any(
                    target == m or target.startswith(m + ".") for m in internal
                ):
                    externals.add(top)

    adj: dict[str, set[str]] = {m: set() for m in internal}
    for src, dst in edges:
        adj[src].add(dst)
    fan_out = {m: len(adj[m]) for m in internal}
    fan_in = {m: 0 for m in internal}
    for _src, dst in edges:
        fan_in[dst] += 1

    nodes = tuple(Node(m, fan_in[m], fan_out[m], parse_ok.get(m, True)) for m in sorted(internal))
    cycles = tuple(_tarjan_scc(adj))
    entrypoints = tuple(sorted(m for m in internal if fan_in[m] == 0))
    leaves = tuple(sorted(m for m in internal if fan_out[m] == 0))
    ranked_hubs = sorted(internal, key=lambda m: (-fan_in[m], m))
    hubs = tuple(m for m in ranked_hubs[:hub_count] if fan_in[m] > 0)

    unknowns = sorted(set(unknowns))
    # confidence: dock for cycles (architecture is tangled) + each distinct unknown; floor 0.3
    penalty = 0.05 * len(cycles) + 0.05 * len(unknowns)
    confidence = round(max(0.3, 1.0 - penalty), 2)
    return RepoModel(
        package=package,
        nodes=nodes,
        edges=tuple(sorted((Edge(s, d) for s, d in edges), key=lambda e: (e.src, e.dst))),
        cycles=cycles,
        entrypoints=entrypoints,
        leaves=leaves,
        hubs=hubs,
        externals=tuple(sorted(externals)),
        unknowns=tuple(unknowns),
        confidence=confidence,
    )


def render(model: RepoModel) -> str:
    """A human-readable rendering of the architecture model (for inspection + correction)."""
    header = (
        f"package: {model.package or '<package>'}  "
        f"({len(model.nodes)} modules, {len(model.edges)} edges, confidence {model.confidence})"
    )
    lines = [header]
    if model.hubs:
        lines.append("  hubs (most depended-upon): " + ", ".join(model.hubs))
    if model.entrypoints:
        lines.append(
            f"  entrypoints ({len(model.entrypoints)}): " + ", ".join(model.entrypoints[:8])
        )
    if model.leaves:
        lines.append(f"  leaves ({len(model.leaves)}): " + ", ".join(model.leaves[:8]))
    if model.externals:
        lines.append("  external deps: " + ", ".join(model.externals))
    if model.cycles:
        lines.append(f"  IMPORT CYCLES ({len(model.cycles)}):")
        for cyc in model.cycles:
            lines.append("    - " + " <-> ".join(cyc))
    else:
        lines.append("  import cycles: none (acyclic)")
    if model.unknowns:
        lines.append("  UNKNOWNS (confidence reducers): " + "; ".join(model.unknowns))
    return "\n".join(lines)
