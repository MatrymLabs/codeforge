"""CARD: aethryn_diagnostics -- common diagnostics for the Aethryn compiler foundation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DiagnosticSeverity = Literal["error", "warning", "info"]
DiagnosticVerdict = Literal["CLEAN", "WATCHLIST", "FAIL"]


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One actionable compiler finding with source and authority context."""

    code: str
    severity: DiagnosticSeverity
    subsystem: str
    source_path: str
    record_id: str
    field: str
    message: str
    violated_rule: str
    authority_source: str
    suggested_correction: str
    related_records: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    """An immutable collection of diagnostics with a reason-bearing verdict."""

    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def verdict(self) -> DiagnosticVerdict:
        if any(item.severity == "error" for item in self.diagnostics):
            return "FAIL"
        if any(item.severity == "warning" for item in self.diagnostics):
            return "WATCHLIST"
        return "CLEAN"

    def merge(self, *reports: DiagnosticReport) -> DiagnosticReport:
        """Return a report containing this report followed by the supplied reports."""
        findings = list(self.diagnostics)
        for report in reports:
            findings.extend(report.diagnostics)
        return DiagnosticReport(tuple(findings))


def format_diagnostics(report: DiagnosticReport) -> str:
    """Render diagnostics for a human or CI log without losing corrective action."""
    lines = [f"verdict: {report.verdict}"]
    for finding in report.diagnostics:
        location = finding.source_path or "<generated>"
        if finding.record_id:
            location += f"/{finding.record_id}"
        if finding.field:
            location += f".{finding.field}"
        lines.append(f"{finding.severity}: {finding.code} at {location}: {finding.message}")
        lines.append(f"  rule: {finding.violated_rule}")
        lines.append(f"  authority: {finding.authority_source}")
        lines.append(f"  action: {finding.suggested_correction}")
    return "\n".join(lines)


def diagnostic(
    code: str,
    message: str,
    *,
    subsystem: str,
    source_path: str = "",
    record_id: str = "",
    field: str = "",
    violated_rule: str,
    authority_source: str,
    suggested_correction: str,
    severity: DiagnosticSeverity = "error",
    related_records: tuple[str, ...] = (),
) -> Diagnostic:
    """Build one diagnostic with explicit corrective and authority fields."""
    return Diagnostic(
        code=code,
        severity=severity,
        subsystem=subsystem,
        source_path=source_path,
        record_id=record_id,
        field=field,
        message=message,
        violated_rule=violated_rule,
        authority_source=authority_source,
        suggested_correction=suggested_correction,
        related_records=related_records,
    )
