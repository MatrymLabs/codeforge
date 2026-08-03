"""CARD: synthesis -- the reverse-TDD generation harness: spec-derived tests -> implement-to-green
-> mutation gate, so a target carries VERIFIED logic instead of a self-affirming scaffold.

NORTH_STAR Gap 1 (business-logic generation with a verification harness). The existing target
generators (kernel/seedlab/cli_generator.py, web_api_generator.py) already run the
generate -> emit-tests -> run -> green skeleton, but they emit "ok"-stubs and tests that assert
only the stub's own shape. This harness is the missing middle: the tests come from a behavioral SPEC
(real acceptance cases), an Implementer produces the source, and the loop runs the tests until they
pass -- then a mutation gate proves the tests actually BITE (a green suite that survives mutants was
too weak to trust).

Domain-neutral (grammar before worlds): this knows about `TargetFiles` (relpath -> content), a spec
that yields tests, an `Implementer` that yields source, a `TestRun` that reports pass/fail, and a
`MutationScorer` -- nothing about CLIs, games, or classrooms. Every boundary is a seam:
  * `Implementer.implement(goal, tests, feedback) -> TargetFiles` -- the code generator. The offline
    fake proves the loop with no network (CI has no ANTHROPIC_API_KEY); the real Claude adapter
    follows the adapters/architect.py Advisor pattern and is a later slice behind the [ai] extra.
  * `TestRun(target_dir) -> ToolRunResult` -- runs the emitted tests under a bound (real one wraps
    kernel/seedlab/tool_runner.run_tool; a fake reports a canned result in unit tests).
  * `MutationScorer.score(target_dir) -> float | None` -- the kill-rate (None = not computable). The
    real one drives cosmic-ray via kernel.mutation_recorder; a fake returns a number in unit tests.

Verdicts, not booleans: VERIFIED (green AND mutation bites), TESTS_TOO_WEAK (green, low kill-rate),
RED_BUDGET_EXHAUSTED (never went green within the iteration budget), REFUSED (an empty goal or no
tests -- there is nothing to verify). Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from kernel.seedlab.tool_runner import ToolRunResult

#: A set of files to write, relpath -> UTF-8 content (both source and tests use this shape).
TargetFiles = dict[str, str]


def pytest_runner(*, seed_id: str = "_synthesize") -> TestRun:
    """The REAL test runner: run the target's pytest suite in its own dir through the Stage-5
    tool_runner (bound cwd, timeout, output cap, argv allowlist), as the generators validate.
    Lazy-imports the world-free seams so importing the harness stays light."""
    import sys

    from kernel.seedlab.project_model import Provenance
    from kernel.seedlab.source_connector import LocalSource
    from kernel.seedlab.tool_runner import run_tool

    def run(target_dir: Path) -> ToolRunResult:
        source = LocalSource(Path(target_dir), Provenance("synthesis", owner="harness"))
        return run_tool(
            source,
            "pytest",
            seed_id=seed_id,
            kind="test",
            allowlist={
                "pytest": [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider"]
            },
        )

    return run


# --- verdict words (a distinct vocabulary: "can we trust this generated target?") --------------
VERIFIED = "verified"  # tests went green AND the mutation gate says they bite
TESTS_TOO_WEAK = "tests_too_weak"  # green, but the mutation kill-rate is below threshold
RED_BUDGET_EXHAUSTED = "red_budget_exhausted"  # never went green within the iteration budget
REFUSED = "refused"  # nothing to verify (empty goal or no tests): fail loud, never a vacuous pass


@runtime_checkable
class Implementer(Protocol):
    """Produces the target's SOURCE files (not the tests) to satisfy the given tests. `feedback` is
    the previous run's failure output ("" on the first attempt) -- the implement-until-green loop
    feeds each red run back so the implementer can converge."""

    def implement(self, goal: str, tests: TargetFiles, feedback: str) -> TargetFiles: ...


@runtime_checkable
class MutationScorer(Protocol):
    """Returns the mutation kill-rate for a target dir (0.0..1.0), or None when not computable (no
    mutants, no run). The gate that proves a green suite actually bites."""

    def score(self, target_dir: Path) -> float | None: ...


#: Runs the emitted tests in `target_dir` under a bound and reports the result (never raises on a
#: failing suite: a non-zero exit is the signal the loop reads).
TestRun = Callable[[Path], ToolRunResult]


@dataclass(frozen=True)
class SynthesisResult:
    """The harness's honest verdict on one synthesis run."""

    verdict: str
    iterations: int  # how many implement attempts were made
    files: TargetFiles = field(default_factory=dict)  # the source the last attempt produced
    run: ToolRunResult | None = None  # the final test run (None if refused before running)
    mutation_score: float | None = None  # the kill-rate if the mutation gate ran

    @property
    def ok(self) -> bool:
        return self.verdict == VERIFIED


def _write(target_dir: Path, files: TargetFiles) -> None:
    for rel, text in files.items():
        path = target_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def synthesize(
    goal: str,
    tests: TargetFiles,
    implementer: Implementer,
    *,
    run: TestRun,
    workdir: Path,
    scorer: MutationScorer | None = None,
    max_iterations: int = 3,
    mutation_threshold: float = 0.70,
) -> SynthesisResult:
    """Drive spec-derived `tests` to green with `implementer`, then gate on mutation.

    The tests are FIXED (they encode the spec); only the source changes each iteration. On each pass
    the implementer sees the previous run's failure output as feedback. Once green, an optional
    `scorer` proves the tests bite: below `mutation_threshold` the verdict is TESTS_TOO_WEAK, not a
    false VERIFIED. Fails loud (REFUSED) if there is nothing to verify."""
    if not goal or not goal.strip():
        return SynthesisResult(REFUSED, 0)
    if not tests:
        return SynthesisResult(REFUSED, 0)
    workdir = Path(workdir)
    _write(workdir, tests)  # the spec-derived tests are written once and never rewritten

    feedback = ""
    last_run: ToolRunResult | None = None
    files: TargetFiles = {}
    attempts = 0
    for _ in range(max_iterations):
        attempts += 1
        files = implementer.implement(goal, tests, feedback)
        _write(workdir, files)
        last_run = run(workdir)
        if last_run.ok:
            break
        feedback = last_run.output  # feed the red output back for the next attempt
    else:
        # loop finished without a break: never went green
        return SynthesisResult(RED_BUDGET_EXHAUSTED, attempts, files=files, run=last_run)

    if scorer is None:
        return SynthesisResult(VERIFIED, attempts, files=files, run=last_run)

    kill_rate = scorer.score(workdir)
    if kill_rate is not None and kill_rate < mutation_threshold:
        return SynthesisResult(
            TESTS_TOO_WEAK, attempts, files=files, run=last_run, mutation_score=kill_rate
        )
    return SynthesisResult(VERIFIED, attempts, files=files, run=last_run, mutation_score=kill_rate)
