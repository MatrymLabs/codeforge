"""CARD: verify_smt -- a CrossHair-backed behavioral-equivalence verifier (the deep gate).

The proof-grade companion to the stdlib `transform_verifier` shelf part (which gates a code
transform by SAMPLING - running both versions on a hostile input battery). Sampling is fast
and dependency-free, but it can only catch a divergence at an input it happens to draw; a
divergence at a rare value (x == 987654321) slips through as a false PRESERVED. This module
drives CrossHair's `diff_behavior`, which explores inputs SYMBOLICALLY (concolic execution
over an SMT solver) and reports a counterexample where two functions diverge - finding
needles the sampler cannot. Proven in the Track-T proving ground (T-EXP-08 / CAND-06): it
caught a rare-input divergence the sampler called PRESERVED even at 5000 samples.

It is NOT a shelf part: CrossHair is a heavy OPTIONAL dependency (the `[verify]` extra), so
this lives outside `kernel/shelf/` (the poured Hardware Store stays portable and zero-dep).
CrossHair is lazy-imported; if it is absent, this fails loud with a clear install hint and
nothing else in the fleet is affected - the stdlib sampler remains the always-available
default. The intended consumer is the roadmapped refactor tool: run the fast sampler on
every transform, and this deep gate on the ones that matter.

Honesty contract (CrossHair's own, verbatim): a found counterexample IS proof the behavior
changed; the ABSENCE of one raises confidence but is NOT a proof (bounded symbolic search;
needs type annotations, deterministic CPython, small functions). A PRESERVED here is a
STRONGER signal than the sampler's, not a certificate.

Security posture: like the sampler, this EXECUTES the functions under analysis in-process.
Trusted/authorized code only - not a sandbox against malicious code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

__all__ = ["Outcome", "SmtVerdict", "VerifySmtError", "verify_transform_smt"]

CAVEAT = (
    "CrossHair diff_behavior: a counterexample IS proof of change; its ABSENCE raises "
    "confidence but is NOT a proof (bounded symbolic search). Needs type annotations, "
    "deterministic CPython, small functions."
)


class VerifySmtError(ValueError):
    """Raised when the target is malformed or the optional CrossHair dependency is absent."""


class Outcome(StrEnum):
    """The verdict of a symbolic verification."""

    PRESERVED = "preserved"  # no divergence found by symbolic search (strong signal)
    BROKEN = "broken"  # a symbolic counterexample proves the behavior changed
    INCONCLUSIVE = "inconclusive"  # CrossHair could not decide (no annotations / gave up)


@dataclass(frozen=True)
class SmtVerdict:
    """The frozen result of a symbolic verification. `broken` is the only proof."""

    outcome: Outcome
    func_name: str
    backend: str = "crosshair"
    counterexample: dict[str, Any] | None = None
    notes: tuple[str, ...] = ()
    caveat: str = CAVEAT

    @property
    def preserved(self) -> bool:
        return self.outcome is Outcome.PRESERVED


def _load_function(src: str, func_name: str, tag: str) -> Any:
    """Exec a source string in a fresh namespace and return the named function (trusted code)."""
    namespace: dict[str, Any] = {}
    try:
        exec(compile(src, f"<{tag}>", "exec"), namespace)  # noqa: S102  # nosec B102
    except SyntaxError as exc:
        raise VerifySmtError(f"{tag} source does not parse: {exc}") from exc
    fn = namespace.get(func_name)
    if not callable(fn):
        raise VerifySmtError(f"{tag} has no callable named {func_name!r}")
    return fn


def _import_crosshair() -> Any:
    """Lazy-import CrossHair (opcode patches + the diff API). Fails loud if it is absent."""
    try:
        import crosshair.core_and_libs  # type: ignore[import-not-found]  # noqa: F401 - loads opcode patches (REQUIRED first)
        from crosshair.diff_behavior import diff_behavior  # type: ignore[import-not-found]
        from crosshair.fnutil import FunctionInfo  # type: ignore[import-not-found]
        from crosshair.options import DEFAULT_OPTIONS  # type: ignore[import-not-found]
    except ImportError as exc:
        raise VerifySmtError(
            "the deep verifier needs the optional dependency: pip install 'codeforge[verify]' "
            "(crosshair-tool). The stdlib sampler (transform_verifier) needs nothing."
        ) from exc
    return diff_behavior, FunctionInfo, DEFAULT_OPTIONS  # pragma: no cover - only with the extra


def verify_transform_smt(
    before_src: str,
    after_src: str,
    func_name: str,
    *,
    max_iterations: int = 40,
    timeout: float = 10.0,
) -> SmtVerdict:
    """Symbolically decide whether `after_src` preserved the behavior of `func_name`.

    Fails loud (VerifySmtError) if BEFORE/AFTER do not parse, lack the function, or CrossHair
    is not installed. Returns BROKEN + a symbolic counterexample, PRESERVED (a strong signal,
    not a proof), or INCONCLUSIVE if CrossHair could not decide.
    """
    before_fn = _load_function(before_src, func_name, "before")
    after_fn = _load_function(after_src, func_name, "after")
    diff_behavior, function_info, default_options = _import_crosshair()

    # Below here CrossHair is present; exercised by the skip-unless-installed tests, not CI.
    opts = default_options.overlay(  # pragma: no cover
        max_iterations=max_iterations, per_condition_timeout=timeout
    )
    result = diff_behavior(  # pragma: no cover
        function_info.from_fn(before_fn), function_info.from_fn(after_fn), opts
    )
    if isinstance(result, str):  # pragma: no cover
        return SmtVerdict(
            outcome=Outcome.INCONCLUSIVE,
            func_name=func_name,
            notes=(f"crosshair could not decide: {result}",),
        )
    if result:  # pragma: no cover
        diff = result[0]
        return SmtVerdict(
            outcome=Outcome.BROKEN,
            func_name=func_name,
            counterexample={
                "args": dict(diff.args),
                "before": diff.result1.return_repr,
                "after": diff.result2.return_repr,
            },
            notes=("a symbolic counterexample proves the transform changed behavior",),
        )
    return SmtVerdict(  # pragma: no cover
        outcome=Outcome.PRESERVED,
        func_name=func_name,
        notes=("no divergence found by bounded symbolic search",),
    )
