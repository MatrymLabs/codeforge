"""Acceptance tests for the per-workdir cosmic-ray MutationScorer adapter."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from adapters.mutation_scorer import CosmicRayMutationScorer
from kernel.seedlab.synthesis import MutationScorer

Runner = Callable[[Path, Path, float, float, int], str | None]

PARTIAL_REPORT = """\
total jobs: 10
complete: 10 (100.00%)
surviving mutants: 2 (20.00%)
"""

ALL_SURVIVED_REPORT = """\
total jobs: 4
complete: 4 (100.00%)
surviving mutants: 4 (100.00%)
"""

ZERO_MUTANT_REPORT = """\
total jobs: 0
complete: 0 (0.00%)
surviving mutants: 0 (0.00%)
"""


def _workdir(tmp_path: Path) -> Path:
    (tmp_path / "cli.py").write_text("def main(argv=None):\n    return 0\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    # This deliberate name collision proves the source, not an identically named test, is mutated.
    (tests / "cli.py").write_text("def test_main():\n    assert True\n", encoding="utf-8")
    return tmp_path


def test_scores_a_workdir_from_a_cosmic_ray_report(tmp_path: Path) -> None:
    calls: list[tuple[Path, Path, float, float, int]] = []

    def runner(
        workdir: Path,
        config: Path,
        per_mutant_timeout: float,
        whole_run_budget: float,
        max_mutants: int,
    ) -> str:
        calls.append((workdir, config, per_mutant_timeout, whole_run_budget, max_mutants))
        return PARTIAL_REPORT

    scorer = CosmicRayMutationScorer(runner=runner)

    assert scorer.score(_workdir(tmp_path)) == pytest.approx(0.8)
    assert calls == [(tmp_path, tmp_path / ".cosmic-ray.toml", 30.0, 300.0, 50)]


def test_returns_none_when_cosmic_ray_is_absent(tmp_path: Path) -> None:
    scorer = CosmicRayMutationScorer(runner=lambda *_: None)

    assert scorer.score(_workdir(tmp_path)) is None


def test_returns_none_when_no_mutants_were_generated(tmp_path: Path) -> None:
    scorer = CosmicRayMutationScorer(runner=lambda *_: ZERO_MUTANT_REPORT)

    assert scorer.score(_workdir(tmp_path)) is None


def test_returns_none_on_timeout_and_does_not_hang(tmp_path: Path) -> None:
    calls: list[tuple[Path, Path, float, float, int]] = []

    def timed_out(
        workdir: Path,
        config: Path,
        per_mutant_timeout: float,
        whole_run_budget: float,
        max_mutants: int,
    ) -> None:
        calls.append((workdir, config, per_mutant_timeout, whole_run_budget, max_mutants))
        return None

    scorer = CosmicRayMutationScorer(
        runner=timed_out, per_mutant_timeout_seconds=0.01, whole_run_budget_seconds=120.0
    )

    assert scorer.score(_workdir(tmp_path)) is None
    assert calls == [(tmp_path, tmp_path / ".cosmic-ray.toml", 0.01, 120.0, 50)]
    assert "timeout = 0.01" in (tmp_path / ".cosmic-ray.toml").read_text(encoding="utf-8")


def test_a_total_survival_result_scores_zero_not_none(tmp_path: Path) -> None:
    scorer = CosmicRayMutationScorer(runner=lambda *_: ALL_SURVIVED_REPORT)

    assert scorer.score(_workdir(tmp_path)) == 0.0


def test_writes_its_config_into_the_workdir_and_never_touches_the_repo_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_config = Path(__file__).resolve().parents[1] / "cosmic-ray.toml"
    before = repository_config.read_text(encoding="utf-8")
    original_read_text = Path.read_text

    def refuse_repository_config(
        self: Path, encoding: str | None = None, errors: str | None = None
    ) -> str:
        if self == repository_config:
            raise AssertionError("the scorer must not read the repository cosmic-ray.toml")
        return original_read_text(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", refuse_repository_config)
    workdir = _workdir(tmp_path)
    scorer = CosmicRayMutationScorer(runner=lambda *_: PARTIAL_REPORT)

    assert scorer.score(workdir) == pytest.approx(0.8)
    monkeypatch.undo()
    config = workdir / ".cosmic-ray.toml"
    assert config.is_file()
    assert 'module-path = "cli.py"' in config.read_text(encoding="utf-8")
    assert repository_config.read_text(encoding="utf-8") == before


def test_malformed_report_is_not_computable(tmp_path: Path) -> None:
    scorer = CosmicRayMutationScorer(runner=lambda *_: "surviving mutants: 99 (99.00%)")

    assert scorer.score(_workdir(tmp_path)) is None


def test_percentage_survival_in_the_report_is_not_treated_as_a_fraction(tmp_path: Path) -> None:
    report = "total jobs: 2\ncomplete: 2 (100.00%)\nsurviving mutants: 1 (50.00%)"
    scorer = CosmicRayMutationScorer(runner=lambda *_: report)

    assert scorer.score(_workdir(tmp_path)) == 0.5


def test_the_scorer_satisfies_the_protocol() -> None:
    scorer = CosmicRayMutationScorer(runner=lambda *_: None)

    assert isinstance(scorer, MutationScorer)
