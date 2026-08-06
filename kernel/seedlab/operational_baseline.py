"""Durable evidence record for a Seed's operational readiness baseline.

This module does not claim that a Seed is production-ready.  It records repeatable evidence from
the operational checks that were actually run: concurrency, persistence migration, backup and
restore, health, telemetry, and recovery.  The checks remain owned by their existing services;
this record is the governed, portable projection that a Creator Workshop or operator can inspect.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from kernel.shelf.atomic_write import atomic_write_text

PASSED = "passed"
FAILED = "failed"
NOT_RUN = "not_run"
CHECK_STATUSES = (PASSED, FAILED, NOT_RUN)
EVIDENCE_ONLY = "evidence_only"

REQUIRED_CHECKS = (
    "concurrent_actions",
    "persistence_migration",
    "backup_restore",
    "health",
    "telemetry",
    "recovery",
)

_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


class OperationalBaselineError(ValueError):
    """A baseline was incomplete, malformed, or unsafe to persist."""


def _required(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OperationalBaselineError(f"{field} must not be empty")
    return value.strip()


@dataclass(frozen=True)
class OperationalCheck:
    """One named operational check and the evidence locator supporting its result."""

    name: str
    status: str
    evidence: str

    def __post_init__(self) -> None:
        _required(self.name, "check name")
        if self.status not in CHECK_STATUSES:
            raise OperationalBaselineError(
                f"check {self.name!r} has unknown status {self.status!r}"
            )
        _required(self.evidence, f"evidence for {self.name!r}")

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "evidence": self.evidence}


@dataclass(frozen=True)
class OperationalBaseline:
    """A complete, file-backed operational evidence packet for one Seed."""

    baseline_id: str
    seed_id: str
    started_at: str
    completed_at: str
    checks: tuple[OperationalCheck, ...]
    limitations: tuple[str, ...]
    readiness: str = EVIDENCE_ONLY

    def __post_init__(self) -> None:
        for value, field in (
            (self.baseline_id, "baseline_id"),
            (self.seed_id, "seed_id"),
            (self.started_at, "started_at"),
            (self.completed_at, "completed_at"),
        ):
            _required(value, field)
        if not _SAFE_ID.fullmatch(self.baseline_id):
            raise OperationalBaselineError("baseline_id must be a safe identifier")
        if self.readiness != EVIDENCE_ONLY:
            raise OperationalBaselineError("operational evidence cannot claim production readiness")
        if not self.checks:
            raise OperationalBaselineError("baseline requires operational checks")
        names = tuple(check.name for check in self.checks)
        if len(set(names)) != len(names):
            raise OperationalBaselineError("baseline check names must be unique")
        missing = [name for name in REQUIRED_CHECKS if name not in names]
        if missing:
            raise OperationalBaselineError(f"baseline is missing checks: {', '.join(missing)}")
        if not self.limitations or any(not str(item).strip() for item in self.limitations):
            raise OperationalBaselineError("baseline requires explicit limitations")

    @property
    def passed(self) -> bool:
        """Whether every required check passed; this still does not mean production-ready."""
        return all(check.status == PASSED for check in self.checks)

    def to_dict(self) -> dict[str, object]:
        return {
            "baseline_id": self.baseline_id,
            "seed_id": self.seed_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "readiness": self.readiness,
            "passed": self.passed,
            "checks": [check.to_dict() for check in self.checks],
            "limitations": list(self.limitations),
        }

    def save(self, path: Path) -> None:
        """Write the packet atomically so an operator never reads a partial baseline."""
        atomic_write_text(
            Path(path), json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", fsync=True
        )

    @classmethod
    def load(cls, path: Path) -> OperationalBaseline:
        """Load a baseline and re-run all completeness and readiness gates."""
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise TypeError("baseline must be an object")
            checks = raw["checks"]
            limitations = raw["limitations"]
            if not isinstance(checks, list) or not isinstance(limitations, list):
                raise TypeError("checks and limitations must be lists")
            parsed = tuple(
                OperationalCheck(
                    name=str(item["name"]),
                    status=str(item["status"]),
                    evidence=str(item["evidence"]),
                )
                for item in checks
                if isinstance(item, dict)
            )
            if len(parsed) != len(checks):
                raise TypeError("every check must be an object")
            return cls(
                baseline_id=str(raw["baseline_id"]),
                seed_id=str(raw["seed_id"]),
                started_at=str(raw["started_at"]),
                completed_at=str(raw["completed_at"]),
                checks=parsed,
                limitations=tuple(str(item) for item in limitations),
                readiness=str(raw.get("readiness", EVIDENCE_ONLY)),
            )
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            if isinstance(exc, OperationalBaselineError):
                raise
            raise OperationalBaselineError(f"cannot load operational baseline: {exc}") from exc


def render_baseline(baseline: OperationalBaseline) -> str:
    """Render the evidence packet for text-first operator and Master Client projections."""
    lines = [
        f"OPERATIONAL BASELINE {baseline.baseline_id} ({baseline.seed_id})",
        f"  result: {'passed' if baseline.passed else 'incomplete'}",
        f"  readiness: {baseline.readiness} (not production-ready)",
    ]
    lines.extend(
        f"  [{check.status:<7}] {check.name}: {check.evidence}" for check in baseline.checks
    )
    lines.append("  limitations:")
    lines.extend(f"    - {limitation}" for limitation in baseline.limitations)
    return "\n".join(lines)
