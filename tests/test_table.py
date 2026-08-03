"""Test twin for table.py (RD-2026-0007 Evennia evtable harvest).

Acceptance (alignment, headers, auto-width, wrapping, borderless), refusal (ragged rows, bad align,
bad max_width), and hostile data (empty cells, multi-line cells, unicode, over-long wrap).
"""

from __future__ import annotations

import unittest

from kernel.shelf import table as t


class Acceptance(unittest.TestCase):
    def test_basic_bordered_table_aligns_columns(self):
        out = t.render([["ab", "1"], ["c", "22"]], headers=["name", "n"])
        lines = out.splitlines()
        # every rendered line is the same visual width (columns line up)
        self.assertEqual(len({len(line) for line in lines}), 1)
        self.assertIn("| name | n  |", out)

    def test_right_align_numbers(self):
        out = t.render([["a", "5"], ["b", "100"]], align=["left", "right"], border=False)
        # the number column is right-justified to width 3
        self.assertIn("  5", out)
        self.assertIn("100", out)

    def test_per_column_alignment_list(self):
        out = t.render([["x", "y", "z"]], align=["left", "center", "right"])
        self.assertIn("x", out)  # smoke: mixed aligns accepted and rendered

    def test_headers_get_a_separator_row(self):
        out = t.render([["v"]], headers=["h"])
        self.assertEqual(out.count("+---"), 3 - 1 + 1)  # top, under-header, bottom borders present

    def test_auto_width_follows_widest_cell(self):
        out = t.render([["short"], ["a-much-longer-cell"]], border=False)
        self.assertTrue(all(len(line) == len("a-much-longer-cell") for line in out.splitlines()))

    def test_max_width_wraps_a_long_cell(self):
        out = t.render([["one two three four"]], max_widths=7, border=False)
        # wraps into multiple physical lines, none wider than 7
        self.assertGreater(len(out.splitlines()), 1)
        self.assertTrue(all(len(line) <= 7 for line in out.splitlines()))

    def test_borderless_uses_two_space_gutters(self):
        out = t.render([["a", "b"]], border=False)
        self.assertEqual(out, "a  b")

    def test_empty_input_is_empty_string(self):
        self.assertEqual(t.render([]), "")


class Hostile(unittest.TestCase):
    def test_blank_cells_are_padded_not_dropped(self):
        out = t.render([["", "x"]], border=False)
        self.assertEqual(out, "  x")  # width0=0 (empty col) -> "" + 2-space gutter + "x"

    def test_multiline_cell_expands_rows(self):
        out = t.render([["line1\nline2", "y"]], border=False)
        self.assertIn("line1", out)
        self.assertIn("line2", out)
        self.assertEqual(len(out.splitlines()), 2)

    def test_unicode_cell_renders(self):
        out = t.render([["café", "★"]], headers=["name", "mark"])
        self.assertIn("café", out)
        self.assertIn("★", out)

    def test_single_column(self):
        out = t.render([["a"], ["bb"]], headers=["h"], border=False)
        self.assertIn("bb", out)


class Refusal(unittest.TestCase):
    def test_ragged_rows_fail_loud(self):
        with self.assertRaises(t.TableError):
            t.render([["a", "b"], ["c"]])

    def test_header_width_mismatch_fails_loud(self):
        with self.assertRaises(t.TableError):
            t.render([["a", "b"]], headers=["only-one"])

    def test_bad_align_token_fails_loud(self):
        with self.assertRaises(t.TableError):
            t.render([["a"]], align="middle")

    def test_align_count_mismatch_fails_loud(self):
        with self.assertRaises(t.TableError):
            t.render([["a", "b"]], align=["left"])

    def test_non_positive_max_width_fails_loud(self):
        with self.assertRaises(t.TableError):
            t.render([["a"]], max_widths=0)


if __name__ == "__main__":
    unittest.main()
