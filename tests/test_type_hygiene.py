"""Real consumer of the Type Smell lens (MOD-05.091) - a CI type-hygiene guard on the shelf.

The Hardware Store shelf is the reusable core other repos install, so its public surfaces must
carry complete type contracts. This runs the type-smell lens over every shelf module and asserts
zero INCOMPLETE-CONTRACT smells (UNTYPED_PUBLIC_API, PARTIAL_ANNOTATION) - the two a `mypy --strict`
gate also rejects, pinned here at the source level so a new part cannot ship a half-typed public
signature. ANY_ON_PUBLIC and INCONSISTENT_PARAM_TYPE are reported by the lens but NOT gated here:
`Any` is a legitimate, deliberate opt-out and one parameter name legitimately carries different
generic types across independent modules - neither is a defect the shelf must be free of.
"""

from __future__ import annotations

import glob
from pathlib import Path

from kernel.shelf.type_smell import analyze

_ROOT = Path(__file__).resolve().parent.parent
_SHELF = str(_ROOT / "kernel" / "shelf" / "*.py")

# Type smells that mean an INCOMPLETE public contract - the shelf must never carry these.
_INCOMPLETE = {"TYPE_SMELL.UNTYPED_PUBLIC_API", "TYPE_SMELL.PARTIAL_ANNOTATION"}


def test_shelf_public_surfaces_carry_complete_type_contracts():
    offenders = []
    for path in sorted(glob.glob(_SHELF)):  # noqa: PTH207
        for smell in analyze(Path(path).read_text(encoding="utf-8"), path=path):
            if smell.smell_id in _INCOMPLETE:
                offenders.append((Path(path).name, smell.smell_id, smell.where, smell.line))
    assert offenders == [], f"incomplete-contract type smells on the shelf: {offenders}"


def test_the_lens_actually_runs_over_the_real_shelf():
    # a guard on the guard: prove the sweep saw real modules (not an empty glob passing vacuously)
    modules = glob.glob(_SHELF)  # noqa: PTH207
    assert len(modules) >= 30
    # and prove the lens does find its non-gated smells on real code (it is not silently inert)
    total = sum(len(analyze(Path(p).read_text(encoding="utf-8"), path=p)) for p in modules)
    assert total > 0
