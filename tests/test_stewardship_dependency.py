"""Test twin for the DependencyGate (parts/stewardship/dependency.py).

Acceptance: an existing, ledger-approved, vuln-free, permissively-licensed package is admitted.
Refusal (each FWA failure mode): a non-existent package (hallucination/typosquat), an
unapproved package, a package with a critical CVE, and a copyleft-licensed package each refused
-- with visible reasons. The external lookups run through an offline StaticOracle (no network).
"""

from __future__ import annotations

from parts.stewardship.dependency import (
    StaticOracle,
    admit_dependency,
    all_admitted,
    ledger_packages,
    render_admissions,
)

_ALLOWLIST = {"good-pkg", "risky-pkg", "gpl-pkg"}
_ORACLE = StaticOracle(
    known=frozenset({"good-pkg", "risky-pkg", "gpl-pkg"}),
    vulns={"risky-pkg": 3},
    licenses={"good-pkg": "MIT", "risky-pkg": "MIT", "gpl-pkg": "GPL-3.0"},
)


def _admit(pkg: str, version: str = "1.0.0"):
    return admit_dependency(pkg, version, allowlist=_ALLOWLIST, oracle=_ORACLE)


def test_a_clean_package_is_admitted() -> None:
    result = _admit("good-pkg")
    assert result.admitted and result.reasons() == []


def test_a_non_existent_package_is_refused_as_a_hallucination() -> None:
    result = _admit("totally-made-up-lib")
    assert not result.admitted
    assert any(r.startswith("DEP01") for r in result.reasons())  # does not exist


def test_an_unapproved_package_is_refused() -> None:
    # Exists on the index, but not filed in the dependency ledger.
    oracle = StaticOracle(known=frozenset({"sneaky-pkg"}), licenses={"sneaky-pkg": "MIT"})
    result = admit_dependency("sneaky-pkg", "1.0", allowlist=set(), oracle=oracle)
    assert not result.admitted
    assert any(r.startswith("DEP02") for r in result.reasons())  # not in the ledger


def test_a_vulnerable_package_is_refused() -> None:
    result = _admit("risky-pkg")
    assert not result.admitted
    assert any(r.startswith("DEP03") for r in result.reasons())  # critical CVEs


def test_a_copyleft_license_is_refused() -> None:
    result = _admit("gpl-pkg")
    assert not result.admitted
    assert any(r.startswith("DEP04") for r in result.reasons())  # license not allowed


def test_the_ledger_is_the_allowlist() -> None:
    # ledger_packages reads the real dependency_ledger.toml; known deps are present.
    packages = ledger_packages()
    assert "pyyaml" in packages and "sqlalchemy" in packages


def test_a_missing_ledger_yields_an_empty_allowlist() -> None:
    from pathlib import Path

    assert ledger_packages(Path("/no/such/dependency_ledger.toml")) == set()


def test_all_admitted_reports_the_mix() -> None:
    ok, results = all_admitted(
        [("good-pkg", "1.0"), ("risky-pkg", "1.0")], allowlist=_ALLOWLIST, oracle=_ORACLE
    )
    assert ok is False  # one vulnerable package fails the batch
    assert len(results) == 2
    out = render_admissions(results)
    assert "DEPENDENCY GATE" in out and "REFUSED" in out and "FWA04" in out


def test_a_real_ledger_package_admits_through_the_actual_allowlist() -> None:
    # End-to-end with the real ledger allowlist + an offline oracle for the external lookups.
    oracle = StaticOracle(known=frozenset({"pyyaml"}), licenses={"pyyaml": "MIT"})
    result = admit_dependency("PyYAML", "6.0", allowlist=ledger_packages(), oracle=oracle)
    assert result.admitted  # case-insensitive: 'PyYAML' -> 'pyyaml' matches the ledger
