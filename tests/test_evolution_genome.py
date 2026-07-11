"""Test twin for parts/evolution/genome.py + validation.py -- the Blueprint Genome gate.

Acceptance: a well-formed genome round-trips and validates. Refusal (the headline cases): a
malformed genome fails loud, an illegal dependency combination is rejected before expression,
and the v1 KeelGate holds -- a genome may never declare autonomous mutation or self-approval.
"""

from __future__ import annotations

import pytest

from parts import blueprint as bp
from parts.evolution.genome import BlueprintGenome, GenomeError, from_dict, to_dict
from parts.evolution.validation import check_constraints, constraints_ok, validate_genome


def _seed() -> bp.Blueprint:
    return bp.Blueprint(
        blueprint_id="score_sheet_renderer",
        title="Score Sheet Renderer",
        intent="Render a character view model as a fixed-width panel.",
        requirements=("pure function", "deterministic output"),
        tasks=("define the view model", "render columns"),
    )


def _genome(**over: object) -> BlueprintGenome:
    base: dict[str, object] = dict(
        genome_id="score_sheet_renderer",
        seed=_seed(),
        purpose="Evolve a readable, fast score-sheet renderer.",
        interfaces=("render_score_sheet(sheet, mode) -> str",),
        invariants=("mutates nothing", "computes no formulas"),
        allowed_dependencies=("parts.score_sheet",),
        prohibited_dependencies=("parts.db",),
        resource_budgets=(("render_us", "50"),),
        test_obligations=("golden snapshot pins the format",),
        documentation_obligations=("CARD docstring",),
        expression_targets=("code", "tests"),
        provenance=(("author", "josh"), ("source", "nature_inspired_report")),
    )
    base.update(over)
    return BlueprintGenome(**base)  # type: ignore[arg-type]


def test_a_well_formed_genome_round_trips() -> None:
    genome = _genome()
    assert from_dict(to_dict(genome)) == genome  # frozen dataclass -> value equality
    assert genome.seed.blueprint_id == "score_sheet_renderer"  # the seed survived


def test_a_clean_genome_validates_and_returns_itself() -> None:
    genome = _genome(test_obligations=("x",), documentation_obligations=("y",))
    assert constraints_ok(genome)
    assert validate_genome(genome) is genome  # passes -> returned unchanged


def test_provenance_and_budgets_survive_serialization() -> None:
    genome = _genome()
    restored = from_dict(to_dict(genome))
    assert restored.provenance == (("author", "josh"), ("source", "nature_inspired_report"))
    assert restored.resource_budgets == (("render_us", "50"),)


def test_a_record_without_genome_id_fails_loud() -> None:
    with pytest.raises(GenomeError, match="missing 'genome_id'"):
        from_dict({"purpose": "x", "seed": bp.to_dict(_seed())})


def test_a_record_without_a_seed_fails_loud() -> None:
    with pytest.raises(GenomeError, match="missing 'seed'"):
        from_dict({"genome_id": "g", "purpose": "x"})


def test_a_bad_seed_fails_loud() -> None:
    with pytest.raises(GenomeError, match="not a valid Blueprint"):
        from_dict({"genome_id": "g", "purpose": "x", "seed": {"nope": 1}})


def test_an_illegal_dependency_combination_is_blocked() -> None:
    # DNA-like constraint: a dependency cannot be both allowed and prohibited.
    genome = _genome(allowed_dependencies=("parts.db",), prohibited_dependencies=("parts.db",))
    results = {r.rule_id: r for r in check_constraints(genome)}
    assert results["GEN07"].blocking
    assert not constraints_ok(genome)
    with pytest.raises(GenomeError, match="GEN07"):
        validate_genome(genome)


def test_keelgate_rejects_autonomous_mutation() -> None:
    # v1 governance: a genome may never declare autonomous mutation.
    genome = _genome(mutation_policy="autonomous_rewrite")
    with pytest.raises(GenomeError, match="GEN04"):
        validate_genome(genome)


def test_keelgate_rejects_self_approval() -> None:
    # v1 governance: a genome may never approve its own promotion -- Josh decides.
    genome = _genome(approval_policy="auto_promote")
    with pytest.raises(GenomeError, match="GEN05"):
        validate_genome(genome)


def test_a_non_snake_case_genome_id_is_blocked() -> None:
    genome = _genome(genome_id="Score Sheet")
    assert not constraints_ok(genome)
    assert any(r.rule_id == "GEN01" and r.blocking for r in check_constraints(genome))


def test_an_unknown_expression_target_is_blocked() -> None:
    genome = _genome(expression_targets=("code", "firmware"))
    assert any(r.rule_id == "GEN06" and r.blocking for r in check_constraints(genome))


def test_a_minimal_genome_defaults_optional_fields_to_empty() -> None:
    # Absent optional fields default to empty tuples (the None-coercion paths).
    genome = from_dict({"genome_id": "min_g", "purpose": "x", "seed": bp.to_dict(_seed())})
    assert genome.interfaces == () and genome.resource_budgets == () and genome.provenance == ()


def test_a_non_mapping_record_fails_loud() -> None:
    with pytest.raises(GenomeError, match="must be a mapping"):
        from_dict(["not", "a", "dict"])


def test_a_string_where_a_list_is_expected_fails_loud() -> None:
    raw = {"genome_id": "g", "purpose": "x", "seed": bp.to_dict(_seed()), "interfaces": "oops"}
    with pytest.raises(GenomeError, match="must be a list of strings"):
        from_dict(raw)


def test_a_malformed_pairs_field_fails_loud() -> None:
    raw = {"genome_id": "g", "purpose": "x", "seed": bp.to_dict(_seed()), "resource_budgets": [1, 2, 3]}
    with pytest.raises(GenomeError, match="pairs of"):
        from_dict(raw)


def test_empty_purpose_and_unknown_status_are_blocked() -> None:
    genome = _genome(purpose="   ", status="bogus")
    blocking = {r.rule_id for r in check_constraints(genome) if r.blocking}
    assert "GEN02" in blocking and "GEN03" in blocking


def test_missing_obligations_warn_but_do_not_block() -> None:
    genome = _genome(test_obligations=(), documentation_obligations=())
    results = {r.rule_id: r for r in check_constraints(genome)}
    assert results["GEN08"].severity == "warning" and not results["GEN08"].blocking
    assert results["GEN09"].severity == "warning" and not results["GEN09"].blocking
    assert constraints_ok(genome)  # warnings never block validation
