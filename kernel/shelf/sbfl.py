"""CARD: sbfl -- spectrum-based fault localization: rank suspicious lines from test coverage.

The first rung of the R&D Debugging Lab (from the "Automating Debugging, Fixing,
Optimization" research brief). Given which program elements each test covered and whether
each test passed or failed, rank the elements by how SUSPICIOUS they are of causing the
failures - the classic Tarantula / Ochiai / DStar / Jaccard / Op2 formulas over a test
spectrum.

SUGGEST-ONLY, by design and by evidence. The load-bearing caveat (Pearson et al., ICSE
2017): rankings derived from artificial faults do NOT transfer to real faults - 40% of
prior artificial-fault results reversed on 310 real faults. So this produces a HINT for a
human to investigate, never a verdict. Every report says so.

Clean-room, stdlib only. The coverage/outcome spectrum is INJECTED (a seam), so tests
never run a real suite - they hand in the spectrum directly, exactly as the fleet's other
boundaries are mocked.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

CAVEAT = (
    "SUGGEST-ONLY hint, not a verdict. Real-fault localization accuracy is far below "
    "artificial-fault studies (Pearson et al., ICSE 2017: 40% of results reversed on real "
    "faults). Investigate the top-ranked elements; do not treat rank as proof of the bug."
)

_FORMULAS = ("ochiai", "tarantula", "dstar", "jaccard", "op2")


class SbflError(ValueError):
    """Raised on malformed input (unknown formula, or an outcome without coverage)."""


@dataclass(frozen=True)
class Suspicion:
    """One program element and its computed suspiciousness."""

    element: str  # e.g. "parts/foo.py:42"
    score: float
    ef: int  # failing tests that executed it
    ep: int  # passing tests that executed it


@dataclass(frozen=True)
class Localization:
    """The ranked fault-localization report - a hint, never a verdict."""

    formula: str
    ranking: tuple[Suspicion, ...] = ()  # descending score; ties broken by element name
    total_failed: int = 0
    total_passed: int = 0
    caveat: str = CAVEAT
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def prime_suspects(self) -> tuple[str, ...]:
        """The elements sharing the top score (all equally suspicious - investigate together)."""
        if not self.ranking:
            return ()
        top = self.ranking[0].score
        if top <= 0.0:
            return ()
        return tuple(s.element for s in self.ranking if s.score == top)


def _score(formula: str, ef: int, ep: int, total_failed: int, total_passed: int) -> float:
    nf = total_failed - ef  # failing tests that did NOT execute it
    if formula == "tarantula":
        if total_failed == 0:
            return 0.0
        fail_ratio = ef / total_failed
        pass_ratio = ep / total_passed if total_passed else 0.0
        denom = fail_ratio + pass_ratio
        return fail_ratio / denom if denom else 0.0
    if formula == "ochiai":
        denom = math.sqrt(total_failed * (ef + ep))
        return ef / denom if denom else 0.0
    if formula == "dstar":  # D* with * = 2
        denom = ep + nf
        return (ef * ef) / denom if denom else float(ef * ef)  # undefined denom -> raw numerator
    if formula == "jaccard":
        denom = total_failed + ep
        return ef / denom if denom else 0.0
    if formula == "op2":
        return ef - ep / (total_passed + 1)
    raise SbflError(f"unknown formula {formula!r}; choose from {_FORMULAS}")  # noqa: TRY003


def localize(
    coverage: dict[str, set[str]],
    outcomes: dict[str, bool],
    *,
    formula: str = "ochiai",
) -> Localization:
    """Rank program elements by suspiciousness from a test spectrum.

    coverage: {test_name: set of elements it executed}
    outcomes: {test_name: True if the test PASSED, False if it FAILED}
    formula:  one of ochiai (default) / tarantula / dstar / jaccard / op2.

    Elements executed by no failing test score 0 (they cannot be the fault by this method).
    """
    if formula not in _FORMULAS:
        raise SbflError(f"unknown formula {formula!r}; choose from {_FORMULAS}")  # noqa: TRY003
    missing = set(coverage) - set(outcomes)
    if missing:
        raise SbflError(f"coverage without an outcome for tests: {sorted(missing)}")  # noqa: TRY003

    total_failed = sum(1 for t, passed in outcomes.items() if not passed)
    total_passed = sum(1 for t, passed in outcomes.items() if passed)

    notes: list[str] = []
    if total_failed == 0:
        notes.append("no failing tests: nothing to localize (need at least one failure)")

    # tally ef/ep per element over the tests that actually have coverage recorded
    ef: dict[str, int] = {}
    ep: dict[str, int] = {}
    for test, elements in coverage.items():
        passed = outcomes[test]
        for el in elements:
            if passed:
                ep[el] = ep.get(el, 0) + 1
            else:
                ef[el] = ef.get(el, 0) + 1

    elements = set(ef) | set(ep)
    suspicions = [
        Suspicion(
            element=el,
            score=round(
                _score(formula, ef.get(el, 0), ep.get(el, 0), total_failed, total_passed), 6
            ),
            ef=ef.get(el, 0),
            ep=ep.get(el, 0),
        )
        for el in elements
    ]
    # descending by score, then ascending by element name for a stable, readable order
    ranking = tuple(sorted(suspicions, key=lambda s: (-s.score, s.element)))
    return Localization(
        formula=formula,
        ranking=ranking,
        total_failed=total_failed,
        total_passed=total_passed,
        notes=tuple(notes),
    )


def render(report: Localization, *, top: int = 10) -> str:
    """A human-readable rendering of the ranked suspects."""
    header = (
        f"fault localization ({report.formula}): "
        f"{report.total_failed} failing / {report.total_passed} passing tests"
    )
    lines = [header]
    if report.notes:
        lines.append("  notes: " + "; ".join(report.notes))
    if report.prime_suspects:
        lines.append("  PRIME SUSPECTS (tied at top): " + ", ".join(report.prime_suspects))
    shown = [s for s in report.ranking if s.score > 0][:top]
    if shown:
        lines.append("  ranked suspects (suggest-only):")
        for s in shown:
            lines.append(f"    {s.score:.4f}  {s.element}  (failed {s.ef}, passed {s.ep})")
    else:
        lines.append("  no suspicious elements (no element executed by a failing test)")
    lines.append("  CAVEAT: " + report.caveat)
    return "\n".join(lines)
