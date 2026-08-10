"""Audit the SeedLab modules: what is platform-capable, what is support, and what is game-adjacent.

This is the honest inventory layer for the recentered platform work. It does not pretend that every
SeedLab module is production-ready or game-first; it classifies the actual `kernel/seedlab/*.py`
modules into a small set of labels with a short rationale for each.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_PLATFORM_CAPABLE = {
    "artifact_store",
    "backup",
    "form",
    "kernel",
    "model_store",
    "platform_proof",
    "project_hub",
    "provision",
    "source_connector",
    "source_modeler",
    "tool_runner",
    "workspace_gmcp",
    "workspace_verb",
}

_PLATFORM_SUPPORT = {
    "cli_generator",
    "cli_synthesis",
    "domain",
    "project_model",
    "seed_package",
    "synthesis",
    "web_api_generator",
}

_GAME_ADJACENT = {
    "reference_seed",
}


@dataclass(frozen=True)
class SeedLabModuleAuditEntry:
    """One SeedLab module and the role the audit assigns it."""

    module: str
    classification: str
    rationale: str


@dataclass(frozen=True)
class SeedLabAuditReport:
    """The current SeedLab inventory, grouped by classification."""

    root: str
    entries: tuple[SeedLabModuleAuditEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "entries": [
                {
                    "module": entry.module,
                    "classification": entry.classification,
                    "rationale": entry.rationale,
                }
                for entry in self.entries
            ],
        }


def _classify(stem: str) -> tuple[str, str]:
    if stem in _PLATFORM_CAPABLE:
        return "platform-capable", "directly participates in the Seed lifecycle or workspace loop"
    if stem in _PLATFORM_SUPPORT:
        return "platform-support", "supports generation, modeling, or serialization around the loop"
    if stem in _GAME_ADJACENT:
        return (
            "game-adjacent",
            "tied to the flagship game/reference Seed rather than the platform core",
        )
    return "unclassified", "present in SeedLab but not yet explicitly categorized"


def audit_seedlab_modules(root: Path | None = None) -> SeedLabAuditReport:
    """Classify the actual `kernel/seedlab/*.py` modules under the repository."""
    base = Path(root) if root is not None else Path(__file__).resolve().parent
    entries = []
    for path in sorted(base.glob("*.py")):
        if path.name == "__init__.py":
            continue
        stem = path.stem
        classification, rationale = _classify(stem)
        entries.append(SeedLabModuleAuditEntry(stem, classification, rationale))
    return SeedLabAuditReport(root=str(base), entries=tuple(entries))


def render_seedlab_audit(report: SeedLabAuditReport) -> str:
    """Human-readable audit output for operators."""
    lines = [f"SeedLab audit: {report.root}"]
    for entry in report.entries:
        lines.append(f"  {entry.module:<18} {entry.classification} - {entry.rationale}")
    return "\n".join(lines)
