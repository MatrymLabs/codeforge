"""CARD: transform_verifier -- gate a code transform by proving it preserved behavior.

The second rung of the R&D Synthesis / Parts-Factory Lab, from the "CodeForge Pipeline &
MVP: Ingest -> IR -> Re-emit, Verifier-Gated Transforms" design corpus. That corpus's
correctness spine is `generate -> apply -> verify`: a transform (a codemod, a refactor,
or an LLM edit) is accepted ONLY if the output still parses AND still behaves the same.
EXP-27 content_address already gives the fleet the STRUCTURAL half (address code by the
hash of its normalized AST); its own docstring named the missing half out loud - "semantic
equivalence needs a verifier (CrossHair/Z3) ... a separate rung. Never trust a
transformation on a hash match alone." This rung is that verifier, built clean-room.

`verify_transform(before_src, after_src, func_name, ...) -> Verdict` runs two gates:
  * Gate PARSE (structural): the transformed source must still parse. A codemod that emits
    broken Python is REJECTED immediately (cheap, exact).
  * Gate BEHAVIOR (differential): the named function is run under both versions on a
    battery of generated inputs (typed from annotations, else a hostile default battery);
    diverging output or a diverging exception is a COUNTEREXAMPLE that rejects the
    transform. This is a stdlib stand-in for CrossHair's `diffbehavior`.

Honesty contract (the load-bearing caveat, taken verbatim from the corpus and CrossHair):
this is SAMPLING, NOT A PROOF. The absence of a counterexample does not guarantee the two
functions are equivalent - it raises confidence, it does not certify. A found
counterexample IS a proof the transform changed behavior. So: BROKEN is a verdict;
PRESERVED is a strong signal; INCONCLUSIVE is honest about what could not be checked
(non-deterministic code, side effects, functions that never terminate).

Scope (clean-room, stdlib only: `inspect`, `random`, builtin `compile`/`exec`): the round-trip
identity gate (parse.code == src) and the scope-correct LibCST codemod in the corpus need
LibCST/CrossHair, which are NOT admitted fleet dependencies (frameless-Python) - that is a
Josh-gated technology-admission decision, logged on the watchlist, not taken here. This
rung proves the verifier IDEA with no new dependency.

Security posture: differential testing EXECUTES the functions in-process with full
builtins, exactly like running their test suite. Trusted/authorized code only - this is
NOT a sandbox against malicious code. The intended use is checking that a transform of
YOUR OWN (already-trusted) code preserved its behavior.
"""

from __future__ import annotations

import inspect
import math
import random
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

__all__ = [
    "Outcome",
    "TransformVerifierError",
    "Verdict",
    "verify_transform",
]

CAVEAT = (
    "SAMPLING, not a proof. Absence of a counterexample raises confidence but does not "
    "certify equivalence (CrossHair's own caveat); a found counterexample IS proof the "
    "behavior changed. Deterministic, terminating, side-effect-free functions only."
)


class TransformVerifierError(ValueError):
    """Raised on malformed input: unparsable BEFORE source, or a missing target function."""


class Outcome(StrEnum):
    """The verdict of a transform verification."""

    PRESERVED = "preserved"  # no divergence found over the sample battery (strong signal)
    BROKEN = "broken"  # a counterexample (or a syntax error) proves behavior changed
    INCONCLUSIVE = "inconclusive"  # could not be checked (non-deterministic / uncallable)


@dataclass(frozen=True)
class Verdict:
    """The frozen result of a verification. `broken` is the only proof; the rest is honest."""

    outcome: Outcome
    func_name: str
    samples_run: int
    parses: bool
    counterexample: dict[str, Any] | None = None
    notes: tuple[str, ...] = ()
    caveat: str = CAVEAT

    @property
    def preserved(self) -> bool:
        return self.outcome is Outcome.PRESERVED


# --------------------------------------------------------------------------------------
# Input battery -- hostile by default (mixed case, symbols, unicode, edges, zero)
# --------------------------------------------------------------------------------------

_INT_BATTERY: tuple[int, ...] = (0, 1, -1, 2, -2, 7, -7, 100, -100, 2**31, -(2**31))
_FLOAT_BATTERY: tuple[float, ...] = (0.0, 1.5, -1.5, 0.1, -0.1, math.inf, -math.inf, math.nan)
_STR_BATTERY: tuple[str, ...] = ("", "a", "Z", "Pass", "pass", "  ", "0", "!@#", "naïve", "日本語")
_BOOL_BATTERY: tuple[bool, ...] = (True, False)
_LIST_BATTERY: tuple[list[int], ...] = ([], [1], [1, 2, 3], [-1, 0, 1], [5, 5, 5])
# The default battery for a parameter with no usable annotation: a mix that exercises the
# common failure edges (zero, negatives, empties, unicode, near-miss strings).
_DEFAULT_BATTERY: tuple[Any, ...] = (
    0,
    1,
    -1,
    7,
    "",
    "a",
    "Pass",
    "pass",
    [],
    [1, 2, 3],
    True,
    False,
)

_ANNOTATION_BATTERIES: dict[type, tuple[Any, ...]] = {
    int: _INT_BATTERY,
    float: _FLOAT_BATTERY,
    str: _STR_BATTERY,
    bool: _BOOL_BATTERY,
    list: _LIST_BATTERY,
}


def _battery_for(param: inspect.Parameter) -> tuple[Any, ...]:
    ann = param.annotation
    if isinstance(ann, type) and ann in _ANNOTATION_BATTERIES:
        return _ANNOTATION_BATTERIES[ann]
    return _DEFAULT_BATTERY


def _load_function(src: str, func_name: str, tag: str) -> Any:
    """Exec a source string in a fresh namespace and return the named function.

    Trusted code only (full builtins in scope). Raises TransformVerifierError on a missing
    function; a SyntaxError in `before` is the caller's problem and also raises."""
    namespace: dict[str, Any] = {}
    try:
        # The parse+load gate executes AUTHORIZED code only, like running its test suite
        # (see the module security posture). Not a sandbox against malicious code.
        exec(compile(src, f"<{tag}>", "exec"), namespace)  # noqa: S102  # nosec B102
    except SyntaxError as exc:
        raise TransformVerifierError(f"{tag} source does not parse: {exc}") from exc
    fn = namespace.get(func_name)
    if not callable(fn):
        raise TransformVerifierError(f"{tag} has no callable named {func_name!r}")
    return fn


def _call(fn: Any, args: tuple[Any, ...]) -> tuple[str, Any]:
    """Run fn(*args), classifying the result as ('return', value) or ('raise', exc_type)."""
    try:
        return ("return", fn(*args))
    except Exception as exc:  # noqa: BLE001 - differential testing: any exception is a signal
        return ("raise", type(exc).__name__)


def _same(a: tuple[str, Any], b: tuple[str, Any]) -> bool:
    """Behavioral sameness: same return value (type-sensitive), or the same exception type."""
    kind_a, val_a = a
    kind_b, val_b = b
    if kind_a != kind_b:
        return False
    if kind_a == "raise":
        return bool(val_a == val_b)
    if type(val_a) is not type(val_b):
        return False
    try:
        # repr is the stable fallback for NaN and quirky __eq__ (nan != nan, but reprs match).
        return bool(val_a == val_b) or repr(val_a) == repr(val_b)
    except Exception:  # noqa: BLE001 - an exotic __eq__ that raises: decide by repr identity
        return repr(val_a) == repr(val_b)


def verify_transform(
    before_src: str,
    after_src: str,
    func_name: str,
    *,
    samples: int = 200,
    seed: int = 1729,
) -> Verdict:
    """Decide whether `after_src` preserved the behavior of `func_name` from `before_src`.

    Inputs:
      before_src / after_src: full Python source strings (the pre- and post-transform code).
      func_name: the function to compare (must exist and be callable in both).
      samples: how many random argument combinations to try (default 200).
      seed: RNG seed for reproducible input generation (default 1729).

    Fails loud: TransformVerifierError if BEFORE does not parse or lacks the function.
    A SyntaxError or a missing function in AFTER is a BROKEN verdict, not an exception
    (that is precisely the transform failing).
    """
    if samples <= 0:
        raise TransformVerifierError(f"samples must be >= 1, got {samples}")

    # Gate PARSE + load BEFORE (BEFORE is the trusted baseline; if it is broken, refuse).
    before_fn = _load_function(before_src, func_name, "before")

    # Gate PARSE for AFTER: a broken transform is a verdict, not an error.
    try:
        after_fn = _load_function(after_src, func_name, "after")
    except TransformVerifierError as exc:
        return Verdict(
            outcome=Outcome.BROKEN,
            func_name=func_name,
            samples_run=0,
            parses="does not parse" not in str(exc),
            counterexample={"reason": str(exc)},
            notes=("AFTER failed the parse/load gate",),
        )

    sig = inspect.signature(before_fn)
    params = [
        p for p in sig.parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    batteries = [_battery_for(p) for p in params]
    # Deterministic, reproducible input generation for the battery; NOT cryptographic.
    rng = random.Random(seed)  # noqa: S311  # nosec B311
    notes: list[str] = []

    ran = 0
    for _ in range(samples):
        args = tuple(rng.choice(battery) for battery in batteries)

        # Determinism guard: BEFORE must agree with itself, or the sample is not usable.
        base = _call(before_fn, args)
        if not _same(base, _call(before_fn, args)):
            notes.append("non-deterministic BEFORE detected; behavioral gate is unreliable")
            return Verdict(
                outcome=Outcome.INCONCLUSIVE,
                func_name=func_name,
                samples_run=ran,
                parses=True,
                notes=tuple(dict.fromkeys(notes)),
            )

        ran += 1
        got = _call(after_fn, args)
        if not _same(base, got):
            return Verdict(
                outcome=Outcome.BROKEN,
                func_name=func_name,
                samples_run=ran,
                parses=True,
                counterexample={
                    "args": args,
                    "before": {"kind": base[0], "result": repr(base[1])},
                    "after": {"kind": got[0], "result": repr(got[1])},
                },
                notes=("a counterexample proves the transform changed behavior",),
            )

    if not params:
        notes.append("function takes no positional args; behavioral coverage is a single call")

    return Verdict(
        outcome=Outcome.PRESERVED,
        func_name=func_name,
        samples_run=ran,
        parses=True,
        notes=tuple(dict.fromkeys(notes)),
    )


def render(verdict: Verdict) -> str:
    """One-screen human summary, caveat always attached."""
    lines = [
        (
            f"transform verdict: {verdict.outcome.value.upper()}  "
            f"(fn {verdict.func_name!r}, {verdict.samples_run} samples)"
        ),
    ]
    if verdict.counterexample is not None:
        lines.append(f"  counterexample: {verdict.counterexample}")
    for note in verdict.notes:
        lines.append(f"  note: {note}")
    lines.append(f"  caveat: {verdict.caveat}")
    return "\n".join(lines)
