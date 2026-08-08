from __future__ import annotations

from pathlib import Path

from kernel.env_parity import (
    ParityReport,
    check_checkout_location,
    check_ci_signals,
    compare_packages,
    run_parity,
)


def _messages(report: ParityReport) -> list[str]:
    return [finding.message for finding in report.findings]


def test_reports_a_package_present_locally_but_not_in_the_ci_install_set() -> None:
    report = compare_packages(
        {"libcst": "1.9.0"},
        {"pytest": "9.0.2"},
    )

    assert any("libcst" in message and "local" in message for message in _messages(report))


def test_reports_a_version_mismatch_for_a_shared_tool() -> None:
    report = compare_packages(
        {"mypy": "2.2.0"},
        {"mypy": "2.3.0"},
    )

    assert any(
        "mypy" in message and "2.2.0" in message and "2.3.0" in message
        for message in _messages(report)
    )


def test_identical_environments_report_clean() -> None:
    report = compare_packages(
        {"PyTest": "9.0.2", "ruff": "0.16.0"},
        {"pytest": "9.0.2", "ruff": "0.16.0"},
    )

    assert report.clean
    assert report.findings == []


def test_reports_a_package_ci_installs_that_is_missing_locally() -> None:
    report = compare_packages(
        {"pytest": "9.0.2"},
        {"pytest": "9.0.2", "mypy": "2.3.0"},
    )

    assert any("mypy" in message and "missing locally" in message for message in _messages(report))


def test_the_gate_reports_and_never_mutates() -> None:
    installer_called = False

    def installer() -> None:
        nonlocal installer_called
        installer_called = True

    report = run_parity(
        local_query=lambda: {"pytest": "9.0.2"},
        ci_query=lambda: {"pytest": "9.0.2"},
        installer=installer,
    )

    assert report.clean
    assert not installer_called


def test_findings_include_a_copy_pasteable_fix_command() -> None:
    report = compare_packages(
        {"libcst": "1.9.0", "pytest": "8.0.0", "duplicate": ("1.0.0", "2.0.0")},
        {"pytest": "9.0.2", "mypy": "2.3.0", "duplicate": "2.0.0"},
    )

    assert report.findings
    assert all(finding.fix_command == "make env" for finding in report.findings)


def test_hostile_package_versions_and_names_are_normalized() -> None:
    report = compare_packages(
        {"My_Package": "2.0.0rc1", "other.package": ("1.0.0", "1.1.0")},
        {"my-package": "2.0.0rc1", "other-package": "1.1.0"},
    )

    assert any("other-package" in message for message in _messages(report))
    assert not any("my-package" in message for message in _messages(report))


def test_checkout_location_drift_is_reported(tmp_path: Path) -> None:
    report = check_checkout_location(
        tmp_path / "worktree" / "codeforge",
        fleet_root=tmp_path / "fleet",
    )

    assert not report.clean
    assert any("checkout location" in message for message in _messages(report))


def test_signal_absence_and_skipping_are_not_passes() -> None:
    report = check_ci_signals({"ci": "success", "codeql": "skipping", "security": "missing"})

    messages = _messages(report)
    assert any("codeql" in message and "skipping" in message for message in messages)
    assert any("security" in message and "missing" in message for message in messages)
