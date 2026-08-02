"""Test twin for kernel/evolution/emitter.py (RD-2026-0002 #10).

Keel first: an invalid genome is refused (fail-closed); the scaffold is PROPOSE-ONLY (bodies raise
NotImplementedError / fail, headers say a human approves). Then: emitted code/tests PARSE, the
target-specific stubs (interfaces->defs, obligations->tests), rough interfaces still parse, and the
default targets.
"""

from __future__ import annotations

import ast
import unittest

from kernel.evolution import emitter as em
from kernel.evolution.genome import BlueprintGenome, from_dict


def _genome(genome_id: str = "row_formatter", **overrides) -> BlueprintGenome:
    base = {
        "genome_id": genome_id,
        "seed": {
            "blueprint_id": f"{genome_id}_seed",
            "title": "Row Formatter",
            "intent": "format a fixed-width row",
            "requirements": ["pad to width"],
            "security": ["reject control chars"],
        },
        "purpose": "a fixed-width column formatter",
        "interfaces": ["format_row(text: str, width: int) -> str"],
        "invariants": ["output width is exact"],
        "allowed_dependencies": ["textwrap"],
        "resource_budgets": [["render_us", "50"]],
        "test_obligations": ["pads short input", "truncates long input"],
        "documentation_obligations": ["a CARD line"],
    }
    base.update(overrides)
    return from_dict(base)


class KeelSafety(unittest.TestCase):
    def test_an_invalid_genome_is_refused(self):
        bad = BlueprintGenome(genome_id="Bad Id", seed=_genome().seed, purpose="")
        with self.assertRaises(em.EmitterError):
            em.express(bad)

    def test_the_scaffold_is_propose_only(self):
        code = em.express(_genome()).file("row_formatter.py")
        self.assertIn("PROPOSE-ONLY", code)
        self.assertIn("A HUMAN implements", code)
        self.assertIn("raise NotImplementedError", code)

    def test_the_header_records_the_keel_policies(self):
        code = em.express(_genome()).file("row_formatter.py")
        self.assertIn("approval_policy=human_required", code)


class EmittedCodeParses(unittest.TestCase):
    def test_code_and_tests_are_valid_python(self):
        pheno = em.express(_genome())
        for fname in ("row_formatter.py", "test_row_formatter.py"):
            ast.parse(pheno.file(fname))  # would raise if not parseable

    def test_a_rough_interface_still_parses(self):
        # an interface that is NOT a clean signature must still yield parseable code
        pheno = em.express(_genome(interfaces=["does a thing, somehow"]))
        ast.parse(pheno.file("row_formatter.py"))

    def test_no_interfaces_emits_a_parseable_stub(self):
        pheno = em.express(_genome(interfaces=[]))
        ast.parse(pheno.file("row_formatter.py"))


class TargetStubs(unittest.TestCase):
    def test_interfaces_become_def_stubs(self):
        code = em.express(_genome()).file("row_formatter.py")
        self.assertIn("def format_row(text: str, width: int) -> str:", code)

    def test_test_obligations_become_test_stubs(self):
        tests = em.express(_genome()).file("test_row_formatter.py")
        self.assertIn("class Test_row_formatter", tests)
        self.assertIn("self.fail(", tests)
        self.assertEqual(tests.count("def test_"), 2)  # two obligations -> two stubs

    def test_config_and_docs_targets(self):
        pheno = em.express(
            _genome(expression_targets=["config", "docs"], security_policies=["no eval on input"])
        )
        cfg = pheno.file("row_formatter.config.py")
        self.assertIn("render_us = 50", cfg)
        self.assertIn("security policy: no eval on input", cfg)
        self.assertIn("[ ] a CARD line", pheno.file("row_formatter.md"))

    def test_config_scaffold_parses_as_python(self):
        cfg = em.express(_genome(expression_targets=["config"])).file("row_formatter.config.py")
        ast.parse(cfg)


class Targets(unittest.TestCase):
    def test_default_targets_are_code_and_tests(self):
        pheno = em.express(_genome(expression_targets=[]))
        names = [f for f, _ in pheno.files]
        self.assertEqual(names, ["row_formatter.py", "test_row_formatter.py"])

    def test_render_lists_the_files(self):
        out = em.render(em.express(_genome()))
        self.assertIn("PROPOSE-ONLY", out)
        self.assertIn("row_formatter.py", out)

    def test_phenotype_file_miss_returns_none(self):
        self.assertIsNone(em.express(_genome()).file("nope.py"))


class Slug(unittest.TestCase):
    def test_slug_fallback_for_leading_digit_or_symbols(self):
        self.assertEqual(em._slug("123"), "scaffold_123")
        self.assertEqual(em._slug("!!!"), "scaffold")


if __name__ == "__main__":
    unittest.main()
