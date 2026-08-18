"""Test twin for kernel/tools_registry.py.

The load-bearing case is the REFUSAL of a version check dressed as a proof. A registry that
accepts `mytool --version` as evidence a tool works is the same document we already had, with
more fields. Every other test here protects that one from being quietly disabled.
"""

from __future__ import annotations

from pathlib import Path

from kernel.tools_registry import REQUIRED_FIELDS, inspect

_GOOD = """
[[tool]]
tool_id = "ruff"
executable = "$(PY) -m ruff"
version_command = "ruff --version"
proof_command = "make lint-python"
supported_inputs = ["*.py"]
supported_outputs = ["lint findings"]
language_lanes = ["python"]
known_faults = "none observed"
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "tools_registry.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_complete_record_registers(tmp_path: Path) -> None:
    verdict = inspect(_write(tmp_path, _GOOD))
    assert verdict.clean, verdict.render()
    assert verdict.registered == ["ruff"]


def test_a_version_check_is_refused_as_a_proof_command(tmp_path: Path) -> None:
    """The rule the whole file exists for. `--version` proves installed, never working, and this
    ship has been caught by that distinction three times in one week."""
    verdict = inspect(_write(tmp_path, _GOOD.replace('"make lint-python"', '"ruff --version"')))
    assert not verdict.clean
    assert any("VERSION CHECK" in f for f in verdict.findings)


def test_a_compound_version_check_is_also_refused(tmp_path: Path) -> None:
    """`go version && golangci-lint --version` is still nothing but version checks."""
    proof = '"go version && golangci-lint --version"'
    verdict = inspect(_write(tmp_path, _GOOD.replace('"make lint-python"', proof)))
    assert not verdict.clean
    assert any("VERSION CHECK" in f for f in verdict.findings)


def test_a_proof_that_does_real_work_passes_even_beside_a_version_check(tmp_path: Path) -> None:
    """The refusal must not overreach: one real command in the chain is a real proof."""
    proof = '"./gradlew --version && make lint-kotlin"'
    verdict = inspect(_write(tmp_path, _GOOD.replace('"make lint-python"', proof)))
    assert verdict.clean, verdict.render()


def test_every_required_field_is_actually_required(tmp_path: Path) -> None:
    """Each field removed in turn, so no field can be dropped from the schema unnoticed."""
    for field in REQUIRED_FIELDS:
        body = "\n".join(ln for ln in _GOOD.splitlines() if not ln.startswith(f"{field} ="))
        verdict = inspect(_write(tmp_path, body))
        assert not verdict.clean, f"{field} was removed and the registry still passed"
        assert any(field in f for f in verdict.findings)


def test_blank_known_faults_is_refused(tmp_path: Path) -> None:
    """ "none observed" is an answer. Silence is not."""
    verdict = inspect(_write(tmp_path, _GOOD.replace('"none observed"', '""')))
    assert not verdict.clean
    assert any("known_faults" in f for f in verdict.findings)


def test_a_duplicate_tool_id_is_caught(tmp_path: Path) -> None:
    verdict = inspect(_write(tmp_path, _GOOD + _GOOD))
    assert not verdict.clean
    assert any("duplicate" in f for f in verdict.findings)


def test_a_missing_registry_is_a_finding_not_a_crash(tmp_path: Path) -> None:
    verdict = inspect(tmp_path / "nope.toml")
    assert not verdict.clean
    assert any("does not exist" in f for f in verdict.findings)


def test_malformed_toml_fails_loud(tmp_path: Path) -> None:
    verdict = inspect(_write(tmp_path, "[[tool]\nbroken"))
    assert not verdict.clean
    assert any("not valid TOML" in f for f in verdict.findings)


def test_the_real_registry_passes_its_own_gate() -> None:
    """The calibration against reality: the shipped registry must satisfy the rules it defines."""
    verdict = inspect()
    assert verdict.clean, verdict.render()
    assert len(verdict.registered) >= 8
