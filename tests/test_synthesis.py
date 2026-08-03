"""Test twin for kernel/seedlab/synthesis.py -- the reverse-TDD generation harness.

Acceptance: the harness drives spec-derived tests to green by iterating an Implementer (feeding each
red run's output back), then gates on mutation; it reports honest verdicts. Proven both with fast
fakes AND end-to-end with REAL pytest execution (a wrong-then-right implementer converging on real
code the real runner verifies).

Refusal (fail loud): an empty goal or no tests is REFUSED (nothing to verify); an implementer that
never satisfies the tests within the budget is RED_BUDGET_EXHAUSTED, never a false VERIFIED; a green
suite whose mutation kill-rate is below threshold is TESTS_TOO_WEAK.
"""

from __future__ import annotations

from pathlib import Path

from kernel.seedlab.synthesis import (
    RED_BUDGET_EXHAUSTED,
    REFUSED,
    TESTS_TOO_WEAK,
    VERIFIED,
    Implementer,
    MutationScorer,
    SynthesisResult,
    TargetFiles,
    pytest_runner,
    synthesize,
)
from kernel.seedlab.tool_runner import ToolRunResult

# Emitted with the spec-derived tests so the target module is importable when pytest runs.
_CONFTEST = "import pathlib\nimport sys\nsys.path.insert(0, str(pathlib.Path(__file__).parent))\n"


def _result(ok: bool, output: str = "") -> ToolRunResult:
    return ToolRunResult(
        seed_id="_t",
        kind="test",
        profile="pytest",
        argv=["pytest"],
        exit_code=0 if ok else 1,
        output=output,
        duration=0.0,
        timed_out=False,
        cwd=".",
        when="2026-08-03T00:00:00+00:00",
    )


class _ScriptedImplementer:
    """Returns a scripted sequence of source file-sets, one per attempt, recording the feedback it
    was given so a test can prove the red output was fed back."""

    def __init__(self, *outputs: TargetFiles) -> None:
        self._outputs = list(outputs)
        self.feedback_seen: list[str] = []
        self.calls = 0

    def implement(self, goal: str, tests: TargetFiles, feedback: str) -> TargetFiles:
        self.feedback_seen.append(feedback)
        out = self._outputs[min(self.calls, len(self._outputs) - 1)]
        self.calls += 1
        return out


class _ScriptedRun:
    """A fake TestRun: returns red until `green_on` calls, then green."""

    def __init__(self, green_on: int) -> None:
        self._green_on = green_on
        self.calls = 0

    def __call__(self, target_dir: Path) -> ToolRunResult:
        self.calls += 1
        return _result(ok=self.calls >= self._green_on, output=f"fail#{self.calls}")


class _FixedScorer:
    def __init__(self, value: float | None) -> None:
        self._value = value

    def score(self, target_dir: Path) -> float | None:
        return self._value


# --- acceptance --------------------------------------------------------------------------------


def test_the_seams_are_protocols() -> None:
    assert isinstance(_ScriptedImplementer({"a.py": ""}), Implementer)
    assert isinstance(_FixedScorer(0.9), MutationScorer)


def test_implements_until_green_and_feeds_failures_back(tmp_path: Path) -> None:
    impl = _ScriptedImplementer({"m.py": "bad"}, {"m.py": "good"})
    run = _ScriptedRun(green_on=2)  # red on attempt 1, green on attempt 2
    result = synthesize("build m", {"tests/t.py": "..."}, impl, run=run, workdir=tmp_path)
    assert result.verdict == VERIFIED and result.iterations == 2
    # the first attempt saw no feedback; the second saw the first red run's output
    assert impl.feedback_seen[0] == "" and impl.feedback_seen[1] == "fail#1"


def test_green_on_first_try_no_scorer_is_verified(tmp_path: Path) -> None:
    impl = _ScriptedImplementer({"m.py": "good"})
    result = synthesize("g", {"tests/t.py": "x"}, impl, run=_ScriptedRun(1), workdir=tmp_path)
    assert result.verdict == VERIFIED and result.iterations == 1
    assert result.ok is True  # the ok property mirrors the verdict


def test_mutation_gate_passes_a_biting_suite(tmp_path: Path) -> None:
    result = synthesize(
        "g",
        {"tests/t.py": "x"},
        _ScriptedImplementer({"m.py": "ok"}),
        run=_ScriptedRun(1),
        workdir=tmp_path,
        scorer=_FixedScorer(0.9),
        mutation_threshold=0.7,
    )
    assert result.verdict == VERIFIED and result.mutation_score == 0.9


# --- refusal: fail loud, never a false VERIFIED -------------------------------------------------


def test_a_weak_suite_is_flagged_not_passed(tmp_path: Path) -> None:
    result = synthesize(
        "g",
        {"tests/t.py": "x"},
        _ScriptedImplementer({"m.py": "ok"}),
        run=_ScriptedRun(1),
        workdir=tmp_path,
        scorer=_FixedScorer(0.4),
        mutation_threshold=0.7,
    )
    assert result.verdict == TESTS_TOO_WEAK and result.mutation_score == 0.4


def test_never_green_is_budget_exhausted_not_verified(tmp_path: Path) -> None:
    result = synthesize(
        "g",
        {"tests/t.py": "x"},
        _ScriptedImplementer({"m.py": "bad"}),
        run=_ScriptedRun(green_on=99),
        workdir=tmp_path,
        max_iterations=3,
    )
    assert result.verdict == RED_BUDGET_EXHAUSTED and result.iterations == 3


def test_empty_goal_or_no_tests_is_refused(tmp_path: Path) -> None:
    impl = _ScriptedImplementer({"m.py": "x"})
    assert (
        synthesize("  ", {"tests/t.py": "x"}, impl, run=_ScriptedRun(1), workdir=tmp_path).verdict
        == REFUSED
    )
    assert synthesize("g", {}, impl, run=_ScriptedRun(1), workdir=tmp_path).verdict == REFUSED


# --- integration: the loop over REAL code, run by the REAL pytest runner -------------------------


class _RealCalcImplementer:
    """A stand-in for the (later) LLM Implementer: emits WRONG code first (a - b), then RIGHT code
    (a + b) once it sees the failure -- so the real pytest runner drives it to green over real code.
    The fixed spec-derived tests are what force correctness."""

    def implement(self, goal: str, tests: TargetFiles, feedback: str) -> TargetFiles:
        body = "a + b" if feedback else "a - b"
        return {"calc.py": f"def add(a, b):\n    return {body}\n"}


def test_end_to_end_real_pytest_drives_wrong_code_to_verified(tmp_path: Path) -> None:
    # spec-derived tests: real behavioral assertions the implementation MUST satisfy
    tests: TargetFiles = {
        "conftest.py": _CONFTEST,
        "tests/test_calc.py": (
            "from calc import add\n\n\n"
            "def test_add_positives():\n    assert add(2, 3) == 5\n\n\n"
            "def test_add_negatives():\n    assert add(-1, -4) == -5\n"
        ),
    }
    result = synthesize(
        "an add(a, b) that returns the sum",
        tests,
        _RealCalcImplementer(),
        run=pytest_runner(),
        workdir=tmp_path,
        max_iterations=3,
    )
    assert result.verdict == VERIFIED  # real pytest went green
    assert result.iterations == 2  # wrong on attempt 1, right on attempt 2
    assert result.run is not None and result.run.ok
    assert "a + b" in (tmp_path / "calc.py").read_text(encoding="utf-8")


def test_end_to_end_a_never_correct_implementer_stays_red(tmp_path: Path) -> None:
    tests: TargetFiles = {
        "conftest.py": _CONFTEST,
        "tests/test_calc.py": (
            "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
        ),
    }

    class _AlwaysWrong:
        def implement(self, goal: str, tests: TargetFiles, feedback: str) -> TargetFiles:
            return {"calc.py": "def add(a, b):\n    return a - b\n"}

    result = synthesize(
        "sum", tests, _AlwaysWrong(), run=pytest_runner(), workdir=tmp_path, max_iterations=2
    )
    assert result.verdict == RED_BUDGET_EXHAUSTED
    assert isinstance(result, SynthesisResult)
