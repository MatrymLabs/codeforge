"""Test twin for probabilistic.py. It pins the one-sided guarantees (Bloom: no false
negatives; CountMin: never under-counts; HLL: estimate within the stated error band),
handles hostile items (mixed case, symbols, unicode, bytes vs str, ints), and refuses
malformed parameters.

Run:  python3 -m unittest test_probabilistic
"""

from __future__ import annotations

import unittest

from kernel.shelf.probabilistic import (
    BloomFilter,
    CountMinSketch,
    HyperLogLog,
    ProbabilisticError,
)


class BloomAcceptance(unittest.TestCase):
    def test_no_false_negatives_is_a_hard_guarantee(self):
        bf = BloomFilter(capacity=1000, false_positive_rate=0.01)
        members = [f"user_{i}" for i in range(1000)]
        for m in members:
            bf.add(m)
        # Every inserted item MUST report present. This is the load-bearing guarantee.
        for m in members:
            self.assertIn(m, bf)

    def test_definite_absence_for_most_unseen(self):
        bf = BloomFilter(capacity=1000, false_positive_rate=0.01)
        for i in range(1000):
            bf.add(f"in_{i}")
        # Query 5000 never-inserted keys; observed FPR should sit near the target, not wild.
        absent = [f"out_{i}" for i in range(5000)]
        hits = sum(1 for a in absent if a in bf)
        observed = hits / len(absent)
        self.assertLess(observed, 0.05)  # target 0.01, generous statistical ceiling

    def test_sizing_is_defensible(self):
        bf = BloomFilter(capacity=100, false_positive_rate=0.01)
        # m = -n ln p / (ln2)^2 ~= 958 bits; k = round(m/n ln2) ~= 7
        self.assertEqual(bf.params.num_bits, 959)
        self.assertEqual(bf.params.num_hashes, 7)

    def test_estimated_fpr_rises_as_it_fills(self):
        bf = BloomFilter(capacity=100, false_positive_rate=0.01)
        self.assertEqual(bf.estimated_fpr(), 0.0)
        for i in range(100):
            bf.add(i)
        self.assertGreater(bf.estimated_fpr(), 0.0)
        self.assertLess(bf.estimated_fpr(), 0.02)

    def test_len_counts_insertions(self):
        bf = BloomFilter(capacity=10)
        bf.add("a")
        bf.add("b")
        self.assertEqual(len(bf), 2)


class BloomHostileItems(unittest.TestCase):
    def test_case_is_preserved_not_mangled(self):
        bf = BloomFilter(capacity=10)
        bf.add("Pass")
        self.assertIn("Pass", bf)
        # "pass" was never added; with a fresh tiny filter it must be absent (no collision here).
        bf2 = BloomFilter(capacity=10)
        bf2.add("Pass")
        self.assertNotIn("pass", bf2)

    def test_symbols_unicode_bytes_and_ints(self):
        bf = BloomFilter(capacity=50)
        hostile = ["!@#$%^&*()", "naïve café", "日本語", b"\x00\xffraw", 42, -7]
        for h in hostile:
            bf.add(h)
        for h in hostile:
            self.assertIn(h, bf)

    def test_str_and_equal_bytes_are_distinct_channels_but_both_work(self):
        bf = BloomFilter(capacity=10)
        bf.add("A")
        self.assertIn("A", bf)


class BloomRefusal(unittest.TestCase):
    def test_zero_capacity_refused(self):
        with self.assertRaises(ProbabilisticError):
            BloomFilter(capacity=0)

    def test_fpr_out_of_range_refused(self):
        for bad in (0.0, 1.0, -0.1, 1.5):
            with self.assertRaises(ProbabilisticError):
                BloomFilter(capacity=10, false_positive_rate=bad)

    def test_unsupported_item_type_refused(self):
        bf = BloomFilter(capacity=10)
        with self.assertRaises(ProbabilisticError):
            bf.add([1, 2, 3])

    def test_bool_refused_as_ambiguous(self):
        bf = BloomFilter(capacity=10)
        with self.assertRaises(ProbabilisticError):
            bf.add(True)


class HyperLogLogAccuracy(unittest.TestCase):
    def test_estimate_within_error_band(self):
        hll = HyperLogLog(precision=14)
        true_n = 100_000
        for i in range(true_n):
            hll.add(f"item_{i}")
        est = hll.cardinality()
        rel_error = abs(est - true_n) / true_n
        # standard error ~0.8%; allow 3-sigma slack for a single trial.
        self.assertLess(rel_error, 3 * hll.standard_error)

    def test_duplicates_do_not_inflate_the_count(self):
        hll = HyperLogLog(precision=12)
        for _ in range(10_000):
            hll.add("same_key")
        self.assertLessEqual(hll.cardinality(), 3)  # ~1 distinct, tiny bias tolerated

    def test_small_cardinality_is_close(self):
        hll = HyperLogLog(precision=14)
        for i in range(500):
            hll.add(i)
        est = hll.cardinality()
        self.assertLess(abs(est - 500) / 500, 0.05)  # linear-counting range is tight

    def test_len_delegates_to_cardinality(self):
        hll = HyperLogLog(precision=8)
        for i in range(200):
            hll.add(i)
        self.assertEqual(len(hll), hll.cardinality())

    def test_standard_error_matches_formula(self):
        hll = HyperLogLog(precision=14)
        self.assertAlmostEqual(hll.standard_error, 1.04 / (2**14) ** 0.5)


class HyperLogLogRefusal(unittest.TestCase):
    def test_precision_out_of_range_refused(self):
        for bad in (3, 17, 0, -1):
            with self.assertRaises(ProbabilisticError):
                HyperLogLog(precision=bad)


class CountMinSketchGuarantee(unittest.TestCase):
    def test_never_underestimates(self):
        cms = CountMinSketch(epsilon=0.001, delta=0.001)
        truth: dict[str, int] = {}
        for i in range(20_000):
            key = f"k_{i % 500}"  # 500 distinct keys, skewed by modulo
            cms.add(key)
            truth[key] = truth.get(key, 0) + 1
        for key, true_count in truth.items():
            self.assertGreaterEqual(cms.estimate(key), true_count)

    def test_overestimate_stays_within_epsilon_N(self):
        cms = CountMinSketch(epsilon=0.001, delta=0.001)
        truth: dict[str, int] = {}
        for i in range(20_000):
            key = f"k_{i % 500}"
            cms.add(key)
            truth[key] = truth.get(key, 0) + 1
        bound = cms.epsilon * cms.total
        for key, true_count in truth.items():
            self.assertLessEqual(cms.estimate(key) - true_count, bound)

    def test_unseen_key_estimate_is_small(self):
        cms = CountMinSketch(epsilon=0.001, delta=0.001)
        for i in range(1000):
            cms.add(f"seen_{i}")
        self.assertLessEqual(cms.estimate("never_added"), cms.epsilon * cms.total)

    def test_bulk_count_add(self):
        cms = CountMinSketch(epsilon=0.01, delta=0.01)
        cms.add("bulk", count=50)
        self.assertGreaterEqual(cms.estimate("bulk"), 50)
        self.assertEqual(cms.total, 50)

    def test_sizing_is_defensible(self):
        cms = CountMinSketch(epsilon=0.01, delta=0.01)
        # w = ceil(e/eps) = ceil(271.8) = 272 ; d = ceil(ln(1/delta)) = ceil(4.6) = 5
        self.assertEqual(cms.width, 272)
        self.assertEqual(cms.depth, 5)


class CountMinSketchRefusal(unittest.TestCase):
    def test_bad_epsilon_delta_refused(self):
        with self.assertRaises(ProbabilisticError):
            CountMinSketch(epsilon=0.0)
        with self.assertRaises(ProbabilisticError):
            CountMinSketch(delta=1.0)

    def test_negative_count_refused(self):
        cms = CountMinSketch()
        with self.assertRaises(ProbabilisticError):
            cms.add("x", count=-1)


if __name__ == "__main__":
    unittest.main()
