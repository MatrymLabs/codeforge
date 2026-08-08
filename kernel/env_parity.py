"""Report differences between the local environment and the CI dev environment.

This module is deliberately read-only.  It may describe ``make env`` as the
convergence command, but it never invokes an installer.
"""

from __future__ import annotations

import importlib.metadata
import os
import re
import sys
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

FIX_COMMAND = "make env"
PackageValue = str | Sequence[str]
PackageSet = Mapping[str, PackageValue]


@dataclass(frozen=True)
class ParityFinding:
    """One actionable environment parity finding."""

    kind: str
    message: str
    fix_command: str = FIX_COMMAND


@dataclass
class ParityReport:
    """Collected findings and the report-only verdict."""

    findings: list[ParityFinding] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.findings

    def add(self, kind: str, message: str, fix_command: str = FIX_COMMAND) -> None:
        self.findings.append(ParityFinding(kind, message, fix_command))

    def extend(self, other: ParityReport) -> None:
        self.findings.extend(other.findings)

    def render(self) -> str:
        lines = ["ENVIRONMENT PARITY"]
        if self.findings:
            lines.append(f"Findings: {len(self.findings)}")
            for finding in self.findings:
                lines.append(f"- [{finding.kind}] {finding.message}")
                lines.append(f"  Fix: {finding.fix_command}")
            lines.append("Verdict: REPORT ONLY, drift detected")
        else:
            lines.append("Findings: 0")
            lines.append("Verdict: CLEAN")
        return "\n".join(lines)


def _canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).casefold()


def _versions(value: PackageValue) -> set[str]:
    if isinstance(value, str):
        return {value}
    return {str(version) for version in value}


def _normalized_packages(packages: PackageSet) -> dict[str, set[str]]:
    normalized: dict[str, set[str]] = {}
    for name, versions in packages.items():
        normalized.setdefault(_canonical_name(name), set()).update(_versions(versions))
    return normalized


def compare_packages(local: PackageSet, ci: PackageSet) -> ParityReport:
    """Compare installed package names and versions without changing either set."""
    local_versions = _normalized_packages(local)
    ci_versions = _normalized_packages(ci)
    report = ParityReport()

    for name in sorted(local_versions.keys() - ci_versions.keys()):
        report.add("extras-drift", f"{name} is present locally but absent from the CI install set")
    for name in sorted(ci_versions.keys() - local_versions.keys()):
        report.add("missing-package", f"{name} is installed by CI but missing locally")
    for name in sorted(local_versions.keys() & ci_versions.keys()):
        local_found = sorted(local_versions[name])
        ci_found = sorted(ci_versions[name])
        if len(local_found) > 1:
            report.add(
                "duplicate-package",
                f"{name} has multiple local versions: {', '.join(local_found)}",
            )
        if local_versions[name] != ci_versions[name]:
            report.add(
                "version-drift",
                f"{name} version differs: local {', '.join(local_found)}; CI {', '.join(ci_found)}",
            )
    return report


def check_interpreter(local_minor: tuple[int, int], ci_minor: tuple[int, int]) -> ParityReport:
    report = ParityReport()
    if local_minor != ci_minor:
        report.add(
            "interpreter-drift",
            f"Python minor version differs: local {local_minor[0]}.{local_minor[1]}; "
            f"CI {ci_minor[0]}.{ci_minor[1]}",
        )
    return report


def check_checkout_location(repo_root: Path, fleet_root: Path | None = None) -> ParityReport:
    """Check the parent-directory convention used to discover the fleet root."""
    repo_parent = repo_root.resolve().parent
    report = ParityReport()
    if fleet_root is not None:
        expected = fleet_root.resolve()
        if repo_parent != expected:
            report.add(
                "checkout-location-drift",
                f"checkout location differs: repo parent {repo_parent}; "
                f"expected fleet root {expected}",
                "FLEET_ROOT=/path/to/MatrymLabs make env-parity",
            )
        return report
    if not (repo_parent / "hardware-store").is_dir():
        report.add(
            "checkout-location-drift",
            f"checkout location cannot discover the fleet root from {repo_parent}",
            "FLEET_ROOT=/path/to/MatrymLabs make env-parity",
        )
    return report


def check_ci_signals(signals: Mapping[str, str | None]) -> ParityReport:
    """Classify CI results so skipped or absent signals never count as success."""
    report = ParityReport()
    for name, raw_status in sorted(signals.items()):
        status = (raw_status or "missing").casefold()
        if status != "success":
            report.add("signal-absence", f"CI signal {name} is {status}, not success")
    return report


def run_parity(
    *,
    local_query: Callable[[], PackageSet],
    ci_query: Callable[[], PackageSet],
    installer: Callable[[], None] | None = None,
) -> ParityReport:
    """Query both environments and compare them; ``installer`` is never called."""
    del installer
    return compare_packages(local_query(), ci_query())


def installed_packages() -> dict[str, PackageValue]:
    """Return all installed distributions, preserving duplicate versions."""
    found: dict[str, list[str]] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if name:
            found.setdefault(name, []).append(distribution.version)
    return {
        name: versions[0] if len(set(versions)) == 1 else tuple(versions)
        for name, versions in found.items()
    }


def _marker_applies(marker: str, environment: Mapping[str, str]) -> bool:
    """Evaluate the small marker vocabulary emitted by this repository's lockfile."""
    for alternative in marker.split(" or "):
        terms = [term.strip(" ()") for term in alternative.split(" and ")]
        if all(_marker_term_applies(term, environment) for term in terms):
            return True
    return False


def _marker_term_applies(term: str, environment: Mapping[str, str]) -> bool:
    match = re.fullmatch(r"([A-Za-z_]+)\s*(==|!=|>=|<=|>|<|in|not in)\s*'([^']+)'", term)
    if match is None:
        return True
    key, operator, expected = match.groups()
    actual = environment.get(key, "")
    if operator == "==":
        return actual == expected
    if operator == "!=":
        return actual != expected
    if operator == "in":
        return actual in expected
    if operator == "not in":
        return actual not in expected
    if key == "python_full_version":
        actual_value = tuple(int(part) for part in re.findall(r"\d+", actual)[:3])
        expected_value = tuple(int(part) for part in re.findall(r"\d+", expected)[:3])
        return {
            ">=": actual_value >= expected_value,
            "<=": actual_value <= expected_value,
            ">": actual_value > expected_value,
            "<": actual_value < expected_value,
        }[operator]
    return True


def locked_ci_packages(lock_path: Path) -> dict[str, PackageValue]:
    """Resolve the root package plus its ``.[dev]`` dependency closure from uv.lock."""
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    records = cast(list[dict[str, Any]], lock.get("package", []))
    by_name: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        name = str(record["name"])
        by_name.setdefault(_canonical_name(name), []).append(record)

    root_records = by_name.get("codeforge", [])
    if not root_records:
        return {}
    root: dict[str, Any] = root_records[0]
    environment = {
        "sys_platform": sys.platform,
        "platform_machine": os.uname().machine,
        "platform_python_implementation": sys.implementation.name,
        "python_full_version": "3.13.0",
    }
    queue: list[str] = []
    for dependency in root.get("dependencies", []):
        queue.append(str(dependency["name"]))
    optional = cast(dict[str, list[dict[str, Any]]], root.get("optional-dependencies", {}))
    for dependency in optional.get("dev", []):
        queue.append(str(dependency["name"]))

    selected: dict[str, set[str]] = {"codeforge": {str(root["version"])}}
    while queue:
        requested = queue.pop(0)
        key = _canonical_name(requested)
        for record in by_name.get(key, []):
            selected.setdefault(key, set()).add(str(record["version"]))
            for dependency in record.get("dependencies", []):
                if not isinstance(dependency, dict):
                    continue
                marker = dependency.get("marker")
                if marker is None or _marker_applies(str(marker), environment):
                    queue.append(str(dependency["name"]))
    return {
        name: tuple(sorted(versions)) if len(versions) > 1 else next(iter(versions))
        for name, versions in selected.items()
    }


def _ci_python_minor(workflow_dir: Path) -> tuple[int, int] | None:
    versions: set[tuple[int, int]] = set()
    for workflow in workflow_dir.glob("*.yml"):
        for major, minor in re.findall(
            r"python-version:\s*[\"']?(\d+)\.(\d+)", workflow.read_text(encoding="utf-8")
        ):
            versions.add((int(major), int(minor)))
    if len(versions) == 1:
        return next(iter(versions))
    return None


def build_report(repo_root: Path) -> ParityReport:
    report = run_parity(
        local_query=installed_packages,
        ci_query=lambda: locked_ci_packages(repo_root / "uv.lock"),
    )
    ci_minor = _ci_python_minor(repo_root / ".github" / "workflows")
    if ci_minor is not None:
        report.extend(check_interpreter(sys.version_info[:2], ci_minor))
    fleet_root = os.environ.get("FLEET_ROOT")
    report.extend(check_checkout_location(repo_root, Path(fleet_root) if fleet_root else None))
    return report


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    report = build_report(repo_root)
    print(report.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
