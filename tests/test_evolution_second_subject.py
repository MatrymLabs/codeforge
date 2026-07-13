"""Test twin: the bake-off generalizes to a second subject with a different signature.

fit_column is (str, int) -> str; slugify is (str,) -> str. The SAME run_bakeoff, evaluators,
fitness, and counterexample machinery must score both -- that is what proves the lab is a
general evaluator-guided search, not a one-function demo.
"""

from __future__ import annotations

from parts import blueprint as bp
from parts.evolution.bakeoff import build_slugify_pairs, run_bakeoff
from parts.evolution.genome import BlueprintGenome
from parts.evolution.subjects import (
    SLUGIFY_INPUTS,
    slug_extensible,
    slug_minimal,
    slugify_oracle,
)


def _genome() -> BlueprintGenome:
    seed = bp.Blueprint(
        "slugify", "Slugify", "Normalize text to a label.", ("pure",), ("no untrusted input",)
    )
    return BlueprintGenome(
        genome_id="slugify",
        seed=seed,
        purpose="Evolve a label normalizer.",
        test_obligations=("matches the oracle",),
        documentation_obligations=("docstring",),
        expression_targets=("code", "tests"),
    )


def _run():
    return run_bakeoff(
        _genome(),
        build_slugify_pairs("slugify"),
        run_id="slug_test",
        inputs=SLUGIFY_INPUTS,
        oracle=slugify_oracle,
        elite_baseline="slugify_oracle",
    )


def test_the_oracle_and_minimal_candidate_agree_on_the_contract() -> None:
    # Sanity on the subject itself: the minimal candidate mirrors the oracle exactly.
    for (text,) in SLUGIFY_INPUTS:
        assert slug_minimal(text) == slugify_oracle(text)
    assert slugify_oracle("") == "label" and slug_extensible("") == ""  # the break is real


def test_a_different_signature_runs_through_the_same_lab() -> None:
    run = _run()
    disp = {o.candidate.candidate_id: o.candidate.disposition for o in run.outcomes}
    assert disp["cand_minimal"] == "qualified"
    assert disp["cand_performance"] == "qualified"
    assert disp["cand_extensible"] == "rejected"  # omits strip + fallback -> breaks the contract


def test_the_slugify_break_becomes_counterexamples() -> None:
    run = _run()
    assert len(run.counterexamples) >= 2  # multiple truncation/fallback inputs fail
    assert all(c.first_seen == "cand_extensible" for c in run.counterexamples)
    assert run.final_status == "human_decision_required"  # still nothing auto-promoted


def test_the_slugify_winner_is_a_qualified_survivor() -> None:
    run = _run()
    assert run.winner in {"cand_minimal", "cand_performance"}
    assert all(o.candidate.disposition != "elite" for o in run.outcomes)
