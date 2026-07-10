"""CARD: dependencies -- the dependency gate: every dependency earns its place.

The Dependency Approval Rule (docs/tooling_strategy.md) made machine-checkable. It reads the
declared dependencies from pyproject.toml and the justifications from dependency_ledger.toml,
then reports every dependency that is declared but unjustified (a FAIL) or justified but no
longer declared (a stale WARN). Frameless discipline: stdlib only (tomllib), no new dep to
police the deps. It mutates nothing; it reports a verdict. `make deps` runs it; the test twin
rides `make check`, so an unjustified dependency cannot merge silently.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PYPROJECT = _ROOT / "pyproject.toml"
_LEDGER = _ROOT / "dependency_ledger.toml"
_REQUIRED_FIELDS = ("why", "stdlib_alternative", "removable")


class LedgerError(RuntimeError):
    """A malformed ledger or pyproject fails loud, never silently passes."""


def _canonical(name: str) -> str:
    """PEP 503 normalize + strip extras/version markers: 'bandit[toml]>=1' -> 'bandit'."""
    head = re.split(r"[<>=!~;\[ ]", name.strip(), maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", head).lower()


@dataclass(frozen=True)
class Declared:
    """The dependencies pyproject.toml actually asks for, canonicalized."""

    runtime: frozenset[str]
    dev: frozenset[str]

    @property
    def all(self) -> frozenset[str]:
        return self.runtime | self.dev


def read_declared(path: Path = _PYPROJECT) -> Declared:
    """Parse the runtime + dev dependency names from pyproject.toml (fails loud if absent)."""
    if not path.is_file():
        raise LedgerError(f"pyproject not found: {path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    optional = project.get("optional-dependencies", {})
    runtime = {_canonical(x) for x in project.get("dependencies", [])}
    # Optional FEATURE extras (e.g. `ai`) are runtime capabilities, not dev tooling: they
    # still earn their place, so fold every non-dev extra into the runtime set the gate audits.
    for group, items in optional.items():
        if group == "dev":
            continue
        runtime |= {_canonical(x) for x in items}
    dev = {_canonical(x) for x in optional.get("dev", [])}
    return Declared(frozenset(runtime), frozenset(dev))


def read_ledger(path: Path = _LEDGER) -> dict[str, dict[str, str]]:
    """Parse the justification rows; a missing file or an incomplete row fails loud."""
    if not path.is_file():
        raise LedgerError(f"dependency ledger not found: {path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    entries: dict[str, dict[str, str]] = {}
    for scope in ("runtime", "dev"):
        for name, row in data.get(scope, {}).items():
            if not isinstance(row, dict):
                raise LedgerError(f"[{scope}.{name}] must be a table of justification fields")
            missing = [f for f in _REQUIRED_FIELDS if not str(row.get(f, "")).strip()]
            if missing:
                raise LedgerError(
                    f"[{scope}.{name}] missing required field(s): {', '.join(missing)}"
                )
            entries[_canonical(name)] = {
                "scope": scope,
                **{f: str(row[f]) for f in _REQUIRED_FIELDS},
            }
    return entries


@dataclass(frozen=True)
class DependencyAudit:
    """The verdict: what is justified, what is unjustified (FAIL), what is stale (WARN)."""

    ok: tuple[str, ...]
    unjustified: tuple[str, ...]
    stale: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.unjustified


def audit_dependencies(pyproject: Path = _PYPROJECT, ledger: Path = _LEDGER) -> DependencyAudit:
    """Compare declared deps against the ledger; unjustified declarations fail the gate."""
    declared = read_declared(pyproject)
    filed = set(read_ledger(ledger))
    return DependencyAudit(
        ok=tuple(sorted(declared.all & filed)),
        unjustified=tuple(sorted(declared.all - filed)),
        stale=tuple(sorted(filed - declared.all)),
    )


def format_audit(audit: DependencyAudit) -> str:
    """Render the verdict for a human (the `make deps` readout / `terminal deps`)."""
    verdict = "PASS" if audit.passed else "FAIL"
    lines = [
        "DEPENDENCY GATE - every dependency earns its place (frameless Python)",
        f"  {len(audit.ok)} justified, {len(audit.unjustified)} unjustified, "
        f"{len(audit.stale)} stale  ->  {verdict}",
        "",
    ]
    if audit.unjustified:
        lines.append("  UNJUSTIFIED (declared in pyproject, no ledger row):")
        lines += [
            f"    - {name}  (add a row to dependency_ledger.toml)" for name in audit.unjustified
        ]
        lines.append("")
    if audit.stale:
        lines.append("  STALE (ledger row, no longer declared):")
        lines += [
            f"    - {name}  (remove its row from dependency_ledger.toml)" for name in audit.stale
        ]
        lines.append("")
    if audit.passed and not audit.stale:
        lines.append("  Every declared dependency has a justification. The ledger is clean.")
    return "\n".join(lines).rstrip() + "\n"


def render_dependencies(pyproject: Path = _PYPROJECT, ledger: Path = _LEDGER) -> str:
    """The gate's human report (used by `make deps` and the in-game terminal)."""
    return format_audit(audit_dependencies(pyproject, ledger))


def main(argv: list[str] | None = None) -> int:
    """`make deps`: print the verdict; exit non-zero if any dependency is unjustified."""
    try:
        audit = audit_dependencies()
    except LedgerError as exc:
        print(f"dependency gate: {exc}")
        return 2
    print(format_audit(audit))
    return 0 if audit.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
