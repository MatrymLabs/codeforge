"""Produce a Blueprint Evolution Lab demo run and file it as evidence.

Runs the ScoreSheetRenderer column-formatter bake-off and writes the report to
reports/evolution/ (git-ignored, reproducible from the recorded commit). This is the
AUTHORIZED execution path -- a CLI / `make evolution`, never a MUD side effect. Nothing is
promoted: the run ends `human_decision_required` and Josh selects the elite via review.
"""

from __future__ import annotations

from parts import blueprint as bp
from parts.evolution.bakeoff import build_score_sheet_pairs, render_run, run_bakeoff
from parts.evolution.genome import BlueprintGenome
from parts.evolution.store import write_run


def main() -> int:
    seed = bp.Blueprint(
        "fit_column", "Fit Column", "Fit text to a fixed width.", ("pure function",)
    )
    genome = BlueprintGenome(
        genome_id="fit_column",
        seed=seed,
        purpose="Evolve a fixed-width column formatter for the ScoreSheetRenderer.",
        test_obligations=("matches the oracle on every input",),
        documentation_obligations=("CARD docstring",),
        expression_targets=("code", "tests"),
    )
    run = run_bakeoff(genome, build_score_sheet_pairs("fit_column"), run_id="score_sheet_fit_v1")
    path = write_run(run)
    print(render_run(run))
    print(f"\nfiled: {path}  (view in-MUD: evolution show {run.run_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
