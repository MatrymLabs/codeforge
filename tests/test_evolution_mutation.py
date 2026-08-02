"""Test twin for parts/evolution/mutation.py.

The propose-only generative step for the Blueprint Evolution Lab (HC-13). Pins the KEEL first:
every proposal is propose_only + human_required + status candidate, never autonomous, never
auto-promoted. Then the operator algebra (drop/harden/scale/crossover), determinism, refusal of a
bad seed, and hostile identifiers.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from parts.evolution import mutation
from parts.evolution.genome import BlueprintGenome, from_dict
from parts.evolution.validation import validate_genome


def _genome(
    genome_id: str = "widget",
    *,
    allowed=("requests", "pyyaml"),
    prohibited=(),
    budgets=(("render_us", "50"), ("bytes", "1024"), ("note", "fast")),
) -> BlueprintGenome:
    """A valid seed genome (its Blueprint seed and the genome both pass their gates)."""
    return from_dict(
        {
            "genome_id": genome_id,
            "seed": {
                "blueprint_id": f"{genome_id}_seed",
                "title": "Widget",
                "intent": "format a widget",
                "requirements": ["render a row"],
                "security": ["untrusted input is escaped"],
            },
            "purpose": "a formatter",
            "invariants": ["output width is fixed"],
            "allowed_dependencies": list(allowed),
            "prohibited_dependencies": list(prohibited),
            "resource_budgets": [list(b) for b in budgets],
            "test_obligations": ["acceptance + refusal"],
            "documentation_obligations": ["a CARD line"],
        }
    )


class KeelInvariants(unittest.TestCase):
    """The whole point: AI proposes, it never self-approves or goes autonomous."""

    def test_every_proposal_is_propose_only_and_human_required(self):
        proposals = mutation.propose_variants(_genome())
        self.assertTrue(proposals)
        for p in proposals:
            self.assertEqual(p.mutation_policy, "propose_only")
            self.assertEqual(p.approval_policy, "human_required")

    def test_no_proposal_is_autonomous_or_self_approving(self):
        pool = [_genome("a"), _genome("b", allowed=("requests",))]
        everything = mutation.propose_variants(pool[0]) + mutation.propose_crossovers(pool)
        for p in everything:
            self.assertNotEqual(p.mutation_policy, "autonomous")
            self.assertNotIn(p.approval_policy, ("self", "auto", "none"))

    def test_no_proposal_is_auto_promoted(self):
        # A generated candidate is never qualified/elite - promotion is a human act.
        for p in mutation.propose_variants(_genome()):
            self.assertEqual(p.status, "candidate")
            self.assertNotIn(p.status, ("qualified", "elite"))

    def test_every_proposal_passes_the_keelgate(self):
        for p in mutation.propose_variants(_genome()):
            self.assertIs(validate_genome(p), p)  # would raise if it did not pass

    def test_provenance_records_operator_and_parent(self):
        p = mutation.propose_variants(_genome("root"))[0]
        prov = dict(p.provenance)
        self.assertIn("mutation_operator", prov)
        self.assertIn("root", prov["parents"])
        self.assertEqual(prov["proposed_by"], "evolution.mutation (propose-only)")


class Operators(unittest.TestCase):
    def test_drop_dependency_yields_one_leaner_variant_per_dep(self):
        variants = mutation.drop_dependency(_genome(allowed=("requests", "pyyaml")))
        self.assertEqual(len(variants), 2)
        surfaces = {v.allowed_dependencies for v in variants}
        self.assertEqual(surfaces, {("pyyaml",), ("requests",)})

    def test_harden_dependency_moves_allowed_to_prohibited(self):
        v = mutation.harden_dependency(_genome(allowed=("requests",)))[0]
        self.assertEqual(v.allowed_dependencies, ())
        self.assertIn("requests", v.prohibited_dependencies)
        # and it stays gate-clean (no allowed/prohibited conflict, GEN07)
        self.assertIs(validate_genome(v), v)

    def test_scale_budgets_tightens_only_numeric_values(self):
        v = mutation.scale_budgets(_genome(), factor=0.5)
        self.assertIsNotNone(v)
        b = dict(v.resource_budgets)
        self.assertEqual(b["render_us"], "25")  # 50 * 0.5, integral -> no trailing .0
        self.assertEqual(b["bytes"], "512")
        self.assertEqual(b["note"], "fast")  # non-numeric untouched

    def test_scale_budgets_none_when_no_numeric_budget(self):
        self.assertIsNone(mutation.scale_budgets(_genome(budgets=(("note", "fast"),))))

    def test_scale_factor_out_of_range_raises(self):
        with self.assertRaises(mutation.MutationError):
            mutation.scale_budgets(_genome(), factor=1.5)

    def test_crossover_unions_invariants_and_intersects_allowed_deps(self):
        a = _genome("a", allowed=("requests", "pyyaml"))
        b = _genome("b", allowed=("pyyaml", "httpx"))
        child = mutation.crossover(a, b)
        self.assertIsNotNone(child)
        # allowed deps never widen past either parent: only what BOTH allow
        self.assertEqual(set(child.allowed_dependencies), {"pyyaml"})

    def test_crossover_keeps_the_stricter_shared_budget(self):
        a = _genome("a", budgets=(("render_us", "50"),))
        b = _genome("b", budgets=(("render_us", "30"),))
        child = mutation.crossover(a, b)
        self.assertEqual(dict(child.resource_budgets)["render_us"], "30")

    def test_crossover_unions_disjoint_fields_and_merges_distinct_budgets(self):
        # disjoint invariants + distinct budgets exercise the union-append + budget-merge paths
        a = replace(_genome("a", budgets=(("render_us", "50"),)), invariants=("width fixed",))
        b = replace(_genome("b", budgets=(("bytes", "1024"),)), invariants=("no allocation",))
        child = mutation.crossover(a, b)
        self.assertEqual(set(child.invariants), {"width fixed", "no allocation"})
        self.assertEqual(dict(child.resource_budgets), {"render_us": "50", "bytes": "1024"})

    def test_scale_budgets_keeps_a_non_integral_value(self):
        v = mutation.scale_budgets(_genome(budgets=(("render_us", "7"),)), factor=0.5)
        self.assertEqual(dict(v.resource_budgets)["render_us"], "3.5")  # 7 * 0.5, not integral


class Determinism(unittest.TestCase):
    def test_same_seed_same_proposals(self):
        first = [p.genome_id for p in mutation.propose_variants(_genome("seed"))]
        second = [p.genome_id for p in mutation.propose_variants(_genome("seed"))]
        self.assertEqual(first, second)

    def test_proposal_ids_are_distinct_and_snake_case(self):
        ids = [p.genome_id for p in mutation.propose_variants(_genome())]
        self.assertEqual(len(ids), len(set(ids)))
        for gid in ids:
            self.assertRegex(gid, r"^[a-z][a-z0-9_]*$")


class Refusal(unittest.TestCase):
    def test_invalid_seed_raises_mutation_error(self):
        bad = BlueprintGenome(genome_id="Bad Id", seed=_genome().seed, purpose="x")
        with self.assertRaises(mutation.MutationError):
            mutation.propose_variants(bad)

    def test_hostile_dependency_names_yield_valid_ids(self):
        # a dep with dots/symbols must still produce a frozen-label id, not a crash or a bad id
        g = _genome(allowed=("some.weird/dep-name",))
        variants = mutation.drop_dependency(g) + mutation.harden_dependency(g)
        self.assertTrue(variants)
        for v in variants:
            self.assertRegex(v.genome_id, r"^[a-z][a-z0-9_]*$")

    def test_propose_crossovers_refuses_an_invalid_member(self):
        bad = BlueprintGenome(genome_id="Bad Id", seed=_genome().seed, purpose="x")
        with self.assertRaises(mutation.MutationError):
            mutation.propose_crossovers([_genome("a"), bad])

    def test_slug_falls_back_for_empty_or_leading_digit(self):
        self.assertEqual(mutation._slug("123"), "g_123")  # leading digit -> prefixed
        self.assertEqual(mutation._slug("@@@"), "g")  # all symbols -> a safe stub

    def test_no_allowed_deps_means_no_dependency_variants(self):
        g = _genome(allowed=())
        self.assertEqual(mutation.drop_dependency(g), [])
        self.assertEqual(mutation.harden_dependency(g), [])


class FailClosedGuards(unittest.TestCase):
    """A proposal that would not pass the gate for a human is dropped, never raised or emitted."""

    def test_a_gate_failing_proposal_is_dropped_not_raised(self):
        # empty purpose -> the mutant fails GEN02; drop_dependency returns [], no exception
        bad = BlueprintGenome(
            genome_id="ok_id", seed=_genome().seed, purpose="", allowed_dependencies=("x",)
        )
        self.assertEqual(mutation.drop_dependency(bad), [])

    def test_an_invalid_parent_id_never_yields_a_bad_label(self):
        bad = BlueprintGenome(
            genome_id="Bad Id", seed=_genome().seed, purpose="p", allowed_dependencies=("x",)
        )
        self.assertEqual(mutation.drop_dependency(bad), [])
        self.assertEqual(mutation.harden_dependency(bad), [])  # same guard on the harden path

    def test_harden_skips_a_dep_already_prohibited(self):
        both = BlueprintGenome(
            genome_id="g",
            seed=_genome().seed,
            purpose="p",
            allowed_dependencies=("x",),
            prohibited_dependencies=("x",),
        )
        self.assertEqual(mutation.harden_dependency(both), [])

    def test_crossover_of_gate_failing_parents_is_none(self):
        bad = BlueprintGenome(genome_id="ok_id", seed=_genome().seed, purpose="")
        self.assertIsNone(mutation.crossover(bad, bad))

    def test_propose_variants_without_a_numeric_budget_skips_the_tighter_variant(self):
        proposals = mutation.propose_variants(_genome(budgets=(("note", "fast"),)))
        self.assertTrue(all("tighter" not in p.genome_id for p in proposals))


class Rendering(unittest.TestCase):
    def test_render_empty(self):
        self.assertIn("no proposals", mutation.render([]))

    def test_render_lists_policy(self):
        out = mutation.render(mutation.propose_variants(_genome()))
        self.assertIn("propose_only/human_required", out)
        self.assertIn("human_decision_required", out)


if __name__ == "__main__":
    unittest.main()
