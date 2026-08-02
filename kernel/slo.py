"""CARD: slo -- service-level objective + error budget for the engine-tick latency SLI.

The Chronicle already records one SLI point per measured run: `engine_tick.median_us`
(`parts/bench.py --record`, `make trend`). Measuring a latency is not the same as having an
*objective* for it. This part wraps that recorded SLI in a stated SLO and an error budget, the
Google SRE discipline made executable:

- an **objective** (>= X% of recorded runs keep the median tick within a latency threshold),
- an **error budget** (1 - SLO: the fraction of runs *allowed* to breach), and
- a **verdict** reporting how much of that budget has been burned (pass | watchlist | breach),
  or an honest `no-data` when nothing has been recorded yet (absence is never a false pass).

It reads the retained ledger and computes. It never mutates state, the SLI, or the world (a
verdict is a projection of recorded evidence, architecture law 1).

Provenance: original implementation. The error-budget formula (`budget = 1 - SLO`) and the
SLI/SLO/error-budget vocabulary are the publicly documented Google SRE pattern (SRE Book, ch. 3
"Embracing Risk" and ch. 4 "Service Level Objectives"); no code is copied. This is a
reimplementation built to study that pattern, not affiliated with or endorsed by Google.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from kernel import chronicle

# The SLI the Chronicle already records (parts/bench.py --record). One point per measured run.
SLI_NAME = "engine_tick.median_us"

# The objective, stated honestly and grounded in measured data
# (docs/reports/slo/engine-tick-slo.md): on the reference host the median tick is ~58us, so a
# 150us threshold is ~2.6x headroom -- loose enough to absorb host jitter, tight enough that a
# breach signals a real regression. Both are host-relative and overridable at the call site.
DEFAULT_THRESHOLD_US = 150.0
DEFAULT_OBJECTIVE_PCT = 99.0

# Burn past this fraction of the budget and the SLI is a watchlist item before it is a breach.
_WATCHLIST_AT_PCT = 75.0


class SloError(ValueError):
    """Reject a nonsensical objective (percentage outside (0, 100), non-positive threshold),
    loudly, rather than emit a meaningless verdict."""


@dataclass(frozen=True)
class SloVerdict:
    """The evaluated standing of one SLI against its objective and error budget."""

    sli_name: str
    threshold_us: float
    objective_pct: float
    samples: int
    good: int  # runs within the threshold
    bad: int  # runs that breached the threshold
    attainment_pct: float  # good / samples * 100 (0.0 when there are no samples)
    budget_pct: float  # 100 - objective_pct: the fraction of runs allowed to breach
    allowed_bad: float  # samples * (budget fraction): how many breaches the budget permits
    budget_consumed_pct: float  # bad / allowed_bad * 100: how much of the budget is burned
    budget_meaningful: bool  # allowed_bad >= 1: below this, one breach trips the whole budget
    verdict: str  # "pass" | "watchlist" | "breach" | "no-data"


def evaluate(
    threshold_us: float = DEFAULT_THRESHOLD_US,
    objective_pct: float = DEFAULT_OBJECTIVE_PCT,
    *,
    sli_name: str = SLI_NAME,
    root: Path | None = None,
) -> SloVerdict:
    """Read the recorded SLI series and evaluate it against the objective and error budget.

    Fails loud (`SloError`) on a threshold <= 0 or an objective outside (0, 100). An absent or
    empty series returns a `no-data` verdict, never a crash and never a false pass.
    """
    if threshold_us <= 0:
        raise SloError(f"threshold_us must be > 0, got {threshold_us}")
    if not 0.0 < objective_pct < 100.0:
        raise SloError(f"objective_pct must be in (0, 100), got {objective_pct}")

    budget_pct = 100.0 - objective_pct
    series = chronicle.trend(sli_name, root=root)
    samples = len(series)
    if samples == 0:
        return SloVerdict(
            sli_name=sli_name,
            threshold_us=threshold_us,
            objective_pct=objective_pct,
            samples=0,
            good=0,
            bad=0,
            attainment_pct=0.0,
            budget_pct=budget_pct,
            allowed_bad=0.0,
            budget_consumed_pct=0.0,
            budget_meaningful=False,
            verdict="no-data",
        )

    bad = sum(1 for r in series if float(r.payload["value"]) > threshold_us)
    good = samples - bad
    attainment_pct = good / samples * 100.0
    allowed_bad = samples * (budget_pct / 100.0)
    # allowed_bad is always > 0 here (0 < budget_pct and samples >= 1), so this is well-defined.
    budget_consumed_pct = bad / allowed_bad * 100.0
    budget_meaningful = allowed_bad >= 1.0

    if bad > allowed_bad:
        verdict = "breach"
    elif budget_consumed_pct >= _WATCHLIST_AT_PCT:
        verdict = "watchlist"
    else:
        verdict = "pass"

    return SloVerdict(
        sli_name=sli_name,
        threshold_us=threshold_us,
        objective_pct=objective_pct,
        samples=samples,
        good=good,
        bad=bad,
        attainment_pct=attainment_pct,
        budget_pct=budget_pct,
        allowed_bad=allowed_bad,
        budget_consumed_pct=budget_consumed_pct,
        budget_meaningful=budget_meaningful,
        verdict=verdict,
    )


def render(v: SloVerdict) -> str:
    """A read-only, human report of an SLO verdict for the `slo` verb / `make slo`."""
    if v.verdict == "no-data":
        return "\n".join(
            [
                f"SLO - {v.sli_name}: NO DATA",
                f"  objective  : >= {v.objective_pct:g}% of runs with median <= "
                f"{v.threshold_us:g}us",
                "  No SLI points are recorded yet; run `make trend` to file a measured run.",
                "  (Absence reads as no-data, never a false pass.)",
            ]
        )
    lines = [
        f"SLO - {v.sli_name}: {v.verdict.upper()}",
        f"  objective   : >= {v.objective_pct:g}% of runs with median <= {v.threshold_us:g}us",
        f"  runs        : {v.samples}  (good {v.good}, bad {v.bad})",
        f"  attainment  : {v.attainment_pct:.2f}%   (objective {v.objective_pct:g}%)",
        f"  error budget: {v.budget_pct:g}% of runs  ->  {v.allowed_bad:.2f} breach(es) allowed",
        f"  budget burn : {v.budget_consumed_pct:.1f}% consumed",
    ]
    if not v.budget_meaningful:
        need = math.ceil(1.0 / (v.budget_pct / 100.0))
        lines.append(
            f"  NOTE: only {v.samples} run(s) recorded; the budget allows < 1 breach, so a single "
            f"breach trips it. Record >= {need} runs for a statistically meaningful budget."
        )
    if v.verdict == "breach":
        lines.append(
            "  POLICY: budget exhausted -> freeze latency-risking changes; see the SLO doc."
        )
    lines.append("  (Host-relative: the SLI is measured on one host; compare only within a host.)")
    return "\n".join(lines)


def slo(arg: str = "") -> str:
    """The read-only `slo` verb: evaluate the engine-tick SLI against its objective + error budget.

    Reads only. A tampered ledger surfaces its integrity failure honestly (via the Chronicle)
    rather than crashing the tick.
    """
    try:
        return render(evaluate())
    except (SloError, chronicle.ChronicleError) as exc:
        return f"The SLO could not be evaluated: {exc}"


def main(argv: list[str] | None = None) -> int:
    """`make slo`: evaluate the engine-tick SLO and print the verdict.

    Optional args: `slo [threshold_us] [objective_pct]`. Returns 1 only on a `breach` (the SRE
    "budget exhausted" signal, so a pipeline can act on it); 0 on pass, watchlist, or no-data.
    Deliberately NOT wired into `make check`: the SLI is host-relative and sparse.
    """
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    try:
        threshold = float(args[0]) if len(args) > 0 else DEFAULT_THRESHOLD_US
        objective = float(args[1]) if len(args) > 1 else DEFAULT_OBJECTIVE_PCT
        verdict = evaluate(threshold, objective)
    except (SloError, chronicle.ChronicleError, ValueError) as exc:
        print(f"SLO evaluation failed: {exc}")
        return 2
    print(render(verdict))
    return 1 if verdict.verdict == "breach" else 0


if __name__ == "__main__":
    raise SystemExit(main())
