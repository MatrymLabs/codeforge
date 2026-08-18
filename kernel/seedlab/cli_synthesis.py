"""CARD: cli_synthesis -- bind the CLI target to the reverse-TDD harness: behavioral acceptance
cases -> spec-derived tests -> implement-until-green -> a VERIFIED CLI (not a self-affirming stub).

The scaffold generator (kernel/seedlab/cli_generator.py) emits a runnable argparse CLI whose every
subcommand prints "<cmd>: ok" and whose test only asserts the exit code -- a self-affirming shape
that proves the target RUNS, never that it does the right thing. This module is the verified path:
the caller states BEHAVIORAL cases (argv -> expected stdout + exit), those become tests that BITE
(they assert real output), and the synthesis harness drives an Implementer until a `cli.py` meets
them -- returning a SynthesisResult verdict (VERIFIED / TESTS_TOO_WEAK / RED_BUDGET_EXHAUSTED /
REFUSED), never a bare "generated".

The tests are the acceptance criteria and are FIXED; only the source changes. Because the cases are
independent (two `greet` cases with different names, say), a stub that hard-codes one answer fails
the others -- so the suite genuinely bites where the scaffold's self-affirming test could not.

Domain-neutral within the platform (grammar before worlds): this knows about a CLI target and the
harness seams, but never imports kernel/world/ or a domain module. The Implementer is injected (the
real Claude one is adapters/synthesis_ai.py; a fake proves this offline). Status: PROTOTYPED.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from kernel.seedlab.cli_generator import GeneratorError
from kernel.seedlab.project_model import ProjectModel
from kernel.seedlab.synthesis import (
    Implementer,
    MutationScorer,
    SynthesisResult,
    TargetFiles,
    TestRun,
    pytest_runner,
    synthesize,
)

#: The single source module the synthesized CLI must provide (the acceptance tests import from it).
_CLI_MODULE = "cli"

#: Emitted with the tests so `cli.py` at the target root is importable when pytest runs.
_CONFTEST = "import pathlib\nimport sys\n\nsys.path.insert(0, str(pathlib.Path(__file__).parent))\n"


@dataclass(frozen=True)
class CliAcceptanceCase:
    """One behavioral acceptance case for a CLI: run `main(argv)`, and it must print exactly
    `expected_stdout` and return `expected_exit`. The spec, stated as observable behavior."""

    argv: tuple[str, ...]
    expected_stdout: str
    expected_exit: int = 0


def cli_acceptance_tests(model: ProjectModel, cases: Sequence[CliAcceptanceCase]) -> TargetFiles:  # noqa: ARG001
    """Emit spec-derived tests (NOT self-affirming): one per case, each asserting the CLI's real
    stdout and exit code via capsys. Fails loud on no cases -- an empty suite is a vacuous pass."""
    if not cases:
        raise GeneratorError("cli synthesis needs at least one acceptance case to verify")
    blocks = [f"from {_CLI_MODULE} import main"]
    for i, case in enumerate(cases):
        argv = json.dumps(list(case.argv))
        out = json.dumps(case.expected_stdout)
        blocks.append(
            f"\n\ndef test_case_{i}(capsys):\n"
            f"    code = main({argv})\n"
            f"    captured = capsys.readouterr()\n"
            f"    assert code == {int(case.expected_exit)}\n"
            f"    assert captured.out == {out}\n"
        )
    return {
        "conftest.py": _CONFTEST,
        "tests/test_cli_acceptance.py": "".join(blocks) + "\n",
    }


def cli_goal(model: ProjectModel, cases: Sequence[CliAcceptanceCase]) -> str:
    """The natural-language spec the Implementer reads alongside the tests: build a `cli.py` with
    `main(argv=None) -> int` for the project, and satisfy each behavioral case."""
    lines = [
        f"Build a Python CLI for the project '{model.identity}'.",
        f"Provide a module `{_CLI_MODULE}.py` exposing `main(argv=None) -> int` "  # noqa: ISC004
        "(argv defaults to sys.argv[1:]). It must satisfy these behavioral cases:",
    ]
    for case in cases:
        lines.append(
            f"  - run with argv {list(case.argv)!r}: print exactly {case.expected_stdout!r} "
            f"and return {int(case.expected_exit)}"
        )
    lines.append("Write real logic, not hard-coded outputs; do not modify the tests.")
    return "\n".join(lines)


def synthesize_cli(
    model: ProjectModel,
    cases: Sequence[CliAcceptanceCase],
    implementer: Implementer,
    *,
    workdir: Path,
    run: TestRun | None = None,
    scorer: MutationScorer | None = None,
    max_iterations: int = 3,
    mutation_threshold: float = 0.70,
) -> SynthesisResult:
    """Compose the CLI acceptance spec with the synthesis harness: derive biting tests + a goal from
    `cases`, then drive `implementer` to green (optionally gated on mutation). Returns the harness's
    verdict. Fails loud (GeneratorError) on an empty identity or no cases -- there is nothing to
    verify. `run` defaults to the real pytest runner; inject a fake to test the compose offline."""
    if not model.identity or not model.identity.strip():
        raise GeneratorError("a project model needs a non-empty identity to synthesize a CLI")
    tests = cli_acceptance_tests(model, cases)  # raises loud if no cases
    goal = cli_goal(model, cases)
    test_run = run if run is not None else pytest_runner(seed_id="_cli_synthesis")
    return synthesize(
        goal,
        tests,
        implementer,
        run=test_run,
        workdir=Path(workdir),
        scorer=scorer,
        max_iterations=max_iterations,
        mutation_threshold=mutation_threshold,
    )
