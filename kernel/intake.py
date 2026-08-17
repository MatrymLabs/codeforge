"""CARD: intake -- the Technology Intake Office: controlled adoption, Python-native by law.

CodeForge stays Python-native; Python owns the orchestration. Other technologies (frameworks,
languages, tools, protocols, services, runtimes) may enter -- but only through explicit boundaries,
as dependencies, tools, plugins, adapters, subprocess workers, external services, clients, build or
render targets, or research references -- never merely because they are popular, modern, or an AI
asked (docs/technology_intake.md). This card is the machine-checkable gate for that doctrine.

It reads an intake ledger (intake_ledger.toml) of TechnologyIntakeRecords and reports every record
that is INCOMPLETE (missing one of the ten onboarding requirements every integration must carry) or
SELF-INCONSISTENT (an unknown classification or decision, a NATIVE_PYTHON row that is not Python, an
externally-hosted role with no declared boundary, or an APPROVED technology with an unfilled
requirement). Frameless: stdlib only (tomllib), no new dependency to police adoption; it mutates
nothing and reports a verdict. `make intake` runs it; the test twin rides `make check`, so a
technology adopted without a complete, consistent onboarding record cannot merge silently.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_LEDGER = _ROOT / "intake_ledger.toml"

# The relationships a technology may hold to CodeForge. Python owns the core; everything else is a
# boundary. A rejected candidate is recorded too, so a "no" is remembered, not re-litigated.
CLASSIFICATIONS = frozenset(
    {
        "NATIVE_PYTHON",  # implemented and run directly in supported Python
        "PYTHON_PACKAGE",  # installed through the approved Python package workflow
        "PYTHON_FRAMEWORK_EXTENSION",  # extends Evennia/Django/Twisted/FastAPI/etc.
        "COMPILED_EXTENSION",  # a compiled accelerator behind a Python interface
        "SUBPROCESS_WORKER",  # invoked as a separate process, spoken to over a contract
        "EXTERNAL_SERVICE",  # a network service CodeForge calls, never hosts
        "CLIENT_TECHNOLOGY",  # runs in the client/browser, not the engine
        "BUILD_TARGET",  # a build/packaging output, not a runtime dependency
        "RENDER_TARGET",  # a rendering surface (terminal, web, desktop)
        "DEV_TOOL",  # development-only; never ships in the wheel
        "RESEARCH_REFERENCE",  # studied for ideas, not integrated
        "REJECTED",  # evaluated and declined
    }
)

# The onboarding pipeline, in order. A record's `stage` says how far it has come; nothing jumps
# to `deployed` without passing through approval.
ONBOARDING_STAGES = (
    "candidate",
    "identity_verified",
    "provenance_reviewed",
    "license_reviewed",
    "capability_interviewed",
    "gap_analyzed",
    "python_assessed",
    "architecture_placed",
    "security_screened",
    "dependency_reviewed",
    "prototyped",
    "tested",
    "arc_evaluated",
    "approved",
    "carded",
    "deployed",
    "in_review",
)

# The ten things every integration must have (doctrine rule 5). A record missing any is INCOMPLETE.
REQUIRED = (
    "purpose",
    "owner",
    "contract",
    "security_review",
    "license_review",
    "compatibility",
    "testing_strategy",
    "failure_strategy",
    "upgrade_strategy",
    "removal_strategy",
)

# The decisions the office may reach. The three "default down" verdicts encode the doctrine: a
# case is weak on need/skill/removability, prefer stdlib, research-only, or defer.
DECISIONS = frozenset(
    {"approved", "held", "rejected", "stdlib_first", "research_only", "integrate_later"}
)

# Classifications that live OUTSIDE the Python core and therefore must name their boundary.
_EXTERNAL = frozenset(
    {
        "SUBPROCESS_WORKER",
        "EXTERNAL_SERVICE",
        "CLIENT_TECHNOLOGY",
        "COMPILED_EXTENSION",
        "RENDER_TARGET",
    }
)


class IntakeError(RuntimeError):
    """A malformed intake ledger fails loud, never silently passes."""


@dataclass(frozen=True)
class TechnologyIntakeRecord:
    """One technology's onboarding record. `data` holds the raw ledger fields; the derived accessors
    read the ones the gate checks. Absent fields read as empty, so a gap is a missing string."""

    intake_id: str
    data: dict[str, object]

    def _text(self, key: str) -> str:
        value = self.data.get(key, "")
        return value.strip() if isinstance(value, str) else ""

    @property
    def name(self) -> str:
        return self._text("technology_name") or self.intake_id

    @property
    def classification(self) -> str:
        return self._text("classification")

    @property
    def language(self) -> str:
        return self._text("language").lower()

    @property
    def decision(self) -> str:
        return self._text("decision")

    @property
    def boundary(self) -> str:
        return self._text("proposed_boundary")

    def requirement(self, key: str) -> str:
        return self._text(key)


def read_ledger(path: Path = _LEDGER) -> list[TechnologyIntakeRecord]:
    """Read the intake ledger into records. Each `[tech.<id>]` table is one technology. A missing or
    malformed ledger fails loud."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise IntakeError(f"intake ledger not found at {path}") from exc  # noqa: TRY003
    except tomllib.TOMLDecodeError as exc:
        raise IntakeError(f"malformed intake ledger: {exc}") from exc  # noqa: TRY003
    tech = raw.get("tech", {})
    if not isinstance(tech, dict):
        raise IntakeError("intake ledger: [tech] must be a table of records")  # noqa: TRY003
    return [TechnologyIntakeRecord(intake_id, fields) for intake_id, fields in tech.items()]


def gaps(record: TechnologyIntakeRecord) -> list[str]:
    """Every reason a record is not admissible, in order, or an empty list when it is sound.

    Two kinds: INCOMPLETE (a missing requirement) and INCONSISTENT (a self-contradiction).
    """
    found: list[str] = []
    if record.classification not in CLASSIFICATIONS:
        found.append(f"unknown classification {record.classification!r}")
    if record.decision not in DECISIONS:
        found.append(f"unknown decision {record.decision!r}")
    # A Python-core classification must actually be Python.
    if record.classification in ("NATIVE_PYTHON", "PYTHON_PACKAGE") and record.language not in (
        "",
        "python",
    ):
        found.append(f"{record.classification} but language is {record.language!r}, not python")
    # A technology living outside the core must name the boundary it enters through.
    if record.classification in _EXTERNAL and not record.boundary:
        found.append(f"{record.classification} but no proposed_boundary declared")
    # An APPROVED technology must carry all ten; a held/research row may still be filling them.
    if record.decision == "approved":
        found.extend(f"missing {req}" for req in REQUIRED if not record.requirement(req))
    return found


@dataclass(frozen=True)
class IntakeAudit:
    """The verdict: the records read, and every one with gaps (with its gaps). Passes when clean."""

    records: list[TechnologyIntakeRecord]
    flagged: dict[str, list[str]] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.flagged


def audit_intake(ledger: Path = _LEDGER) -> IntakeAudit:
    """Read the ledger and flag every record that is incomplete or inconsistent."""
    records = read_ledger(ledger)
    flagged = {record.intake_id: g for record in records if (g := gaps(record))}
    return IntakeAudit(records, flagged)


def render_intake(ledger: Path = _LEDGER) -> str:
    """The gate's human report (used by `make intake` and the in-game terminal)."""
    audit = audit_intake(ledger)
    verdict = "PASS" if audit.passed else "FAIL"
    lines = [
        f"Technology Intake: {verdict}",
        f"  onboarded records: {len(audit.records)}",
    ]
    approved = sum(1 for r in audit.records if r.decision == "approved")
    lines.append(f"  approved: {approved}   flagged: {len(audit.flagged)}")
    for intake_id, reasons in sorted(audit.flagged.items()):
        lines.append(f"  FAIL {intake_id}:")
        lines.extend(f"    - {reason}" for reason in reasons)
    if audit.passed:
        lines.append("  every onboarding record is complete and consistent.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    """`python -m kernel.intake` / `make intake`: print the report, exit non-zero on a FAIL."""
    print(render_intake())
    return 0 if audit_intake().passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
