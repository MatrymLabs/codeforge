"""Contract tests for the calibration harness's case selector."""

from __future__ import annotations

import sys

from scripts import calibrate_gates


def _run_main(monkeypatch, *args: str) -> None:
    monkeypatch.setattr(sys, "argv", ["calibrate_gates.py", *args])
    calibrate_gates.main()


def test_unknown_only_name_refuses_and_explains_available_cases(monkeypatch, capsys) -> None:
    _run_main(monkeypatch, "--only", "zzz-no-such-case-exists")
    output = capsys.readouterr().out
    assert "zzz-no-such-case-exists" in output
    assert "mypy-strict-type-error" in output


def test_unknown_only_name_returns_nonzero(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["calibrate_gates.py", "--only", "missing-case"])
    assert calibrate_gates.main() != 0


def test_real_only_name_still_runs_exactly_one_case(monkeypatch, capsys) -> None:
    seen: list[str] = []

    def fake_calibrate(case: calibrate_gates.Case) -> tuple[str, str]:
        seen.append(case.name)
        return calibrate_gates.PASS, "controlled proof"

    monkeypatch.setattr(calibrate_gates, "calibrate", fake_calibrate)
    _run_main(monkeypatch, "--only", "mypy-strict-type-error")
    output = capsys.readouterr().out
    assert seen == ["mypy-strict-type-error"]
    assert "[PASS] mypy-strict-type-error" in output


def test_absent_toolchain_skip_stays_green(monkeypatch, capsys) -> None:
    case = calibrate_gates.Case(
        name="missing-tool-calibration",
        gate=["never-run"],
        probe="unused-probe",
        violation="unused-violation",
        signal="unused-signal",
        needs=("tool-that-is-not-installed-for-this-test",),
    )
    monkeypatch.setattr(calibrate_gates, "CASES", [case])
    _run_main(monkeypatch)
    output = capsys.readouterr().out
    assert "[SKIP] missing-tool-calibration" in output


def test_unfiltered_empty_case_list_remains_green(monkeypatch, capsys) -> None:
    monkeypatch.setattr(calibrate_gates, "CASES", [])
    _run_main(monkeypatch)
    output = capsys.readouterr().out
    assert "0 calibrated, 0 FAILED, 0 skipped" in output
