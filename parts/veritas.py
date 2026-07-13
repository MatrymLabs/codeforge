"""CARD: veritas -- VeritasGate: check that CodeForge's claims match reality.

No claim without correspondence. `truth check` composes the truth-relevant signals --
an overclaim scan, drift-prone hardcoded claims, documentation presence, registry
validity, and the QA board -- into one honest verdict. It REPORTS mismatches, never
hides them, and never asserts more than the evidence supports. It does not prove legal
originality or compliance; it keeps the project's own claims honest.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from parts.hardware import source_gaps
from parts.integrity import overclaim_hits, presence_gaps
from parts.qualitygate import FAIL, gate_all
from parts.registry import load_collective, validate

_ROOT = Path(__file__).resolve().parent.parent

VERIFIED = "verified"
FLAGGED = "flagged"


@dataclass(frozen=True)
class TruthCheck:
    """One claim, its truth status, and the evidence behind the verdict."""

    claim: str
    status: str  # verified | flagged
    evidence: str


# Dated, point-in-time record dirs: a count there is a snapshot, not a drift-prone live claim.
_SNAPSHOT_DIRS = frozenset(
    {"captains-log", "keel_records", "pioneer_experiments", "reports", "postmortems"}
)


def _hardcoded_test_counts(root: Path) -> list[str]:
    """Drift-prone claims: an exact test count in the README or living docs goes stale (it has).

    Scans README.md and every docs/**.md except dated snapshot dirs (where a count is a
    point-in-time record, not a live claim). The CI badge is the one live source of the count.
    """
    targets = [root / "README.md"]
    docs = root / "docs"
    if docs.is_dir():
        targets += [
            p
            for p in sorted(docs.rglob("*.md"))
            if not _SNAPSHOT_DIRS.intersection(p.relative_to(docs).parts)
        ]
    hits: list[str] = []
    for path in targets:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits += [f"{path.name}: {m}" for m in re.findall(r"\b\d+ tests\b", text)]
    return hits


def truth_checks(root: Path | None = None) -> list[TruthCheck]:
    """Run the truth checks, composing signals the repo already produces."""
    base = root if root is not None else _ROOT

    def check(claim: str, ok: bool, good: str, bad: str) -> TruthCheck:
        return TruthCheck(claim, VERIFIED if ok else FLAGGED, good if ok else bad)

    over = overclaim_hits(base)
    counts = _hardcoded_test_counts(base)
    gaps = presence_gaps(base)
    records = load_collective()
    problems = validate(records) if records else ["registry empty"]
    fails = [r.designation for r in gate_all(records) if r.verdict == FAIL]
    catalog_gaps = source_gaps()

    return [
        check(
            "README/docs avoid unqualified compliance / production claims",
            not over,
            "none found",
            "FLAGS: " + ", ".join(over),
        ),
        check(
            "README and docs make no drift-prone hardcoded test count",
            not counts,
            "none (the CI badge is the live source)",
            "hardcoded: " + ", ".join(counts),
        ),
        check(
            "Key documentation is present",
            not gaps,
            "all present",
            "MISSING: " + ", ".join(gaps),
        ),
        check(
            "Classification registry validates (no duplicates / orphans)",
            not problems,
            "clean",
            "; ".join(problems),
        ),
        check(
            "Every Hardware Store part cites a source file that exists",
            not catalog_gaps,
            "all present",
            "MISSING SOURCE: " + ", ".join(catalog_gaps),
        ),
        check(
            "QA board has no failing objects (active claims backed by tests)",
            not fails,
            "no failures",
            "FAILS: " + ", ".join(fails),
        ),
    ]


def render_truth(checks: list[TruthCheck] | None = None) -> str:
    """The `truth check` projection: each check, its verdict, and the overall call.

    Accepts pre-computed checks (so a caller that also needs the pass/fail verdict does
    not run the audit twice); computes them from the live repo when none are passed.
    """
    checks = truth_checks() if checks is None else checks
    flagged = [c for c in checks if c.status != VERIFIED]
    lines = ["VeritasGate: truth check", "", "No claim without correspondence.", ""]
    for c in checks:
        lines.append(f"  [{c.status:8}] {c.claim}")
        lines.append(f"             {c.evidence}")
    lines.append("")
    verdict = (
        "ALL VERIFIED - the project's claims correspond to reality."
        if not flagged
        else f"{len(flagged)} FLAGGED - correct the claim (or the code) before trusting it."
    )
    lines.append(f"Verdict: {verdict}")
    lines.append("")
    lines.append(
        "This keeps CodeForge's own claims honest. "
        "It does not prove legal originality or compliance."
    )
    return "\n".join(lines)


def main() -> int:
    """CLI entry (`python -m parts.veritas`, `make truth`): render the audit and GATE.

    Exit 0 when every claim corresponds to reality; exit 1 the moment one is FLAGGED, so
    the ritual and CI can fail loud on a claim that has drifted from the code.
    """
    checks = truth_checks()
    print(render_truth(checks))
    return 1 if any(c.status != VERIFIED for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
