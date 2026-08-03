"""Test twin for kernel/seedlab/cli_synthesis.py -- binding the CLI target to the synthesis harness.

Acceptance: behavioral cases (argv -> expected stdout + exit) become tests that BITE; a correct
Implementer is driven to a VERIFIED verdict over REAL pytest; the emitted tests and goal carry the
observable behavior. The key contrast with the scaffold generator: a stub that prints "<cmd>: ok"
(the shape cli_generator emits) FAILS the acceptance suite -- proving these tests verify real logic
where the scaffold's self-affirming exit-code test could not.

Refusal (fail loud): no acceptance cases is a GeneratorError (an empty suite is a vacuous pass), and
an empty model identity is a GeneratorError (nothing to synthesize). Offline throughout with fakes,
plus one end-to-end run over the real runner.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.seedlab.cli_generator import GeneratorError
from kernel.seedlab.cli_synthesis import (
    CliAcceptanceCase,
    cli_acceptance_tests,
    cli_goal,
    synthesize_cli,
)
from kernel.seedlab.project_model import ProjectModel, Provenance
from kernel.seedlab.synthesis import (
    RED_BUDGET_EXHAUSTED,
    VERIFIED,
    TargetFiles,
)

_MODEL = ProjectModel(identity="greeter", provenance=Provenance("spec", owner="josh"))

# Independent cases: two greet names + an add. A hard-coded single answer can't satisfy all three.
_CASES = (
    CliAcceptanceCase(argv=("greet", "Ada"), expected_stdout="Hello, Ada!\n"),
    CliAcceptanceCase(argv=("greet", "Bo"), expected_stdout="Hello, Bo!\n"),
    CliAcceptanceCase(argv=("add", "2", "3"), expected_stdout="5\n"),
)


class _CorrectImplementer:
    """Stand-in for the real Claude Implementer: emits a `cli.py` with genuine dispatch logic that
    satisfies every case. The FIXED acceptance tests are what force this correctness."""

    def implement(self, goal: str, tests: TargetFiles, feedback: str) -> TargetFiles:
        return {
            "cli.py": (
                "import sys\n\n\n"
                "def main(argv=None):\n"
                "    argv = list(sys.argv[1:] if argv is None else argv)\n"
                "    if not argv:\n"
                "        return 0\n"
                "    cmd, *rest = argv\n"
                "    if cmd == 'greet':\n"
                "        print(f'Hello, {rest[0]}!')\n"
                "        return 0\n"
                "    if cmd == 'add':\n"
                "        print(sum(int(x) for x in rest))\n"
                "        return 0\n"
                "    return 1\n"
            )
        }


class _StubImplementer:
    """Emits the SCAFFOLD shape cli_generator produces: every command prints '<cmd>: ok'. It passes
    a self-affirming exit-code test but FAILS a behavioral acceptance suite -- the whole point."""

    def implement(self, goal: str, tests: TargetFiles, feedback: str) -> TargetFiles:
        return {
            "cli.py": (
                "import sys\n\n\n"
                "def main(argv=None):\n"
                "    argv = list(sys.argv[1:] if argv is None else argv)\n"
                "    if not argv:\n"
                "        return 0\n"
                "    print(f'{argv[0]}: ok')\n"
                "    return 0\n"
            )
        }


# --- unit: the emitted tests + goal carry the behavior --------------------------------------------


def test_acceptance_tests_assert_real_stdout_and_exit() -> None:
    files = cli_acceptance_tests(_MODEL, _CASES)
    body = files["tests/test_cli_acceptance.py"]
    assert "from cli import main" in body
    assert 'main(["greet", "Ada"])' in body
    assert 'captured.out == "Hello, Ada!\\n"' in body  # asserts real output, not just exit
    assert "conftest.py" in files


def test_no_cases_is_refused_loud() -> None:
    with pytest.raises(GeneratorError):
        cli_acceptance_tests(_MODEL, ())


def test_goal_states_the_module_and_the_cases() -> None:
    goal = cli_goal(_MODEL, _CASES)
    assert "cli.py" in goal and "greeter" in goal
    assert "Hello, Ada!" in goal  # the behavioral case reaches the implementer's brief


# --- integration: the compose over REAL pytest ---------------------------------------------------


def test_correct_implementer_reaches_verified(tmp_path: Path) -> None:
    result = synthesize_cli(_MODEL, _CASES, _CorrectImplementer(), workdir=tmp_path)
    assert result.verdict == VERIFIED  # real pytest went green on genuine logic
    assert result.ok is True
    assert "Hello" in (tmp_path / "cli.py").read_text(encoding="utf-8")


def test_the_scaffold_stub_fails_the_biting_suite(tmp_path: Path) -> None:
    # The scaffold's '<cmd>: ok' output does NOT match "Hello, Ada!": the acceptance suite bites.
    result = synthesize_cli(_MODEL, _CASES, _StubImplementer(), workdir=tmp_path, max_iterations=2)
    assert result.verdict == RED_BUDGET_EXHAUSTED


# --- refusal: fail loud on nothing to verify -----------------------------------------------------


def test_empty_identity_is_refused_loud(tmp_path: Path) -> None:
    blank = ProjectModel(identity="   ", provenance=Provenance("spec"))
    with pytest.raises(GeneratorError):
        synthesize_cli(blank, _CASES, _CorrectImplementer(), workdir=tmp_path)


def test_no_cases_through_synthesize_is_refused_loud(tmp_path: Path) -> None:
    with pytest.raises(GeneratorError):
        synthesize_cli(_MODEL, (), _CorrectImplementer(), workdir=tmp_path)
