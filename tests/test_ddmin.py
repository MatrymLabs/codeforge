"""Test twin for ddmin.py. It shrinks a failing input to the 1-minimal reproducer, keeps
the failure reproducing at every step, counts oracle calls, honours the max_calls cap,
handles string/line convenience wrappers, and refuses a non-failing input.

Run:  python3 -m unittest test_ddmin
"""

from __future__ import annotations

import unittest

from kernel.shelf.ddmin import DeltaError, ddmin, minimize_lines, minimize_string, render


class Minimization(unittest.TestCase):
    def test_reduces_to_the_required_pair(self):
        # the "bug" reproduces only when BOTH 7 and 13 are present
        seq = list(range(1, 31))

        def still_fails(subset: list[int]) -> bool:
            return 7 in subset and 13 in subset

        r = ddmin(seq, still_fails)
        self.assertEqual(set(r.minimal), {7, 13})
        self.assertTrue(r.is_one_minimal)

    def test_reduces_to_single_element(self):
        def still_fails(subset: list[int]) -> bool:
            return 42 in subset

        r = ddmin([1, 42, 3, 4, 5, 6], still_fails)
        self.assertEqual(r.minimal, (42,))

    def test_result_still_reproduces_the_failure(self):
        seq = list(range(50))

        def still_fails(subset: list[int]) -> bool:
            return 10 in subset and 20 in subset and 30 in subset

        r = ddmin(seq, still_fails)
        self.assertTrue(still_fails(list(r.minimal)))
        self.assertEqual(set(r.minimal), {10, 20, 30})

    def test_one_minimal_means_each_removal_passes(self):
        def still_fails(subset: list[int]) -> bool:
            return 2 in subset and 5 in subset

        r = ddmin([1, 2, 3, 4, 5], still_fails)
        for i in range(len(r.minimal)):
            shrunk = list(r.minimal[:i] + r.minimal[i + 1 :])
            self.assertFalse(still_fails(shrunk))  # removing any element must stop the failure


class Bookkeeping(unittest.TestCase):
    def test_original_size_and_calls_recorded(self):
        r = ddmin(list(range(10)), lambda s: 3 in s)
        self.assertEqual(r.original_size, 10)
        self.assertGreater(r.oracle_calls, 0)

    def test_duplicates_are_handled(self):
        # duplicate elements must not confuse the contiguous-chunk complement logic
        seq = [1, 1, 9, 1, 1, 9, 1]

        def still_fails(subset: list[int]) -> bool:
            return subset.count(9) >= 2

        r = ddmin(seq, still_fails)
        self.assertEqual(list(r.minimal), [9, 9])

    def test_max_calls_cap_returns_best_so_far_with_note(self):
        r = ddmin(list(range(100)), lambda s: 50 in s, max_calls=3)
        self.assertFalse(r.is_one_minimal)
        self.assertTrue(any("max_calls" in n for n in r.notes))


class Wrappers(unittest.TestCase):
    def test_minimize_string_to_trigger_substring(self):
        # failure reproduces whenever the text contains "!!"
        r = minimize_string("hello !! world", lambda s: "!!" in s)
        self.assertEqual("".join(r.minimal), "!!")

    def test_minimize_lines_to_the_offending_line(self):
        text = "ok\nok\nBOOM\nok\n"
        r = minimize_lines(text, lambda s: "BOOM" in s)
        self.assertEqual(list(r.minimal), ["BOOM"])


class Refusal(unittest.TestCase):
    def test_non_failing_full_input_refused(self):
        with self.assertRaises(DeltaError):
            ddmin([1, 2, 3], lambda s: False)

    def test_render_is_readable(self):
        out = render(ddmin(list(range(20)), lambda s: 7 in s and 12 in s))
        self.assertIn("delta debugging", out)
        self.assertIn("1-minimal", out)
        self.assertIn("minimal reproducer", out)


if __name__ == "__main__":
    unittest.main()
