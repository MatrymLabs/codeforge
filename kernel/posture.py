"""CARD: posture -- compute the security-posture KPI scorecard from evidence we already produce.

RD-2026-0002 finding #5. The fleet HAS gates (audit-runtime, bandit, detect-secrets, SBOM, patch
ritual) but never MEASURED its own posture; the SSDF map even names "CVE past SLA" as a failure
condition with no SLA defined anywhere. This computes the KPI catalog the DoD secure-coding doc
prescribes, each metric carrying its anti-gaming metadata (scope, data source, exclusions, target,
owner) so a number can never be quoted without its context.

Honesty is the whole point (the doc's rule: "measure deployed fixes, not closed tickets"): a KPI is
either MEASURED (from evidence on disk) or NOT_COMPUTABLE with the exact store that enables it,
never a faked zero. That distinction is itself the DoD-readiness signal: you cannot fake having
measured, and an honest "we do not yet measure MTTR because no timestamped remediation store exists"
beats a green dashboard built on nothing.

Evidence is INJECTED (a seam): `compute(evidence, today)` takes a parsed PostureEvidence, so tests
never read the filesystem; `load_evidence(dir, today)` reads the real security-evidence/ store.
Clean-room, stdlib only (json, datetime, pathlib).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pure type import; the shelf part is loaded lazily where it is actually used
    from kernel.shelf.mutation_kpi import MutationResult

MEASURED = "measured"
NOT_COMPUTABLE = "not_computable"


class PostureError(ValueError):
    """Raised when evidence on disk cannot be parsed into a posture scorecard."""


@dataclass(frozen=True)
class KpiSpec:
    """One KPI's definition + the anti-gaming metadata the DoD doc requires on every metric."""

    id: str
    question: str  # what it answers, in plain words
    scope: str  # what is (and is not) included
    data_source: str  # where the number comes from
    target: str  # the goal (e.g. "<= 7 days", "0")
    owner: str  # who is accountable
    exclusions: str = ""


@dataclass(frozen=True)
class Kpi:
    """One computed KPI: its spec, whether it was measurable, the value, and the evidence detail."""

    spec: KpiSpec
    status: str  # MEASURED | NOT_COMPUTABLE
    value: float | int | None
    detail: str
    breaches_target: bool = False


@dataclass(frozen=True)
class PostureEvidence:
    """The injected inputs a scorecard is computed from (a seam, so tests never touch disk)."""

    latest_scan_date: date | None = None  # newest security-evidence/*.json date
    open_advisory_count: int | None = None  # advisories in that newest scan
    oldest_advisory_first_seen: date | None = (
        None  # when the oldest still-open advisory first appeared
    )
    remediation_days: tuple[int, ...] | None = (
        None  # per-fix identify->deploy days (needs a persistent store)
    )
    expired_exceptions: int | None = None  # pip-audit --ignore-vuln entries past their review date
    sbom_present: bool | None = None  # a CycloneDX SBOM exists for the release
    scan_cadence_days: int = 1  # the freshness target (daily ritual)
    mutation_result: MutationResult | None = None  # last recorded `make mutation` run (or None)


# The catalog: every KPI carries scope/source/target/owner so a value is never context-free.
KPI_CATALOG: tuple[KpiSpec, ...] = (
    KpiSpec(
        "evidence_freshness_days",
        "how old is our newest security scan evidence?",
        "the security-evidence/ pip-audit store; excludes ad-hoc local runs",
        "newest security-evidence/*.json file date",
        "<= scan cadence (daily ritual: 1 day)",
        "Security Lead",
    ),
    KpiSpec(
        "open_advisory_count",
        "how many known dependency advisories are open right now?",
        "the runtime + dev dependency set in the newest scan",
        "newest security-evidence/*.json (pip-audit)",
        "0",
        "Security Lead",
    ),
    KpiSpec(
        "oldest_open_advisory_days",
        "how long has our longest-standing open advisory been exposed?",
        "still-open advisories only; a fixed one leaves the count",
        "advisory first-seen date vs today",
        "<= 7 days for critical/high",
        "Security Lead",
    ),
    KpiSpec(
        "mean_time_to_remediate_days",
        "on average, how long from a validated finding to a DEPLOYED fix?",
        "deployed fixes, NOT closed tickets (the doc's rule)",
        "a persistent timestamped remediation store (patch_tracker history)",
        "<= 7 days (high), <= 30 (medium)",
        "Security Lead",
    ),
    KpiSpec(
        "expired_exception_count",
        "how many risk exceptions (pip-audit --ignore-vuln) are past their review date?",
        "documented CVE-ignore exceptions",
        "the exception register with review dates",
        "0",
        "Security Lead",
    ),
    KpiSpec(
        "sbom_release_coverage",
        "does the release carry a software bill of materials?",
        "the shipped artifact's SBOM",
        "the CycloneDX SBOM (make sbom)",
        "present",
        "Security Lead",
    ),
    KpiSpec(
        "mutation_kill_rate",
        "would our tests notice if the code were wrong (not just: did the line run)?",
        "modules enrolled in cosmic-ray.toml; incomplete mutants excluded from the denominator",
        "a recorded `make mutation` run (security-evidence/mutation-latest.json)",
        ">= 70% killed (the field report's per-suite floor)",
        "codeforge maintainer",
    ),
)

_BY_ID = {s.id: s for s in KPI_CATALOG}


def _measured(spec_id: str, value: float | int, detail: str, breaches: bool) -> Kpi:  # noqa: PYI041
    return Kpi(_BY_ID[spec_id], MEASURED, value, detail, breaches)


def _not_computable(spec_id: str, why: str) -> Kpi:
    return Kpi(_BY_ID[spec_id], NOT_COMPUTABLE, None, why, breaches_target=False)


def compute(evidence: PostureEvidence, today: date) -> list[Kpi]:  # noqa: PLR0912
    """Compute the posture scorecard from injected evidence: each KPI measured or honestly not."""
    out: list[Kpi] = []

    if evidence.latest_scan_date is None:
        out.append(
            _not_computable(
                "evidence_freshness_days", "no scan evidence found in security-evidence/"
            )
        )
    else:
        age = (today - evidence.latest_scan_date).days
        out.append(
            _measured(
                "evidence_freshness_days",
                age,
                f"newest scan {age}d old (cadence {evidence.scan_cadence_days}d)",
                breaches=age > evidence.scan_cadence_days,
            )
        )

    if evidence.open_advisory_count is None:
        out.append(
            _not_computable("open_advisory_count", "no scan evidence to count advisories from")
        )
    else:
        n = evidence.open_advisory_count
        out.append(
            _measured(
                "open_advisory_count", n, f"{n} open advisories in the newest scan", breaches=n > 0
            )
        )

    if evidence.oldest_advisory_first_seen is None:
        out.append(
            _not_computable(
                "oldest_open_advisory_days",
                "advisory first-seen dates are not tracked (add a per-advisory ledger)",
            )
        )
    else:
        age = (today - evidence.oldest_advisory_first_seen).days
        out.append(
            _measured(
                "oldest_open_advisory_days",
                age,
                f"oldest open advisory exposed {age}d",
                breaches=age > 7,  # noqa: PLR2004
            )
        )

    if not evidence.remediation_days:
        out.append(
            _not_computable(
                "mean_time_to_remediate_days",
                "no persistent timestamped remediation store (patch_tracker is in-memory)",
            )
        )
    else:
        mttr = round(sum(evidence.remediation_days) / len(evidence.remediation_days), 1)
        out.append(
            _measured(
                "mean_time_to_remediate_days",
                mttr,
                f"MTTR {mttr}d over {len(evidence.remediation_days)} fixes",
                breaches=mttr > 7,  # noqa: PLR2004
            )
        )

    if evidence.expired_exceptions is None:
        out.append(
            _not_computable(
                "expired_exception_count", "no exception register with review dates yet"
            )
        )
    else:
        out.append(
            _measured(
                "expired_exception_count",
                evidence.expired_exceptions,
                f"{evidence.expired_exceptions} expired exceptions",
                breaches=evidence.expired_exceptions > 0,
            )
        )

    if evidence.sbom_present is None:
        out.append(_not_computable("sbom_release_coverage", "SBOM presence not provided"))
    else:
        out.append(
            _measured(
                "sbom_release_coverage",
                int(evidence.sbom_present),
                "SBOM present" if evidence.sbom_present else "SBOM MISSING",
                breaches=not evidence.sbom_present,
            )
        )

    # Mutation kill rate: delegate the honesty logic to the shelf part (lazy import keeps posture
    # loadable even if the shelf part is absent, mirroring the advisory_ledger seam below).
    from kernel.shelf.mutation_kpi import mutation_score_kpi  # noqa: PLC0415

    mkpi = mutation_score_kpi(evidence.mutation_result, today)
    if mkpi.measured:
        assert mkpi.kill_rate is not None  # measured => a rate exists
        out.append(
            _measured(
                "mutation_kill_rate",
                round(mkpi.kill_rate, 3),
                mkpi.detail,
                breaches=mkpi.breaches_target,
            )
        )
    else:
        out.append(_not_computable("mutation_kill_rate", mkpi.detail))
    return out


@dataclass(frozen=True)
class Scorecard:
    """The whole posture read: the KPIs, and honest headline counts."""

    kpis: tuple[Kpi, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def measured(self) -> int:
        return sum(1 for k in self.kpis if k.status == MEASURED)

    @property
    def breaches(self) -> tuple[Kpi, ...]:
        return tuple(k for k in self.kpis if k.breaches_target)

    @property
    def not_computable(self) -> tuple[Kpi, ...]:
        return tuple(k for k in self.kpis if k.status == NOT_COMPUTABLE)


def scorecard(evidence: PostureEvidence, today: date) -> Scorecard:
    kpis = compute(evidence, today)
    notes: list[str] = []
    uncomputed = sum(1 for k in kpis if k.status == NOT_COMPUTABLE)
    if uncomputed:
        notes.append(
            f"{uncomputed} KPI(s) not yet computable - build the named store to measure them"
        )
    return Scorecard(kpis=tuple(kpis), notes=tuple(notes))


def load_evidence(
    security_evidence_dir: Path | str,
    today: date,  # noqa: ARG001
    *,
    cadence_days: int = 1,
    advisory_ledger_path: Path | str | None = None,
    mutation_evidence_path: Path | str | None = None,
) -> PostureEvidence:
    """Read the newest pip-audit json from security-evidence/ into PostureEvidence (real-use layer).

    An empty/absent store is HONEST evidence (latest_scan_date=None -> freshness not_computable),
    not an error - a fleet that has not scanned recently should read that way, not green. When an
    advisory_ledger (kernel.advisory_ledger) is supplied, its first_seen/resolved history lights up
    the oldest-advisory and MTTR KPIs that are otherwise NOT_COMPUTABLE. The last recorded
    `make mutation` run (security-evidence/mutation-latest.json by default) lights up the
    mutation-kill-rate KPI the same way - independent of any pip-audit scan."""
    root = Path(security_evidence_dir)

    # Mutation evidence is independent of the pip-audit scan, so load it before the no-scan return.
    from kernel import mutation_recorder  # noqa: PLC0415

    mpath = (
        Path(mutation_evidence_path)
        if mutation_evidence_path is not None
        else root / "mutation-latest.json"
    )
    mutation_result = mutation_recorder.load(mpath)

    scans = sorted(root.glob("*-pip-audit.json")) if root.exists() else []
    if not scans:
        return PostureEvidence(scan_cadence_days=cadence_days, mutation_result=mutation_result)
    newest = scans[-1]
    try:
        data = json.loads(newest.read_text("utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise PostureError(f"cannot read scan evidence {newest}: {exc}") from exc  # noqa: TRY003
    deps = data.get("dependencies", []) if isinstance(data, dict) else data
    advisories = sum(len(d.get("vulns", [])) for d in deps if isinstance(d, dict))
    # the file name carries its date: YYYY-MM-DD-pip-audit.json
    try:
        scan_date = date.fromisoformat(newest.name[:10])
    except ValueError:
        scan_date = date.fromtimestamp(newest.stat().st_mtime)  # noqa: DTZ012

    oldest_first_seen: date | None = None
    remediation: tuple[int, ...] | None = None
    if advisory_ledger_path is not None:
        # lazy import: advisory_ledger is the optional lifecycle store; posture works without it
        from kernel import advisory_ledger as al  # noqa: PLC0415

        states = al.load(advisory_ledger_path)
        oldest_first_seen = al.oldest_open_first_seen(states)
        rem = al.remediation_days(states)
        remediation = rem or None  # empty -> None so the KPI stays honestly not_computable

    return PostureEvidence(
        latest_scan_date=scan_date,
        open_advisory_count=advisories,
        oldest_advisory_first_seen=oldest_first_seen,
        remediation_days=remediation,
        scan_cadence_days=cadence_days,
        mutation_result=mutation_result,
    )


def render(card: Scorecard) -> str:
    """A human-readable posture scorecard (honest: measured values + named gaps)."""
    verdict = "CLEAN" if not card.breaches else "ATTENTION"
    lines = [f"security posture: [{verdict}]  {card.measured}/{len(card.kpis)} KPIs measured"]
    for k in card.kpis:
        if k.status == MEASURED:
            mark = "!!" if k.breaches_target else "ok"
            lines.append(
                f"  [{mark}] {k.spec.id} = {k.value}  (target {k.spec.target})  - {k.detail}"
            )
        else:
            lines.append(f"  [--] {k.spec.id}: NOT COMPUTABLE - {k.detail}")
    for note in card.notes:
        lines.append(f"  note: {note}")
    return "\n".join(lines)
