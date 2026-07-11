"""CARD: stewardship.dependency -- the DependencyGate: admit a new package, or refuse it.

The cleanest direct defense against hallucinated / typosquatted / risky dependencies (the FWA
report's highest-priority, low-effort control). A new package is admitted only if it EXISTS on
the index, is APPROVED in the dependency ledger (or security-reviewed), carries NO critical
vulnerabilities, and has a permissive LICENSE. The result feeds the Stewardship Gate's FWA04
check (`dependencies_approved`).

The index / vulnerability / license lookups are external, so they live behind a `DependencyOracle`
seam: tests inject a `StaticOracle` and never touch the network (a live PyPI/OSV oracle is a later
wiring, and by contract never gates CI). The ledger allowlist is a local file, read offline.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

_ROOT = Path(__file__).resolve().parent.parent.parent

# Permissive licenses compatible with this MIT project. Strong copyleft (GPL/AGPL/LGPL) is not
# admitted automatically -- that is a human policy decision, not a default. Editable policy.
ALLOWED_LICENSES = frozenset(
    {
        "MIT",
        "BSD",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "Apache-2.0",
        "ISC",
        "0BSD",
        "Unlicense",
        "CC0-1.0",
        "PSF-2.0",
        "Python-2.0",
        "MPL-2.0",
    }
)


class DependencyOracle(Protocol):
    """The external lookups a dependency admission needs -- a seam, so tests stay offline."""

    def exists(self, name: str) -> bool: ...
    def critical_cve_count(self, name: str, version: str) -> int: ...
    def license_of(self, name: str, version: str) -> str: ...


@dataclass(frozen=True)
class StaticOracle:
    """An offline oracle built from known facts -- for tests, demos, and reproducible runs."""

    known: frozenset[str] = frozenset()
    vulns: Mapping[str, int] = field(default_factory=dict)
    licenses: Mapping[str, str] = field(default_factory=dict)

    def exists(self, name: str) -> bool:
        return name in self.known

    def critical_cve_count(self, name: str, version: str) -> int:
        return self.vulns.get(name, 0)

    def license_of(self, name: str, version: str) -> str:
        return self.licenses.get(name, "UNKNOWN")


@dataclass(frozen=True)
class DepCheck:
    """One admission rule's verdict for one package (detail explains a failure)."""

    rule_id: str
    requirement: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class AdmissionResult:
    """Whether one package is admitted, and every rule that judged it."""

    package: str
    version: str
    admitted: bool
    checks: tuple[DepCheck, ...]

    def reasons(self) -> list[str]:
        """The rules that refused this package (empty when admitted)."""
        return [f"{c.rule_id}: {c.detail}" for c in self.checks if not c.ok]


def ledger_packages(path: Path | None = None) -> set[str]:
    """The approved-dependency allowlist: the PEP 503 names filed in dependency_ledger.toml."""
    src = path or (_ROOT / "dependency_ledger.toml")
    if not src.exists():
        return set()
    data = tomllib.loads(src.read_text(encoding="utf-8"))
    names: set[str] = set()
    for group in ("runtime", "dev"):
        names |= set(data.get(group, {}).keys())
    return {name.lower() for name in names}


def admit_dependency(
    package: str, version: str, *, allowlist: set[str], oracle: DependencyOracle
) -> AdmissionResult:
    """Admit a package only if it exists, is ledger-approved, is vuln-free, and is licensed OK."""
    name = package.strip().lower()
    exists = oracle.exists(name)
    vulns = oracle.critical_cve_count(name, version)
    lic = oracle.license_of(name, version)
    checks = (
        DepCheck(
            "DEP01",
            "package exists on the index",
            exists,
            f"'{package}' not found on the index (possible hallucinated/typosquatted package)",
        ),
        DepCheck(
            "DEP02",
            "approved in the dependency ledger",
            name in allowlist,
            f"'{package}' is not in the ledger; add a justified row or get a security review",
        ),
        DepCheck(
            "DEP03",
            "no critical vulnerabilities",
            vulns == 0,
            f"{vulns} critical CVE(s) for {package} {version}",
        ),
        DepCheck(
            "DEP04",
            "license is permissive/allowed",
            lic in ALLOWED_LICENSES,
            f"license '{lic}' is not in the allowed set",
        ),
    )
    return AdmissionResult(package, version, all(c.ok for c in checks), checks)


def all_admitted(
    requests: list[tuple[str, str]], *, allowlist: set[str], oracle: DependencyOracle
) -> tuple[bool, list[AdmissionResult]]:
    """Admit every (package, version) request; return (all-admitted?, per-package results)."""
    results = [admit_dependency(n, v, allowlist=allowlist, oracle=oracle) for n, v in requests]
    return all(r.admitted for r in results), results


def render_admissions(results: list[AdmissionResult]) -> str:
    """A readable DependencyGate report: each package, its verdict, and any refusals."""
    lines = ["DEPENDENCY GATE -- admission control for new packages", ""]
    for r in results:
        mark = "[x]" if r.admitted else "[ ]"
        lines.append(
            f"  {mark} {r.package} {r.version}  ({'admitted' if r.admitted else 'REFUSED'})"
        )
        for reason in r.reasons():
            lines.append(f"        -> {reason}")
    admitted = sum(1 for r in results if r.admitted)
    lines += ["", f"  {admitted}/{len(results)} admitted. A refusal blocks the change (FWA04)."]
    return "\n".join(lines)
