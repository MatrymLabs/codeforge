"""Cosmic-ray-backed implementation of the SeedLab MutationScorer protocol.

Each score owns its config and session inside the generated workdir. The repository mutation
configuration is deliberately never read or changed: it targets a fixed repository module, while
this adapter measures one generated source module against that workdir's generated tests.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess  # nosec B404
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from kernel.shelf.mutation_kpi import MutationKpiError, parse_cr_report

DEFAULT_PER_MUTANT_TIMEOUT_SECONDS = 30.0
# P-06 measured about 3.1 seconds per mutant. 300 seconds gives 50 capped mutants about twice
# that measured time for test and process startup overhead before the whole run is abandoned.
DEFAULT_WHOLE_RUN_BUDGET_SECONDS = 300.0
DEFAULT_MAX_MUTANTS = 50

# The runner is injected so the acceptance twin stays offline and does not need cosmic-ray.
CosmicRayRunner = Callable[[Path, Path, float, float, int], str | None]


def _source_module(workdir: Path) -> Path | None:
    """Return the sole generated source module, refusing an ambiguous target."""
    candidates = [
        path
        for path in sorted(workdir.rglob("*.py"))
        if "tests" not in path.relative_to(workdir).parts
        and path.name != "conftest.py"
        and not path.name.startswith("test_")
    ]
    return candidates[0] if len(candidates) == 1 else None


def _write_config(workdir: Path, source: Path, per_mutant_timeout_seconds: float) -> Path:
    """Write the per-run config that targets only this generated source module."""
    config = workdir / ".cosmic-ray.toml"
    module_path = source.relative_to(workdir).as_posix()
    config.write_text(
        "\n".join(
            (
                "[cosmic-ray]",
                f'module-path = "{module_path}"',
                f"timeout = {per_mutant_timeout_seconds}",
                "excluded-modules = []",
                'test-command = "python -m pytest -x -q tests"',
                "",
                "[cosmic-ray.distributor]",
                'name = "local"',
                "",
            )
        ),
        encoding="utf-8",
    )
    return config


def _run_command(argv: list[str], workdir: Path, timeout_seconds: float) -> str | None:
    """Run one bounded cosmic-ray command, returning output only on success."""
    try:
        completed = subprocess.run(  # nosec B603  # noqa: S603
            argv,
            cwd=workdir,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def _cap_session(session: Path, max_mutants: int) -> bool:
    """Keep only bounded work items in a private session.

    This reads cosmic-ray's private ``work_items`` and ``mutation_specs`` schema. A future
    cosmic-ray rename becomes False here, so the caller degrades to None rather than a wrong score.
    """
    try:
        with sqlite3.connect(session) as connection:
            rows = connection.execute(
                "SELECT job_id FROM work_items ORDER BY job_id LIMIT ?", (max_mutants,)
            ).fetchall()
            job_ids = [row[0] for row in rows]
            if not job_ids:
                return True
            placeholders = ", ".join("?" for _ in job_ids)
            # Safe: placeholder count only, values are parameterized.
            connection.execute(
                f"DELETE FROM mutation_specs WHERE job_id NOT IN ({placeholders})",  # nosec B608  # noqa: S608
                job_ids,
            )
            # Safe: placeholder count only, values are parameterized.
            connection.execute(
                f"DELETE FROM work_items WHERE job_id NOT IN ({placeholders})",  # nosec B608  # noqa: S608
                job_ids,
            )
    except sqlite3.Error:
        return False
    return True


def _run_cosmic_ray(
    workdir: Path,
    config: Path,
    per_mutant_timeout_seconds: float,  # noqa: ARG001
    whole_run_budget_seconds: float,
    max_mutants: int,
) -> str | None:
    """Run cosmic-ray in the generated workdir and return its report, or None if unmeasurable."""
    cosmic_ray = shutil.which("cosmic-ray")
    report = shutil.which("cr-report")
    if cosmic_ray is None or report is None:
        return None

    session = workdir / ".cosmic-ray-session.sqlite"
    if (
        _run_command(
            [cosmic_ray, "init", "--force", str(config), str(session)],
            workdir,
            whole_run_budget_seconds,
        )
        is None
    ):
        return None
    if not _cap_session(session, max_mutants):
        return None
    if (
        _run_command(
            [cosmic_ray, "exec", str(config), str(session)], workdir, whole_run_budget_seconds
        )
        is None
    ):
        return None
    return _run_command([report, str(session)], workdir, whole_run_budget_seconds)


@dataclass(frozen=True)
class CosmicRayMutationScorer:
    """Score a generated workdir with a bounded, private cosmic-ray session."""

    runner: CosmicRayRunner = _run_cosmic_ray
    per_mutant_timeout_seconds: float = DEFAULT_PER_MUTANT_TIMEOUT_SECONDS
    whole_run_budget_seconds: float = DEFAULT_WHOLE_RUN_BUDGET_SECONDS
    max_mutants: int = DEFAULT_MAX_MUTANTS

    def __post_init__(self) -> None:
        if self.per_mutant_timeout_seconds <= 0:
            raise ValueError("per_mutant_timeout_seconds must be positive")  # noqa: TRY003
        if self.whole_run_budget_seconds <= 0:
            raise ValueError("whole_run_budget_seconds must be positive")  # noqa: TRY003
        if self.max_mutants <= 0:
            raise ValueError("max_mutants must be positive")  # noqa: TRY003

    def score(self, target_dir: Path) -> float | None:
        """Return a measured kill rate, or None when cosmic-ray cannot produce one honestly."""
        workdir = Path(target_dir)
        source = _source_module(workdir)
        if source is None:
            return None
        config = _write_config(workdir, source, self.per_mutant_timeout_seconds)
        report = self.runner(
            workdir,
            config,
            self.per_mutant_timeout_seconds,
            self.whole_run_budget_seconds,
            self.max_mutants,
        )
        if report is None:
            return None
        try:
            result = parse_cr_report(report, run_date=date.today())  # noqa: DTZ011
        except MutationKpiError:
            return None
        if result.total == 0:
            return None
        return result.kill_rate
