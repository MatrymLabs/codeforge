"""Test twin for the minimap part: acceptance + hostile/refusal cases."""

from __future__ import annotations

import unittest

from kernel.shelf.minimap import Graph, MinimapError, render


def _bracket_count(rendered: str) -> int:
    """How many room cells were drawn (each cell opens with a '[')."""
    return rendered.count("[")


class AcceptanceTests(unittest.TestCase):
    def test_single_room_is_just_the_center_marker(self) -> None:
        graph: Graph = {"a": {}}
        out = render(graph, "a")
        self.assertEqual(out, "[@]")

    def test_center_is_marked_with_at_sign(self) -> None:
        graph: Graph = {"a": {}}
        out = render(graph, "a")
        self.assertIn("@", out)
        self.assertEqual(out.count("@"), 1)

    def test_east_neighbour_draws_horizontal_connector(self) -> None:
        graph: Graph = {"a": {"e": "b"}, "b": {"w": "a"}}
        out = render(graph, "a")
        # center on the left, dash connector, a second bracketed cell right of it.
        self.assertEqual(out, "[@]-[ ]")
        self.assertIn("-", out)
        self.assertEqual(_bracket_count(out), 2)

    def test_west_neighbour_puts_center_on_the_right(self) -> None:
        graph: Graph = {"a": {"w": "b"}, "b": {"e": "a"}}
        out = render(graph, "a")
        self.assertEqual(out, "[ ]-[@]")

    def test_north_neighbour_draws_vertical_connector_above_center(self) -> None:
        graph: Graph = {"a": {"n": "b"}, "b": {"s": "a"}}
        out = render(graph, "a")
        lines = out.split("\n")
        at_line = next(i for i, ln in enumerate(lines) if "@" in ln)
        pipe_line = next(i for i, ln in enumerate(lines) if "|" in ln)
        # the connector sits on a line above the center room.
        self.assertLess(pipe_line, at_line)
        self.assertIn("|", out)

    def test_south_neighbour_draws_vertical_connector_below_center(self) -> None:
        graph: Graph = {"a": {"s": "b"}, "b": {"n": "a"}}
        out = render(graph, "a")
        lines = out.split("\n")
        at_line = next(i for i, ln in enumerate(lines) if "@" in ln)
        pipe_line = next(i for i, ln in enumerate(lines) if "|" in ln)
        self.assertGreater(pipe_line, at_line)

    def test_full_cross_renders_five_rooms(self) -> None:
        graph: Graph = {
            "c": {"n": "n1", "s": "s1", "e": "e1", "w": "w1"},
            "n1": {"s": "c"},
            "s1": {"n": "c"},
            "e1": {"w": "c"},
            "w1": {"e": "c"},
        }
        out = render(graph, "c")
        self.assertEqual(_bracket_count(out), 5)
        self.assertIn("@", out)
        self.assertIn("-", out)
        self.assertIn("|", out)

    def test_radius_limits_how_far_it_draws(self) -> None:
        # chain: a -e-> b -e-> c -e-> d
        graph: Graph = {
            "a": {"e": "b"},
            "b": {"w": "a", "e": "c"},
            "c": {"w": "b", "e": "d"},
            "d": {"w": "c"},
        }
        self.assertEqual(_bracket_count(render(graph, "a", radius=0)), 1)
        self.assertEqual(_bracket_count(render(graph, "a", radius=1)), 2)
        self.assertEqual(_bracket_count(render(graph, "a", radius=2)), 3)
        self.assertEqual(_bracket_count(render(graph, "a", radius=3)), 4)

    def test_radius_zero_draws_only_center(self) -> None:
        graph: Graph = {"a": {"e": "b"}, "b": {"w": "a"}}
        self.assertEqual(render(graph, "a", radius=0), "[@]")

    def test_render_is_deterministic(self) -> None:
        graph: Graph = {
            "c": {"n": "n1", "e": "e1"},
            "n1": {"s": "c"},
            "e1": {"w": "c"},
        }
        self.assertEqual(render(graph, "c"), render(graph, "c"))

    def test_up_down_exits_are_noted_in_footer(self) -> None:
        graph: Graph = {"a": {"u": "b"}, "b": {"d": "a"}}
        out = render(graph, "a")
        self.assertIn("[@]", out)
        self.assertIn("u/d exits present", out)


class RefusalTests(unittest.TestCase):
    def test_center_absent_fails_loud(self) -> None:
        graph: Graph = {"a": {}}
        with self.assertRaises(MinimapError):
            render(graph, "ghost")

    def test_negative_radius_fails_loud(self) -> None:
        graph: Graph = {"a": {}}
        with self.assertRaises(MinimapError):
            render(graph, "a", radius=-1)

    def test_dangling_exit_fails_loud(self) -> None:
        graph: Graph = {"a": {"e": "ghost"}}
        with self.assertRaises(MinimapError):
            render(graph, "a")

    def test_disconnected_room_is_omitted(self) -> None:
        # z is unreachable from a; it must not appear on the map.
        graph: Graph = {"a": {"e": "b"}, "b": {"w": "a"}, "z": {}}
        out = render(graph, "a", radius=5)
        self.assertEqual(_bracket_count(out), 2)


if __name__ == "__main__":
    unittest.main()
