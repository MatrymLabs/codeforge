"""Test twin for health_bar.py (RD-2026-0007 Evennia health_bar harvest).

Acceptance (full/empty/partial fills, honest edges, custom glyphs, numbers, no-numbers), refusal
(max <= 0, negative value, over-max, width < 1, multi-char glyph fail loud).
"""

from __future__ import annotations

import unittest

from kernel.shelf import health_bar as h


class Acceptance(unittest.TestCase):
    def test_full_bar(self):
        self.assertEqual(h.bar(20, 20, width=5), "[#####] 20/20")

    def test_empty_bar(self):
        self.assertEqual(h.bar(0, 20, width=5), "[-----] 0/20")

    def test_half_bar(self):
        self.assertEqual(h.bar(10, 20, width=10), "[#####-----] 10/20")

    def test_nonzero_never_fully_empty(self):
        # 1/1000 over width 10 rounds to 0 cells, but a live value keeps at least one filled cell
        self.assertTrue(h.bar(1, 1000, width=10).startswith("[#"))

    def test_below_max_never_fully_full(self):
        # 999/1000 rounds to 10 cells, but a non-max value keeps at least one empty cell
        self.assertTrue(h.bar(999, 1000, width=10).count("-") >= 1)

    def test_custom_glyphs(self):
        self.assertEqual(h.bar(2, 4, width=4, filled="=", empty=".", show_numbers=False), "[==..]")

    def test_numbers_drop_trailing_zero(self):
        self.assertIn("12/20", h.bar(12, 20))

    def test_float_values_render(self):
        self.assertIn("2.5/5", h.bar(2.5, 5, width=4))


class Refusal(unittest.TestCase):
    def test_non_positive_maximum_fails_loud(self):
        with self.assertRaises(h.HealthBarError):
            h.bar(0, 0)

    def test_negative_value_fails_loud(self):
        with self.assertRaises(h.HealthBarError):
            h.bar(-1, 20)

    def test_over_max_fails_loud(self):
        with self.assertRaises(h.HealthBarError):
            h.bar(21, 20)

    def test_zero_width_fails_loud(self):
        with self.assertRaises(h.HealthBarError):
            h.bar(5, 20, width=0)

    def test_multi_char_glyph_fails_loud(self):
        with self.assertRaises(h.HealthBarError):
            h.bar(5, 20, filled="##")


if __name__ == "__main__":
    unittest.main()
