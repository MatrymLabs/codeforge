"""Test twin for corpus.py + the seed. Acceptance (records build, load, and query;
the honesty fields work), refusal (malformed records fail loud), and a load of the
real seed file to prove the schema round-trips the reverse-engineered knowledge.

Run:  python3 -m unittest test_corpus
"""

from __future__ import annotations

import unittest
from pathlib import Path

from kernel.shelf.corpus import (
    Contested,
    Corpus,
    CorpusError,
    Detection,
    Record,
    Transformation,
    load_yaml,
)

_SEED = Path(__file__).resolve().parent.parent / "data" / "coding_corpus.yaml"


def strategy() -> Record:
    return Record(
        id="PATTERN.GOF.STRATEGY",
        category="design",
        name="Strategy",
        subsumed_by="first-class functions",
        detection=Detection("ast_query", "class where a callable would do"),
        automatability="detectable",
    )


class RecordValidation(unittest.TestCase):
    def test_valid_record(self):
        r = strategy()
        self.assertEqual(r.category, "design")
        self.assertTrue(r.subsumed_by)

    def test_id_must_be_upper_dotted(self):
        for bad in ("", "lower.case", "NODOT", "Mixed.Case"):
            with self.assertRaises(CorpusError):
                Record(id=bad, category="design", name="x")

    def test_bad_category(self):
        with self.assertRaises(CorpusError):
            Record(id="X.Y", category="nonsense", name="x")

    def test_bad_automatability(self):
        with self.assertRaises(CorpusError):
            Record(id="X.Y", category="smell", name="x", automatability="magic")

    def test_bad_detection_method(self):
        with self.assertRaises(CorpusError):
            Detection("telepathy")

    def test_bad_transform_method(self):
        with self.assertRaises(CorpusError):
            Transformation("rewrite-everything")


class CorpusQueries(unittest.TestCase):
    def _corpus(self) -> Corpus:
        return Corpus.from_records(
            [
                strategy(),
                Record(
                    id="PATTERN.GOF.SINGLETON",
                    category="anti_pattern",
                    name="Singleton",
                    contested=Contested(True, "hidden global state", "consensus"),
                    automatability="detectable",
                ),
                Record(
                    id="SMELL.LONG_METHOD",
                    category="smell",
                    name="Long Method",
                    detection=Detection("metric", "length > N"),
                    transformation=Transformation("mechanical_refactor", ("Extract Method",)),
                    automatability="transformable",
                ),
            ]
        )

    def test_get_and_all(self):
        c = self._corpus()
        self.assertEqual(c.get("SMELL.LONG_METHOD").name, "Long Method")
        self.assertEqual(len(c.all()), 3)

    def test_by_category(self):
        self.assertEqual(len(self._corpus().by_category("design")), 1)

    def test_contested(self):
        contested = self._corpus().contested()
        self.assertEqual([r.id for r in contested], ["PATTERN.GOF.SINGLETON"])

    def test_subsumed(self):
        self.assertIn("PATTERN.GOF.STRATEGY", [r.id for r in self._corpus().subsumed()])

    def test_detectable(self):
        ids = {r.id for r in self._corpus().detectable()}
        self.assertIn("SMELL.LONG_METHOD", ids)

    def test_duplicate_id_rejected(self):
        c = self._corpus()
        with self.assertRaises(CorpusError):
            c.add(strategy())

    def test_unknown_id(self):
        with self.assertRaises(CorpusError):
            self._corpus().get("NOPE.X")


@unittest.skipUnless(_SEED.exists(), "seed present only in the engine repo, not the poured shelf")
class SeedFile(unittest.TestCase):
    def test_the_real_seed_loads_and_validates(self):
        corpus = load_yaml(_SEED.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(corpus.all()), 12)

    def test_the_seed_has_subsumed_patterns(self):
        corpus = load_yaml(_SEED.read_text(encoding="utf-8"))
        # the report's key point: encode subsumed_by so CodeForge discourages over-engineering
        subsumed = {r.id for r in corpus.subsumed()}
        self.assertTrue({"PATTERN.GOF.STRATEGY", "PATTERN.GOF.VISITOR"} <= subsumed)

    def test_the_seed_encodes_contested_laws(self):
        corpus = load_yaml(_SEED.read_text(encoding="utf-8"))
        contested = {r.id for r in corpus.contested()}
        self.assertTrue(
            {"PRINCIPLE.POSTELS_LAW", "PRINCIPLE.SOLID", "PATTERN.GOF.SINGLETON"} <= contested
        )

    def test_the_seed_has_a_smell_to_refactoring_pair(self):
        corpus = load_yaml(_SEED.read_text(encoding="utf-8"))
        smell = corpus.get("SMELL.LONG_METHOD")
        self.assertIsNotNone(smell.detection)
        self.assertIsNotNone(smell.transformation)
        assert smell.transformation is not None
        self.assertEqual(smell.transformation.method, "mechanical_refactor")

    def test_the_seed_has_a_security_taint_rule(self):
        corpus = load_yaml(_SEED.read_text(encoding="utf-8"))
        rule = corpus.get("RULE.TAINT.OS_SYSTEM")
        assert rule.detection is not None
        self.assertEqual(rule.detection.method, "dataflow")


if __name__ == "__main__":
    unittest.main()
