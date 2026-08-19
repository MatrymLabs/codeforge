"""Report differences between the local environment and the CI dev environment.

This module is deliberately read-only.  It may describe ``make env`` as the
convergence command, but it never invokes an installer.
"""

from __future__ import annotations

import importlib.metadata
import os
import platform
import re
import subprocess  # nosec B404 - reads the git index, no untrusted input
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
    """Classify CI results so skipped or absent signals never count as success.

    Deliberately NOT part of ``build_report``: reading real CI status needs the network, and this
    gate stays offline. It is the executable form of the fleet rule that a ``skipping`` or absent
    check is not a passing check (a codeql break once hid behind ``skipping`` and reached main),
    for a caller that already holds the statuses. ``make env-parity`` does not report this
    dimension, and the registry record must not claim it does.
    """
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


def _marker_term_applies(term: str, environment: Mapping[str, str]) -> bool:  # noqa: PLR0911
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
        # platform.machine(), not os.uname(): os.uname is POSIX-only and absent on Windows.
        "platform_machine": platform.machine(),
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


def check_platform_divergence(
    default_encoding: str, utf8_mode: str | None, unmarked_scripts: list[str]
) -> ParityReport:
    """Differences between THIS platform and the Linux CI runs on, that nothing else reports.

    Package parity answers "do we have the same libraries". It does not answer "will the same
    command behave the same way", and on 2026-08-17 that gap cost three separate defects, each
    found by a different accident:

      1. `_git` in the stranded gate decoded subprocess output with the process locale (cp1252
         here, UTF-8 in CI). An em dash came back mangled, so a search pattern built from it
         matched nothing and safe content reported as stranded.
      2. The integrity ritual crashed writing its own report, because the report contains a
         checkmark and stdout was cp1252. It could not run on this bench at all, all day.
      3. Nine files carried a shebang without the executable bit. Ruff's EXE001 is SKIPPED on
         Windows, so the bench reported green while CI failed, and no amount of re-running here
         would ever have shown it.

    All three are one thing: the bench cannot see what CI sees, and nothing said so. These checks
    say so. Report-only, like the rest of this module -- it names the divergence and the fix.
    """
    report = ParityReport()
    if default_encoding.lower() not in {"utf-8", "utf8"} and not utf8_mode:
        report.add(
            "encoding-divergence",
            f"default text encoding is {default_encoding!r}, CI runs UTF-8. Subprocess output and "
            f"file writes containing any non-ASCII character will differ from CI, silently",
            "set PYTHONUTF8=1 (the Makefile exports it for every gate target)",
        )
    for path in unmarked_scripts:
        report.add(
            "exec-bit-divergence",
            f"{path} declares a shebang and is not executable in the git index. ruff EXE001 skips "
            f"this check on Windows, so only CI can see it",
            f"git update-index --chmod=+x {path}",
        )
    return report


_MODE_AND_PATH = 2  # `git ls-files -s` emits "<mode> <sha> <stage>	<path>"


def shebang_scripts_missing_exec_bit(repo_root: Path) -> list[str]:
    """Tracked files that claim to be runnable and are not, read from GIT rather than the disk.

    The git index carries the mode, so this answers the same question ruff answers on Linux and
    cannot answer on Windows. Reading the index instead of the filesystem is the whole trick: it
    is the same data CI will check out.
    """
    try:
        listing = subprocess.run(  # nosec B603 B607 - fixed argv, local checkout
            ["git", "ls-files", "-s", "--", "*.py", "*.sh"],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if listing.returncode != 0:
        return []

    unmarked: list[str] = []
    for line in listing.stdout.splitlines():
        parts = line.split("	", 1)
        if len(parts) != _MODE_AND_PATH or not parts[0].startswith("100644"):
            continue
        name = parts[1].strip()
        candidate = repo_root / name
        try:
            first = candidate.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        except OSError:
            continue
        if first and first[0].startswith("#!"):
            unmarked.append(name)
    return unmarked


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
    report.extend(
        check_platform_divergence(
            sys.getdefaultencoding() if sys.stdout.encoding is None else sys.stdout.encoding,
            os.environ.get("PYTHONUTF8"),
            shebang_scripts_missing_exec_bit(repo_root),
        )
    )
    return report


#: The one divergence kind that is not advisory. Everything else this module reports is a
#: difference a human should weigh; this one is a CI failure that has already happened and is
#: merely waiting to be observed.
BLOCKING_KINDS = frozenset({"exec-bit-divergence"})


def main() -> int:
    """Report drift. Exit non-zero ONLY for a divergence that is a certain CI failure.

    This target was REPORT ONLY and returned 0 unconditionally, which was right for most of what
    it finds: a Python minor mismatch or an odd checkout location is a difference to weigh, not a
    defect to block on.

    Exec-bit divergence is not that. On 2026-08-19 a new script with a shebang and no exec bit was
    pushed, and CI died at `lint-python` on `EXE001 Shebang is present but file is not executable`.
    THIS MODULE HAD ALREADY DETECTED IT, named the file, and explained that "ruff EXE001 skips this
    check on Windows, so only CI can see it". Then it exited 0 and the push proceeded.

    A Windows bench CANNOT see EXE001: there is no executable bit to inspect, so ruff skips the
    rule entirely. That makes this check the ONLY thing standing between the bench and a guaranteed
    red on the merge path, and an advisory verdict on a guaranteed failure is the wrong verdict.
    An instrument that knows the answer and shrugs is worth less than one that never looked, because
    it produces a record saying somebody checked.
    """
    repo_root = Path(__file__).resolve().parents[1]
    report = build_report(repo_root)
    print(report.render())
    blocking = [finding for finding in report.findings if finding.kind in BLOCKING_KINDS]
    if blocking:
        print(
            f"\nBLOCKING: {len(blocking)} divergence(s) that CI will certainly fail on. "
            "Everything else above is advisory."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
