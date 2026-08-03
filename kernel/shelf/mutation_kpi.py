"""CARD: mutation_kpi -- normalize a mutation-testing run into a posture-style evidence KPI.

Opened by the "Closing the Five Capability Gaps at Matrym Labs" field report (RD-2026-0003,
claim #2). The report's #1 acquirer-facing evidence signal is the MUTATION SCORE: it proves a
test suite would notice if the code were wrong, where line coverage cannot. codeforge already
runs mutation testing (`make mutation`, cosmic-ray; see docs/mutation_testing.md) but the number
lives only in a doc. This turns a run into a KPI in the same MEASURED / NOT_COMPUTABLE honesty
shape `kernel/posture.py` uses, so the score becomes evidence on disk, not a manual number.

Tool-agnostic core (`mutation_score_kpi` over a structured `MutationResult` any tool produces)
plus a thin cosmic-ray adapter (`parse_cr_report` / `parse_cr_rate`) faithful to the real
cr-report/cr-rate output. The posture-KPI consumer (a `mutation_kill_rate` KpiSpec fed by a
recorded run) is the gated follow-up, exactly as the shelf's earlier parts landed part-first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

MEASURED = "measured"
NOT_COMPUTABLE = "not_computable"

# Anti-gaming metadata (the DoD secure-coding doc's rule, mirrored from posture.KpiSpec): a value
# is never context-free - it names its scope, source, target, and owner.
KPI_ID = "mutation_kill_rate"
KPI_SCOPE = "modules enrolled in cosmic-ray.toml"
KPI_SOURCE = "a recorded `make mutation` (cosmic-ray) session"
KPI_OWNER = "codeforge maintainer"
DEFAULT_TARGET_KILL_RATE = 0.70  # the field report's per-component floor for a suite that bites
DEFAULT_FRESHNESS_DAYS = 30  # a mutation run older than this is stale evidence, not current


class MutationKpiError(ValueError):
    """Raised loud and early on incoherent mutation counts - a KPI must never launder bad input."""


@dataclass(frozen=True)
class MutationResult:
    """One mutation run's structured outcome. `run_date` is when the session was executed."""

    total: int
    killed: int
    survived: int
    run_date: date
    incomplete: int = 0

    def __post_init__(self) -> None:
        for name, value in (
            ("total", self.total),
            ("killed", self.killed),
            ("survived", self.survived),
            ("incomplete", self.incomplete),
        ):
            if value < 0:
                raise MutationKpiError(f"{name} cannot be negative (got {value})")
        accounted = self.killed + self.survived + self.incomplete
        if accounted > self.total:
            raise MutationKpiError(
                f"killed+survived+incomplete ({accounted}) exceeds total ({self.total})"
            )

    @property
    def kill_rate(self) -> float:
        """Fraction of COMPLETED mutants killed. Incomplete mutants are excluded from the
        denominator (an errored/timed-out mutant is not evidence either way)."""
        completed = self.killed + self.survived
        return self.killed / completed if completed else 0.0


@dataclass(frozen=True)
class MutationKpi:
    """The computed KPI: measurable-or-not, honest about which, never a faked zero."""

    status: str  # MEASURED | NOT_COMPUTABLE
    kill_rate: float | None
    detail: str
    breaches_target: bool = False

    @property
    def measured(self) -> bool:
        return self.status == MEASURED


def mutation_score_kpi(
    result: MutationResult | None,
    today: date,
    *,
    target_kill_rate: float = DEFAULT_TARGET_KILL_RATE,
    freshness_days: int = DEFAULT_FRESHNESS_DAYS,
) -> MutationKpi:
    """Normalize a mutation run into a KPI. NOT_COMPUTABLE (never a faked 0) when there is no run,
    the run is stale, or it produced no mutants - each with the exact reason and the store/action
    that would make it MEASURED."""
    if result is None:
        return MutationKpi(
            NOT_COMPUTABLE,
            None,
            f"no mutation session on disk; run `make mutation` and record it "
            f"({KPI_SOURCE}) to measure {KPI_ID}",
        )
    if result.total == 0:
        return MutationKpi(
            NOT_COMPUTABLE,
            None,
            "the recorded session generated 0 mutants (nothing enrolled in cosmic-ray.toml)",
        )
    age_days = (today - result.run_date).days
    if age_days < 0:
        raise MutationKpiError(f"run_date {result.run_date} is in the future relative to {today}")
    if age_days > freshness_days:
        return MutationKpi(
            NOT_COMPUTABLE,
            None,
            f"stale evidence: last mutation run {age_days}d ago "
            f"(freshness window {freshness_days}d); re-run `make mutation`",
        )
    rate = result.kill_rate
    breaches = rate < target_kill_rate
    detail = (
        f"{result.killed}/{result.killed + result.survived} completed mutants killed "
        f"({rate:.0%}); target {target_kill_rate:.0%}; run {age_days}d ago"
    )
    return MutationKpi(MEASURED, rate, detail, breaches_target=breaches)


# --- cosmic-ray adapter: parse the real `make mutation` output into a MutationResult ------------
# `cr-report` ends with a summary (verified-real):
#     total jobs: 31
#     complete: 31 (100.00%)
#     surviving mutants: 0 (0.00%)
# `cr-rate` prints the survival percent as a bare float, e.g. "0.00".

_TOTAL = re.compile(r"^total jobs:\s*(\d+)", re.MULTILINE)
_COMPLETE = re.compile(r"^complete:\s*(\d+)", re.MULTILINE)
_SURVIVING = re.compile(r"^surviving mutants:\s*(\d+)", re.MULTILINE)


def parse_cr_report(text: str, run_date: date) -> MutationResult:
    """Parse a `cr-report` summary into a MutationResult. Loud on a missing summary line."""
    total_m = _TOTAL.search(text)
    complete_m = _COMPLETE.search(text)
    surviving_m = _SURVIVING.search(text)
    missing = [
        name
        for name, m in (
            ("total jobs", total_m),
            ("complete", complete_m),
            ("surviving mutants", surviving_m),
        )
        if m is None
    ]
    if missing:
        raise MutationKpiError(f"cr-report summary missing line(s): {', '.join(missing)}")

    total = int(total_m.group(1))  # type: ignore[union-attr]
    complete = int(complete_m.group(1))  # type: ignore[union-attr]
    survived = int(surviving_m.group(1))  # type: ignore[union-attr]
    killed = complete - survived
    incomplete = total - complete
    if killed < 0:
        raise MutationKpiError(
            f"cr-report incoherent: surviving ({survived}) exceeds complete ({complete})"
        )
    return MutationResult(
        total=total, killed=killed, survived=survived, incomplete=incomplete, run_date=run_date
    )


def parse_cr_rate(text: str) -> float:
    """Parse the survival RATE (percent) `cr-rate` prints as a bare float (e.g. '0.00'). Returns
    the survival fraction in [0, 1]; kill rate is 1 - survival."""
    token = text.strip().split()[0] if text.strip() else ""
    try:
        pct = float(token)
    except ValueError as exc:
        raise MutationKpiError(f"cr-rate output not a number: {text!r}") from exc
    if not 0.0 <= pct <= 100.0:
        raise MutationKpiError(f"cr-rate survival percent out of range: {pct}")
    return pct / 100.0
