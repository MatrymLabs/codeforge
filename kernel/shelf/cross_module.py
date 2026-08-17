"""CARD: cross_module -- reverse-engineer cross-module symbol usage across a whole package.

Batch 6 and the capstone of the R&D Tech Lab Reverse-Engineering Lab (composes on
EXP-15/16/19): where EXP-19 sees calls WITHIN one module, this resolves symbol usage
ACROSS module boundaries via the import graph. It answers the questions a single module
cannot:

  * who uses this - for every public symbol (function/class) a module defines, which
    OTHER modules import or reference it.
  * package-wide unused public API - a public symbol no other module in the package
    imports or references (a candidate for making it private, or removing it).
  * cross-module hubs - the symbols used from the most places (change them carefully).
  * cross-module call edges - `A imports foo from B and calls it` -> edge A -> B via foo.

It never presents "unused" as proven fact. A symbol reached only through a dynamic
import, a star import, or `getattr` would look unused but is not; those are recorded as
unknowns and lower confidence. An entrypoint (a CLI, a `__main__`, a test-only helper)
is public-but-unused BY DESIGN - so the field is named a CANDIDATE list, not a verdict.

Clean-room, stdlib only (Python's own `ast`). Scope: one package's *.py modules.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

_DYNAMIC = {
    "__import__": "__import__() loads a module the analyzer cannot follow",
    "import_module": "importlib.import_module() loads a module the analyzer cannot follow",
    "getattr": "getattr() dispatch hides which symbol is used",
}


class CrossModuleError(ValueError):
    """Raised when the input is malformed."""


@dataclass(frozen=True)
class SymbolUse:
    """A public symbol and the OTHER modules that import or reference it."""

    symbol: str  # "module:name"
    defined_in: str
    kind: str  # "function" | "class"
    used_by: tuple[str, ...] = ()  # other internal modules that use it


@dataclass(frozen=True)
class CallEdge:
    """`src` module uses `symbol` defined in `dst` module."""

    src: str
    dst: str
    symbol: str


@dataclass(frozen=True)
class CrossModuleReport:
    """The validated cross-module usage report - inspectable and honest."""

    package: str
    symbols: tuple[SymbolUse, ...] = ()
    edges: tuple[CallEdge, ...] = ()
    unused_public: tuple[str, ...] = ()  # "module:name" used by no other module (candidate)
    hubs: tuple[str, ...] = ()  # most cross-module-used symbols
    externals: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 1.0


def _resolve_relative(importer: str, level: int, tail: str | None) -> str | None:
    parts = importer.split(".")
    if level > len(parts):
        return None
    base = parts[: len(parts) - level]
    if tail:
        base = base + tail.split(".")
    return ".".join(base) if base else None


def _public_defs(tree: ast.Module) -> dict[str, str]:
    """{name: kind} for public top-level functions and classes."""
    out: dict[str, str] = {}
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and not stmt.name.startswith(
            "_"
        ):
            out[stmt.name] = "function"
        elif isinstance(stmt, ast.ClassDef) and not stmt.name.startswith("_"):
            out[stmt.name] = "class"
    return out


def _flatten_attr(node: ast.expr) -> list[str] | None:
    """Flatten `a.b.c` into ['a','b','c']; None if the chain is not pure Name/Attribute."""
    parts: list[str] = []
    cur: ast.expr = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        parts.reverse()
        return parts
    return None


def _imports(
    tree: ast.Module, importer: str, internal: set[str]
) -> tuple[dict[str, tuple[str, str]], dict[str, str], list[str]]:
    """Resolve imports.

    Returns (local_name -> (source_module, original_symbol) for INTERNAL from-imports,
    local_root -> module_dotted for INTERNAL module imports, list of unknown reasons).
    """
    name_to_symbol: dict[str, tuple[str, str]] = {}
    module_alias: dict[str, str] = {}
    unknowns: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                source = _resolve_relative(importer, node.level, node.module)
                if source is None:
                    unknowns.append(f"{importer}: relative import escapes the package root")
                    continue
            else:
                source = node.module or ""
            for alias in node.names:
                if alias.name == "*":
                    unknowns.append(
                        f"{importer}: star import from {source} hides which symbols are used"
                    )
                    continue
                if source in internal:
                    local = alias.asname or alias.name
                    name_to_symbol[local] = (source, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in internal:
                    # `import pkg.util` binds root `pkg` (full-path access); `... as u` binds `u`
                    root = alias.asname or alias.name.split(".")[0]
                    module_alias[root] = alias.name if alias.asname else alias.name.split(".")[0]
    return name_to_symbol, module_alias, unknowns


def analyze_repo(  # noqa: PLR0912, PLR0915
    modules: dict[str, str], *, package: str = "", hub_count: int = 10
) -> CrossModuleReport:
    """Reverse-engineer cross-module symbol usage from {module_name: source}. Pure/testable."""
    if not isinstance(modules, dict):
        raise CrossModuleError("modules must be a dict of {module_name: source}")  # noqa: TRY003
    internal = set(modules)

    # pass 1: parse + catalog public definitions
    trees: dict[str, ast.Module] = {}
    defs: dict[str, dict[str, str]] = {}  # module -> {name: kind}
    unknowns: list[str] = []
    for name, source in sorted(modules.items()):
        try:
            trees[name] = ast.parse(source, filename=name)
        except SyntaxError as exc:
            unknowns.append(f"{name}: could not parse ({exc.msg})")
            continue
        defs[name] = _public_defs(trees[name])

    # symbol_id -> defining module + kind ; and a used_by accumulator
    defined: dict[str, tuple[str, str]] = {}
    for mod, d in defs.items():
        for nm, kind in d.items():
            defined[f"{mod}:{nm}"] = (mod, kind)
    used_by: dict[str, set[str]] = {sid: set() for sid in defined}

    edges: set[tuple[str, str, str]] = set()
    externals: set[str] = set()

    def resolve_chain(parts: list[str], module_alias: dict[str, str]) -> tuple[str, str] | None:
        """Resolve a dotted attribute chain to (internal_module, symbol), or None."""
        expanded = parts[:]
        if expanded and expanded[0] in module_alias:
            expanded = module_alias[expanded[0]].split(".") + expanded[1:]
        # longest internal-module prefix, with a symbol component after it
        for cut in range(len(expanded) - 1, 0, -1):
            candidate = ".".join(expanded[:cut])
            if candidate in internal:
                return candidate, expanded[cut]
        return None

    # pass 2: resolve each module's usage of internal symbols
    for mod, tree in trees.items():
        name_to_symbol, module_alias, mod_unknowns = _imports(tree, mod, internal)
        unknowns.extend(mod_unknowns)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id in name_to_symbol:
                    src_mod, sym = name_to_symbol[node.id]
                    sid = f"{src_mod}:{sym}"
                    if sid in defined and src_mod != mod:
                        used_by[sid].add(mod)
                        edges.add((mod, src_mod, sym))
                elif node.id in _DYNAMIC:
                    unknowns.append(f"{mod}: {_DYNAMIC[node.id]}")
            elif isinstance(node, ast.Attribute):
                if node.attr in _DYNAMIC:
                    unknowns.append(f"{mod}: {_DYNAMIC[node.attr]}")
                parts = _flatten_attr(node)
                if parts:
                    hit = resolve_chain(parts, module_alias)
                    if hit and hit[0] != mod:
                        src_mod, sym = hit
                        sid = f"{src_mod}:{sym}"
                        if sid in defined:
                            used_by[sid].add(mod)
                            edges.add((mod, src_mod, sym))
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                top = node.module.split(".")[0]
                if node.module not in internal and top not in internal:
                    externals.add(top)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if alias.name not in internal and top not in internal:
                        externals.add(top)

    symbols = tuple(
        SymbolUse(sid, defined[sid][0], defined[sid][1], tuple(sorted(used_by[sid])))
        for sid in sorted(defined)
    )
    unused_public = tuple(sid for sid in sorted(defined) if not used_by[sid])
    ranked = sorted(defined, key=lambda s: (-len(used_by[s]), s))
    hubs = tuple(s for s in ranked[:hub_count] if used_by[s])

    unknowns = sorted(set(unknowns))
    confidence = round(max(0.3, 1.0 - 0.05 * len(unknowns)), 2)
    return CrossModuleReport(
        package=package,
        symbols=symbols,
        edges=tuple(sorted((CallEdge(*e) for e in edges), key=lambda e: (e.src, e.dst, e.symbol))),
        unused_public=unused_public,
        hubs=hubs,
        externals=tuple(sorted(externals)),
        unknowns=tuple(unknowns),
        confidence=confidence,
    )


def render(report: CrossModuleReport) -> str:
    """A human-readable rendering of the cross-module usage report."""
    header = (
        f"cross-module: {report.package or '<package>'}  "
        f"({len(report.symbols)} public symbols, {len(report.edges)} usage edges, "
        f"confidence {report.confidence})"
    )
    lines = [header]
    if report.hubs:
        lines.append("  cross-module hubs (most-used):")
        used = {s.symbol: s.used_by for s in report.symbols}
        for h in report.hubs:
            lines.append(f"    - {h}  (used by {len(used.get(h, ()))} modules)")
    if report.unused_public:
        lines.append(
            f"  UNUSED-PUBLIC CANDIDATES ({len(report.unused_public)}): "
            + ", ".join(report.unused_public[:12])
        )
        if len(report.unused_public) > 12:  # noqa: PLR2004
            lines.append(f"    ... and {len(report.unused_public) - 12} more")
    else:
        lines.append("  unused-public candidates: none")
    if report.unknowns:
        lines.append("  UNKNOWNS (confidence reducers): " + "; ".join(report.unknowns[:6]))
    return "\n".join(lines)
