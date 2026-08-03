"""Test twin for menu.py: the branching-menu graph, proven both ways.

Acceptance cases confirm the graph renders, advances, and detects terminals;
refusal cases confirm every malformed graph and illegal choice fails loud.
Hostile data (dangling edges, dupes, bad keys, zero/negative choices) is on
purpose - an all-happy suite once hid real bugs.
"""

from __future__ import annotations

import unittest

from kernel.shelf.menu import Menu, MenuError, Node, Option


def _dialog_tree() -> Menu:
    """A 3-node NPC dialog: greeting -> a branch -> two terminal ends."""
    nodes = [
        Node(
            key="greeting",
            text="The smith looks up. What do you need?",
            options=(
                Option(label="Ask about wares", goto="wares"),
                Option(label="Leave", goto="farewell"),
            ),
        ),
        Node(
            key="wares",
            text="Fine steel, forged today.",
            options=(),
        ),
        Node(
            key="farewell",
            text="Safe travels.",
            options=(),
        ),
    ]
    return Menu.build(nodes, start="greeting")


class AcceptanceTests(unittest.TestCase):
    def test_build_returns_menu_with_start(self) -> None:
        menu = _dialog_tree()
        self.assertEqual(menu.start, "greeting")

    def test_node_fetches_by_key(self) -> None:
        menu = _dialog_tree()
        self.assertEqual(menu.node("wares").text, "Fine steel, forged today.")

    def test_render_numbers_options(self) -> None:
        menu = _dialog_tree()
        rendered = menu.render("greeting")
        self.assertIn("1) Ask about wares", rendered)
        self.assertIn("2) Leave", rendered)
        self.assertTrue(rendered.startswith("The smith looks up."))

    def test_render_terminal_has_no_numbers(self) -> None:
        menu = _dialog_tree()
        self.assertEqual(menu.render("farewell"), "Safe travels.")

    def test_choose_follows_goto(self) -> None:
        menu = _dialog_tree()
        self.assertEqual(menu.choose("greeting", 1), "wares")
        self.assertEqual(menu.choose("greeting", 2), "farewell")

    def test_terminal_node_detected(self) -> None:
        menu = _dialog_tree()
        self.assertTrue(menu.is_terminal("wares"))
        self.assertFalse(menu.is_terminal("greeting"))

    def test_full_walk_start_to_end(self) -> None:
        menu = _dialog_tree()
        here = menu.start
        self.assertFalse(menu.is_terminal(here))
        here = menu.choose(here, 1)
        self.assertEqual(here, "wares")
        self.assertTrue(menu.is_terminal(here))

    def test_single_node_menu_builds(self) -> None:
        menu = Menu.build([Node(key="only", text="hi", options=())], "only")
        self.assertTrue(menu.is_terminal("only"))


class RefusalTests(unittest.TestCase):
    def test_empty_node_list_fails(self) -> None:
        with self.assertRaises(MenuError):
            Menu.build([], start="anything")

    def test_dangling_goto_fails(self) -> None:
        nodes = [
            Node(
                key="root",
                text="go",
                options=(Option(label="onward", goto="nowhere"),),
            ),
        ]
        with self.assertRaises(MenuError):
            Menu.build(nodes, start="root")

    def test_duplicate_keys_fail(self) -> None:
        nodes = [
            Node(key="dup", text="a", options=()),
            Node(key="dup", text="b", options=()),
        ]
        with self.assertRaises(MenuError):
            Menu.build(nodes, start="dup")

    def test_start_not_in_nodes_fails(self) -> None:
        nodes = [Node(key="real", text="a", options=())]
        with self.assertRaises(MenuError):
            Menu.build(nodes, start="ghost")

    def test_non_snake_case_key_fails(self) -> None:
        nodes = [Node(key="NotSnake", text="a", options=())]
        with self.assertRaises(MenuError):
            Menu.build(nodes, start="NotSnake")

    def test_leading_digit_key_fails(self) -> None:
        nodes = [Node(key="1bad", text="a", options=())]
        with self.assertRaises(MenuError):
            Menu.build(nodes, start="1bad")

    def test_choose_out_of_range_high_fails(self) -> None:
        menu = _dialog_tree()
        with self.assertRaises(MenuError):
            menu.choose("greeting", 3)

    def test_choose_zero_fails(self) -> None:
        menu = _dialog_tree()
        with self.assertRaises(MenuError):
            menu.choose("greeting", 0)

    def test_choose_negative_fails(self) -> None:
        menu = _dialog_tree()
        with self.assertRaises(MenuError):
            menu.choose("greeting", -1)

    def test_choose_on_terminal_fails(self) -> None:
        menu = _dialog_tree()
        with self.assertRaises(MenuError):
            menu.choose("wares", 1)

    def test_node_unknown_key_fails(self) -> None:
        menu = _dialog_tree()
        with self.assertRaises(MenuError):
            menu.node("missing")

    def test_render_unknown_key_fails(self) -> None:
        menu = _dialog_tree()
        with self.assertRaises(MenuError):
            menu.render("missing")


if __name__ == "__main__":
    unittest.main()
