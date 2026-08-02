"""Produce a Blueprint Evolution Lab demo run and file it as evidence.

Runs the ScoreSheetRenderer column-formatter bake-off and writes the report to
reports/evolution/ (git-ignored, reproducible from the recorded commit). This is the
AUTHORIZED execution path -- a CLI / `make evolution`, never a MUD side effect. Nothing is
promoted: the run ends `human_decision_required` and Josh selects the elite via review.
"""

from __future__ import annotations

from parts import blueprint as bp
from parts.evolution.bakeoff import (
    build_score_sheet_pairs,
    build_slugify_pairs,
    render_run,
    run_bakeoff,
)
from parts.evolution.genome import BlueprintGenome
from parts.evolution.store import write_run
from parts.evolution.subjects import SLUGIFY_INPUTS, slugify_oracle


def _genome(genome_id: str, title: str, intent: str, purpose: str) -> BlueprintGenome:
    return BlueprintGenome(
        genome_id=genome_id,
        seed=bp.Blueprint(
            genome_id,
            title,
            intent,
            ("pure function",),
            ("pure function: no security-sensitive surface",),
        ),
        purpose=purpose,
        test_obligations=("matches the oracle on every input",),
        documentation_obligations=("CARD docstring",),
        expression_targets=("code", "tests"),
    )


def main() -> int:
    # Two subjects, one lab: fit_column (str, int) and slugify (str,) prove the framework is
    # signature-agnostic. Both end human_decision_required; nothing is promoted.
    fit = run_bakeoff(
        _genome(
            "fit_column",
            "Fit Column",
            "Fit text to a fixed width.",
            "Evolve a fixed-width column formatter for the ScoreSheetRenderer.",
        ),
        build_score_sheet_pairs("fit_column"),
        run_id="score_sheet_fit_v1",
    )
    slug = run_bakeoff(
        _genome("slugify", "Slugify", "Normalize text to a label.", "Evolve a label normalizer."),
        build_slugify_pairs("slugify"),
        run_id="slugify_v1",
        inputs=SLUGIFY_INPUTS,
        oracle=slugify_oracle,
        elite_baseline="slugify_oracle",
    )
    for run in (fit, slug):
        path = write_run(run)
        print(render_run(run))
        print(f"\nfiled: {path}  (view in-MUD: evolution show {run.run_id})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
