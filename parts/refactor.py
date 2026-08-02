"""CARD: refactor -- scope-correct, verifier-gated Python codemods (safe rename).

The consumer that makes the verifier gate real. The corpus's `generate -> apply -> verify`
spine, built as a tool: rename a local variable or parameter inside one function, then
REFUSE to emit the result unless it passes the behavioral gate.

- **generate/apply** - `scoped_rename` uses LibCST's ScopeProvider to rename ONLY the
  target binding and its uses (not a blind string replace): a global of the same name, or
  the same name in another function, is left untouched. LibCST is lossless, so
  comments/formatting/parentheses survive the transform.
- **verify** - `verified_rename` runs the renamed output through the stdlib
  `transform_verifier` sampler (always available) and, when `deep=True`, the CrossHair
  `verify_smt` deep gate. If the verdict is not PRESERVED, the transform is REFUSED
  (the original source is returned, `applied=False`, with the counterexample).

A scope-correct rename is behaviour-preserving by construction, so the gate is a safety
net: it catches a codemod bug (or a future LLM-generated transform) that changes behaviour,
exactly as the corpus prescribes - every transform, deterministic or not, passes the same
gate. A blind rename that also renamed a shadowed global would be caught as BROKEN.

Dependency posture: LibCST is the OPTIONAL `[refactor]` extra (the only lossless
scope-aware Python codemod path; stdlib `ast` is lossy). Absent, `refactor_available()` is
False and the tool fails loud with an install hint; the rest of the fleet is untouched.
`deep=True` additionally needs the `[verify]` extra (CrossHair). CI runs without either.

Security posture: verification EXECUTES the function under analysis (via the verifier).
Trusted/authorized code only - not a sandbox against malicious code.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any

from kernel.shelf.transform_verifier import Outcome, verify_transform

__all__ = [
    "RefactorError",
    "RefactorResult",
    "refactor_available",
    "scoped_rename",
    "verified_rename",
]


class RefactorError(ValueError):
    """Raised on malformed input, a missing target, a name collision, or an absent dependency."""


@dataclass(frozen=True)
class RefactorResult:
    """The frozen outcome of a verified refactor. `applied` is False on a refused transform."""

    applied: bool
    source: str  # the renamed source if applied, else the original (refused)
    func_name: str
    verdict: str  # the behavioural verdict: preserved / broken / inconclusive
    counterexample: dict[str, Any] | None = None
    notes: tuple[str, ...] = ()


def refactor_available() -> bool:
    """True when the optional LibCST dependency (the [refactor] extra) is installed."""
    return importlib.util.find_spec("libcst") is not None


def _import_libcst() -> Any:  # pragma: no cover - import glue, exercised in the [refactor] run
    """Lazy-import LibCST's parser + scope metadata. Fails loud if the extra is absent."""
    try:
        import libcst as cst  # type: ignore[import-not-found]
        from libcst.metadata import (  # type: ignore[import-not-found]
            FunctionScope,
            MetadataWrapper,
            ScopeProvider,
        )
    except ImportError as exc:  # pragma: no cover - exercised only when the extra is absent
        raise RefactorError(
            "the refactor tool needs the optional dependency: pip install 'codeforge[refactor]' "
            "(libcst). It is the only lossless scope-aware Python codemod path."
        ) from exc
    return cst, MetadataWrapper, ScopeProvider, FunctionScope


def scoped_rename(source: str, func_name: str, old: str, new: str) -> str:  # pragma: no cover
    """Rename local/param `old` to `new` inside `func_name`, and ONLY there.

    Scope-correct via LibCST's ScopeProvider: the binding and its uses are renamed by node
    identity, so a global of the same name or the same name in another function is untouched.
    Lossless: comments/formatting survive. Covered by the [refactor]-installed test run;
    marked no-cover because CI runs without LibCST (the availability + refusal paths are
    covered there).

    Raises RefactorError if LibCST is absent, `new` is not an identifier, the source does not
    parse, `func_name` is absent, `old` is not a local/param of it, or `new` already exists in
    that scope (a collision).
    """
    cst, wrapper_cls, scope_provider, func_scope = _import_libcst()
    if not new.isidentifier():
        raise RefactorError(f"new name {new!r} is not a valid identifier")
    try:
        module = cst.parse_module(source)
    except Exception as exc:
        raise RefactorError(f"source does not parse: {exc}") from exc

    wrapper = wrapper_cls(module)
    scopes = wrapper.resolve(scope_provider)
    targets: set[int] = set()
    found_func = False

    for _node, scope in scopes.items():
        if not (isinstance(scope, func_scope) and getattr(scope, "name", None) == func_name):
            continue
        found_func = True
        if list(scope[new]):
            raise RefactorError(f"{new!r} already exists in {func_name!r} (rename would collide)")
        bindings = list(scope[old])
        if not bindings:
            raise RefactorError(f"{old!r} is not a local or parameter of {func_name!r}")
        for assignment in bindings:
            node = assignment.node
            if isinstance(node, cst.Param):
                targets.add(id(node.name))
            elif isinstance(node, cst.Name):
                targets.add(id(node))
            for access in assignment.references:
                targets.add(id(access.node))
        break

    if not found_func:
        raise RefactorError(f"function {func_name!r} not found")

    class _Rename(cst.CSTTransformer):  # type: ignore[name-defined]
        def leave_Name(self, original_node: Any, updated_node: Any) -> Any:
            if id(original_node) in targets:
                return updated_node.with_changes(value=new)
            return updated_node

    return wrapper.module.visit(_Rename()).code


def verified_rename(
    source: str,
    func_name: str,
    old: str,
    new: str,
    *,
    samples: int = 200,
    deep: bool = False,
) -> RefactorResult:
    """Scope-rename `old`->`new` in `func_name`, then GATE it on behavioural equivalence.

    Applies `scoped_rename`, then verifies the result preserved behaviour with the stdlib
    sampler (and, if `deep=True`, the CrossHair deep gate). A non-PRESERVED verdict REFUSES
    the transform: the returned `RefactorResult` has `applied=False` and the ORIGINAL source,
    plus the counterexample. Raises RefactorError on the same conditions as `scoped_rename`.
    """
    new_source = scoped_rename(source, func_name, old, new)  # RefactorError if LibCST absent

    verdict = verify_transform(source, new_source, func_name, samples=samples)
    outcome, cex, notes = verdict.outcome, verdict.counterexample, list(verdict.notes)

    if deep and outcome is Outcome.PRESERVED:  # pragma: no cover - needs the [verify] extra
        from parts.verify_smt import Outcome as SmtOutcome
        from parts.verify_smt import verify_transform_smt

        smt = verify_transform_smt(source, new_source, func_name)
        notes.append(f"deep gate (crosshair): {smt.outcome.value}")
        if smt.outcome is SmtOutcome.BROKEN:
            outcome, cex = Outcome.BROKEN, smt.counterexample

    if outcome is not Outcome.PRESERVED:
        return RefactorResult(
            applied=False,
            source=source,
            func_name=func_name,
            verdict=outcome.value,
            counterexample=cex,
            notes=("refused: the rename did not preserve behaviour", *notes),
        )
    return RefactorResult(
        applied=True,
        source=new_source,
        func_name=func_name,
        verdict=outcome.value,
        notes=tuple(notes),
    )
