"""CARD: content_address -- address code by the hash of its normalized AST (Unison-inspired).

The first rung of the R&D Synthesis / Parts-Factory Lab, and the top clean-room build from
the "Verifier-Guided Frontiers" survey ("content-addressed code ... the single cheapest
high-leverage architectural decision available"). It gives CodeForge's "parts factory" its
identity model: a definition is named by the SHA-256 of its normalized syntax tree, not by
a label. Two definitions that are structurally the same get the same address; renaming the
binding is free (the address does not change); a repository of parts can dedup and detect
clones by hash alone.

Two normalizations, both honest about what they preserve:
  * rename_binding (default on) - the top-level def/class NAME is normalized out, so
    `def foo(): return 1` and `def bar(): return 1` share an address (rename-invariance).
  * normalize_locals (opt-in) - parameters and locally-bound names are alpha-renamed per
    function scope, so structurally-identical code with different local names collides
    (clone detection). It deliberately does NOT touch attributes, globals, or call targets.

Honesty (the survey's throughline): content-addressing is a STRUCTURAL check, not a
semantic one. Two different algorithms that compute the same result hash differently, and
two structurally-identical snippets that read different globals are NOT proven equivalent.
Structural identity is a fast, exact filter; semantic equivalence needs a verifier
(CrossHair/Z3), which is a separate, dependency-bearing rung. Never trust a transformation
on a hash match alone.

Clean-room, stdlib only (`ast`, `hashlib`).
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass


class ContentAddressError(ValueError):
    """Raised when the source cannot be parsed."""


class _LocalRenamer(ast.NodeTransformer):
    """Alpha-rename parameters + locally-bound names, per function scope, to _v0.._vN.

    Conservative by design: it only renames names that are BOUND in the current function
    (its parameters, its assignment/for/with/comprehension targets). It never renames
    attribute accesses, and it leaves any name not bound in the current scope (a global, a
    call to another function) exactly as written.
    """

    def __init__(self) -> None:
        self._scopes: list[dict[str, str]] = []

    def _bound_names(self, func: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, str]:
        names: list[str] = []
        seen: set[str] = set()

        def add(name: str) -> None:
            if name not in seen:
                seen.add(name)
                names.append(name)

        a = func.args
        for arg in (*a.posonlyargs, *a.args, *a.kwonlyargs):
            add(arg.arg)
        if a.vararg:
            add(a.vararg.arg)
        if a.kwarg:
            add(a.kwarg.arg)
        for node in ast.walk(func):
            if node is func:
                continue
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                add(node.id)
            elif isinstance(node, ast.arg):
                add(node.arg)
        return {name: f"_v{i}" for i, name in enumerate(names)}

    def _visit_function(self, func: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.AST:
        self._scopes.append(self._bound_names(func))
        self.generic_visit(func)
        self._scopes.pop()
        return func

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return self._visit_function(node)

    def visit_Name(self, node: ast.Name) -> ast.AST:
        for scope in reversed(self._scopes):
            if node.id in scope:
                return ast.copy_location(ast.Name(id=scope[node.id], ctx=node.ctx), node)
        return node

    def visit_arg(self, node: ast.arg) -> ast.AST:
        for scope in reversed(self._scopes):
            if node.arg in scope:
                node.arg = scope[node.arg]
                break
        node.annotation = None  # a type annotation is not part of the runtime structure
        return node


def _strip_binding_name(tree: ast.Module) -> None:
    """Normalize the name of a single top-level def/class to '_' (rename-invariance)."""
    if len(tree.body) == 1 and isinstance(
        tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    ):
        tree.body[0].name = "_"


def canonicalize(
    source: str,
    *,
    rename_binding: bool = True,
    normalize_locals: bool = False,
) -> str:
    """Return the canonical AST serialization used for addressing (formatting/comments gone)."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ContentAddressError(f"cannot parse source: {exc}") from exc
    if rename_binding:
        _strip_binding_name(tree)
    if normalize_locals:
        tree = _LocalRenamer().visit(tree)
        ast.fix_missing_locations(tree)
    return ast.dump(tree, annotate_fields=True, include_attributes=False)


def content_hash(
    source: str,
    *,
    rename_binding: bool = True,
    normalize_locals: bool = False,
) -> str:
    """The content address: SHA-256 of the canonical AST. Same structure -> same address."""
    canon = canonicalize(source, rename_binding=rename_binding, normalize_locals=normalize_locals)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Definition:
    """A stored definition: its label, its source, and its content address."""

    name: str
    source: str
    digest: str

    @property
    def short(self) -> str:
        return self.digest[:12]


class Store:
    """A content-addressed store of definitions - dedup and clone detection by hash."""

    def __init__(self, *, normalize_locals: bool = False) -> None:
        self._normalize_locals = normalize_locals
        self._by_name: dict[str, Definition] = {}
        self._by_digest: dict[str, list[str]] = {}

    def add(self, name: str, source: str) -> Definition:
        """Hash `source` and record it under `name`. Returns the Definition."""
        digest = content_hash(source, normalize_locals=self._normalize_locals)
        definition = Definition(name=name, source=source, digest=digest)
        self._by_name[name] = definition
        self._by_digest.setdefault(digest, [])
        if name not in self._by_digest[digest]:
            self._by_digest[digest].append(name)
        return definition

    def digest_of(self, name: str) -> str | None:
        d = self._by_name.get(name)
        return d.digest if d else None

    def is_known(self, source: str) -> bool:
        """True if a structurally-identical definition is already stored."""
        return content_hash(source, normalize_locals=self._normalize_locals) in self._by_digest

    def names_for(self, digest: str) -> tuple[str, ...]:
        return tuple(self._by_digest.get(digest, ()))

    def clones(self) -> tuple[tuple[str, ...], ...]:
        """Groups of names that share a content address (structural duplicates)."""
        return tuple(tuple(names) for names in self._by_digest.values() if len(names) > 1)

    def unique_count(self) -> int:
        """How many distinct content addresses are stored (deduped part count)."""
        return len(self._by_digest)

    def __len__(self) -> int:
        return len(self._by_name)


def render_store(store: Store) -> str:
    """A human-readable summary of a content-addressed store."""
    header = (
        f"content-addressed store: {len(store)} definitions, "
        f"{store.unique_count()} unique addresses"
    )
    lines = [header]
    clones = store.clones()
    if clones:
        lines.append(f"  clone groups ({len(clones)}):")
        for group in clones:
            lines.append("    - " + ", ".join(group))
    else:
        lines.append("  no clones (every definition is structurally unique)")
    return "\n".join(lines)
