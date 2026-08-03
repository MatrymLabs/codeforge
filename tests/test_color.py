"""CARD: test_color -- twin for the color markup renderer.

Acceptance cases prove tags become escapes, strip cleans, `||` is a literal
pipe, visible_len ignores tags, and a reset is always appended. Hostile cases
prove unknown tags, empty strings, tag-free text, and a dangling pipe are all
handled loud and correct.
"""

from __future__ import annotations

import unittest

from kernel.shelf import color
from kernel.shelf.color import ColorError, colorize, render, strip, visible_len

_ESC = "\033["
_RESET = _ESC + "0m"


class AcceptanceTests(unittest.TestCase):
    def test_tag_becomes_escape(self) -> None:
        out = colorize("|rhot")
        self.assertIn(_ESC + "31m", out)
        self.assertIn("hot", out)

    def test_bright_tag_distinct_from_normal(self) -> None:
        self.assertIn(_ESC + "91m", colorize("|Rx"))
        self.assertIn(_ESC + "31m", colorize("|rx"))

    def test_strip_removes_tags(self) -> None:
        self.assertEqual(strip("|rhot|n cocoa"), "hot cocoa")

    def test_double_pipe_is_literal(self) -> None:
        self.assertEqual(colorize("a||b"), "a|b")
        self.assertEqual(strip("a||b"), "a|b")

    def test_double_pipe_not_treated_as_tag(self) -> None:
        # `||r` is a literal pipe followed by a plain `r`, not a red tag.
        self.assertEqual(colorize("||r"), "|r")

    def test_visible_len_ignores_tags(self) -> None:
        self.assertEqual(visible_len("|rhot|n"), 3)
        self.assertEqual(visible_len("a||b"), 3)

    def test_reset_appended_when_color_used(self) -> None:
        self.assertTrue(colorize("|rhot").endswith(_RESET))

    def test_no_reset_when_no_color(self) -> None:
        self.assertEqual(colorize("plain text"), "plain text")

    def test_explicit_reset_not_doubled(self) -> None:
        out = colorize("|rhot|n")
        self.assertTrue(out.endswith(_RESET))
        self.assertFalse(out.endswith(_RESET + _RESET))

    def test_rgb_cube_becomes_256_escape(self) -> None:
        # 5,0,0 -> 16 + 36*5 + 0 + 0 = 196 (bright red corner of the cube).
        self.assertIn(_ESC + "38;5;196m", colorize("|500x"))

    def test_grey_tag(self) -> None:
        self.assertIn(_ESC + "30m", colorize("|xshadow"))

    def test_render_switches_on_color_flag(self) -> None:
        self.assertIn(_ESC + "31m", render("|rhot", color=True))
        self.assertEqual(render("|rhot", color=False), "hot")


class RefusalTests(unittest.TestCase):
    def test_unknown_tag_fails_loud(self) -> None:
        with self.assertRaises(ColorError):
            colorize("|Zoops")

    def test_unknown_tag_fails_loud_in_strip(self) -> None:
        with self.assertRaises(ColorError):
            strip("|Zoops")

    def test_colorerror_is_valueerror(self) -> None:
        self.assertTrue(issubclass(ColorError, ValueError))

    def test_empty_string(self) -> None:
        self.assertEqual(colorize(""), "")
        self.assertEqual(strip(""), "")
        self.assertEqual(visible_len(""), 0)

    def test_text_with_no_tags_unchanged(self) -> None:
        plain = "just some words"
        self.assertEqual(colorize(plain), plain)
        self.assertEqual(strip(plain), plain)

    def test_lone_trailing_pipe_fails_loud(self) -> None:
        with self.assertRaises(ColorError):
            colorize("hot|")
        with self.assertRaises(ColorError):
            strip("hot|")

    def test_partial_rgb_cube_is_unknown_tag(self) -> None:
        # `|5` is a single unknown code char, not a full three-digit cube.
        with self.assertRaises(ColorError):
            colorize("|5x")

    def test_out_of_range_cube_digits_are_not_matched(self) -> None:
        # `|600` has a 6 (out of 0-5); the token engine reads `|6` as a tag.
        with self.assertRaises(ColorError):
            colorize("|600")

    def test_module_exports(self) -> None:
        for name in ("ColorError", "colorize", "strip", "render", "visible_len"):
            self.assertIn(name, color.__all__)


if __name__ == "__main__":
    unittest.main()
