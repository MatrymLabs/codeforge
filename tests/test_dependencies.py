"""Test twin for parts/dependencies.py -- the dependency gate.

Acceptance: the real repo is clean (every declared dependency is justified). Refusal:
an unjustified dependency fails, an incomplete ledger row fails loud, a stale row warns,
and missing files fail loud. This test rides `make check`, so an unjustified dependency
cannot merge silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts.dependencies import (
    LedgerError,
    _canonical,
    audit_dependencies,
    read_declared,
    read_ledger,
    render_dependencies,
)

_GOOD_ROW = 'why = "w"\nstdlib_alternative = "s"\nremovable = "r"\n'


def _write(tmp_path: Path, pyproject: str, ledger: str) -> tuple[Path, Path]:
    p = tmp_path / "pyproject.toml"
    lg = tmp_path / "ledger.toml"
    p.write_text(pyproject, encoding="utf-8")
    lg.write_text(ledger, encoding="utf-8")
    return p, lg


# ----- acceptance: the shipped repo passes its own gate --------------------------------
def test_the_real_repo_has_no_unjustified_dependencies() -> None:
    audit = audit_dependencies()  # defaults to the repo's pyproject + ledger
    assert audit.passed, f"unjustified dependencies: {audit.unjustified}"
    assert not audit.stale, f"stale ledger rows: {audit.stale}"
    assert audit.ok, "expected at least one justified dependency"


def test_canonical_strips_extras_and_version_markers() -> None:
    assert _canonical("bandit[toml]>=1.7") == "bandit"
    assert _canonical("types-PyYAML") == "types-pyyaml"
    assert _canonical("pytest_cov") == "pytest-cov"


# ----- refusal: unjustified declaration fails the gate ---------------------------------
def test_an_unjustified_dependency_fails(tmp_path: Path) -> None:
    p, lg = _write(
        tmp_path,
        '[project]\ndependencies = ["pyyaml", "requests"]\n',
        f"[runtime.pyyaml]\n{_GOOD_ROW}",  # requests has no row
    )
    audit = audit_dependencies(p, lg)
    assert not audit.passed
    assert "requests" in audit.unjustified


def test_a_stale_ledger_row_warns_but_does_not_fail(tmp_path: Path) -> None:
    p, lg = _write(
        tmp_path,
        '[project]\ndependencies = ["pyyaml"]\n',
        f"[runtime.pyyaml]\n{_GOOD_ROW}\n[runtime.olddep]\n{_GOOD_ROW}",
    )
    audit = audit_dependencies(p, lg)
    assert audit.passed  # stale is a warning, not a failure
    assert "olddep" in audit.stale


def test_an_incomplete_ledger_row_fails_loud(tmp_path: Path) -> None:
    p, lg = _write(
        tmp_path,
        '[project]\ndependencies = ["pyyaml"]\n',
        '[runtime.pyyaml]\nwhy = "w"\n',  # missing stdlib_alternative + removable
    )
    with pytest.raises(LedgerError, match="missing required field"):
        audit_dependencies(p, lg)


def test_a_missing_pyproject_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(LedgerError, match="pyproject not found"):
        read_declared(tmp_path / "nope.toml")


def test_a_missing_ledger_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(LedgerError, match="ledger not found"):
        read_ledger(tmp_path / "nope.toml")


def test_dev_extras_are_counted_as_declared(tmp_path: Path) -> None:
    p, lg = _write(
        tmp_path,
        '[project]\ndependencies = []\n[project.optional-dependencies]\ndev = ["ruff"]\n',
        f"[dev.ruff]\n{_GOOD_ROW}",
    )
    declared = read_declared(p)
    assert "ruff" in declared.dev
    assert audit_dependencies(p, lg).passed


def test_render_shows_the_verdict() -> None:
    out = render_dependencies()
    assert "DEPENDENCY GATE" in out
    assert "PASS" in out  # the real repo is clean
