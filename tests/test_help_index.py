"""Test twin for help_index: acceptance + hostile/refusal cases."""

from __future__ import annotations

import dataclasses
import unittest

from kernel.shelf.help_index import HelpEntry, HelpError, HelpIndex


def _sample() -> HelpIndex:
    return HelpIndex.build(
        [
            HelpEntry("look", "inspect your surroundings", "core"),
            HelpEntry("go", "travel through an exit", "core", body="usage: go <exit>"),
            HelpEntry("grant", "grant a rank to an account", "admin"),
            HelpEntry("shutdown", "stop the server safely", "admin"),
            HelpEntry("forge_ignite", "spark a seed world", "seed"),
        ]
    )


class AcceptanceTests(unittest.TestCase):
    def test_topic_returns_right_entry(self) -> None:
        entry = _sample().topic("look")
        self.assertEqual(entry.purpose, "inspect your surroundings")
        self.assertEqual(entry.namespace, "core")

    def test_search_finds_by_name(self) -> None:
        self.assertEqual(_sample().search("forge"), ["forge_ignite"])

    def test_search_finds_by_purpose(self) -> None:
        # "rank" appears only in grant's purpose, not in any name.
        self.assertEqual(_sample().search("rank"), ["grant"])

    def test_search_is_case_insensitive(self) -> None:
        self.assertEqual(_sample().search("TRAVEL"), ["go"])

    def test_search_sorted_multi_hit(self) -> None:
        # "server"/"safely" both in shutdown; "spark"/"seed" in forge_ignite.
        self.assertEqual(_sample().search("s"), sorted(_sample().search("s")))

    def test_overview_groups_by_namespace(self) -> None:
        text = _sample().overview()
        self.assertIn("[admin]", text)
        self.assertIn("[core]", text)
        self.assertIn("[seed]", text)
        # admin sorts before core sorts before seed.
        self.assertLess(text.index("[admin]"), text.index("[core]"))
        self.assertLess(text.index("[core]"), text.index("[seed]"))

    def test_overview_lists_name_and_purpose(self) -> None:
        self.assertIn("look - inspect your surroundings", _sample().overview())

    def test_render_topic_includes_purpose_and_namespace(self) -> None:
        block = _sample().render_topic("grant")
        self.assertIn("grant (admin)", block)
        self.assertIn("grant a rank to an account", block)

    def test_render_topic_includes_body_when_present(self) -> None:
        self.assertIn("usage: go <exit>", _sample().render_topic("go"))

    def test_entry_is_frozen(self) -> None:
        entry = HelpEntry("look", "inspect", "core")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            entry.name = "peek"  # type: ignore[misc]


class HostileTests(unittest.TestCase):
    def test_unknown_topic_fails_loud_with_near_match(self) -> None:
        with self.assertRaises(HelpError) as ctx:
            _sample().topic("loo")
        self.assertIn("look", str(ctx.exception))

    def test_unknown_topic_no_match_still_fails(self) -> None:
        with self.assertRaises(HelpError) as ctx:
            _sample().topic("zzzzz")
        self.assertIn("zzzzz", str(ctx.exception))

    def test_render_topic_unknown_fails_loud(self) -> None:
        with self.assertRaises(HelpError):
            _sample().render_topic("nope")

    def test_duplicate_names_fail_loud(self) -> None:
        with self.assertRaises(HelpError) as ctx:
            HelpIndex.build(
                [
                    HelpEntry("look", "inspect", "core"),
                    HelpEntry("look", "peek again", "core"),
                ]
            )
        self.assertIn("duplicate", str(ctx.exception))

    def test_non_snake_case_name_fails_loud(self) -> None:
        for bad in ["Look", "go-fast", "two words", "_lead", "trail_", "up__down"]:
            with self.subTest(bad=bad), self.assertRaises(HelpError):
                HelpIndex.build([HelpEntry(bad, "x", "core")])

    def test_empty_query_fails_loud(self) -> None:
        with self.assertRaises(HelpError):
            _sample().search("")

    def test_whitespace_query_fails_loud(self) -> None:
        with self.assertRaises(HelpError):
            _sample().search("   ")

    def test_empty_overview_is_honest(self) -> None:
        self.assertEqual(HelpIndex.build([]).overview(), "(no help entries)")


if __name__ == "__main__":
    unittest.main()
