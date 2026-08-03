"""CARD: menu -- a pure branching interactive-menu state machine.

Nodes hold text and numbered options; each option points (goto) at another
node's key. The Menu is a validated directed graph: state is canonical, text
is a projection. No I/O lives here - no input(), no print(). Drivers (NPC
dialog, shops, char-creation) render a node, take a choice, and advance.

Clean-room harvest (pattern-not-code) of the branching-dialogue idea from
Evennia's utils/evmenu.py (BSD-3-Clause). No source was copied; only the
menu-as-graph pattern was learned and reforged for a pure, frameless API.

Attribution:
    Evennia game server, utils/evmenu.py, BSD-3-Clause.
    Copyright (c) Evennia contributors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")


class MenuError(ValueError):
    """Raised loud on a malformed menu graph or an illegal choice."""


@dataclass(frozen=True)
class Option:
    """One numbered branch: a label the reader sees, a goto it leads to."""

    label: str
    goto: str


@dataclass(frozen=True)
class Node:
    """A single menu state: a snake_case key, its text, its branches."""

    key: str
    text: str
    options: tuple[Option, ...]


@dataclass(frozen=True)
class Menu:
    """A validated dialogue graph. Build it through Menu.build, never raw."""

    nodes: dict[str, Node]
    start: str

    @staticmethod
    def build(nodes: list[Node], start: str) -> Menu:
        """Validate a node list into a Menu, or fail loud with MenuError.

        Checks: at least one node; every key is snake_case; keys are unique;
        start names an existing node; every option.goto targets an existing
        node (no dangling edges).
        """
        if not nodes:
            raise MenuError("a menu needs at least one node")

        by_key: dict[str, Node] = {}
        for node in nodes:
            if not _SNAKE_CASE.match(node.key):
                raise MenuError(f"node key is not snake_case: {node.key!r}")
            if node.key in by_key:
                raise MenuError(f"duplicate node key: {node.key!r}")
            by_key[node.key] = node

        if start not in by_key:
            raise MenuError(f"start node not in menu: {start!r}")

        for node in nodes:
            for option in node.options:
                if option.goto not in by_key:
                    raise MenuError(f"dangling goto {option.goto!r} from node {node.key!r}")

        return Menu(nodes=by_key, start=start)

    def node(self, key: str) -> Node:
        """Fetch a node by key, or fail loud with MenuError."""
        try:
            return self.nodes[key]
        except KeyError:
            raise MenuError(f"unknown node: {key!r}") from None

    def render(self, key: str) -> str:
        """Project a node to text: its body then its numbered options."""
        node = self.node(key)
        lines = [node.text]
        for index, option in enumerate(node.options, start=1):
            lines.append(f"{index}) {option.label}")
        return "\n".join(lines)

    def choose(self, key: str, choice: int) -> str:
        """Follow a 1-based option to its goto, or fail loud with MenuError."""
        node = self.node(key)
        if choice < 1 or choice > len(node.options):
            raise MenuError(
                f"choice {choice} out of range for node {key!r} (1..{len(node.options)})"
            )
        return node.options[choice - 1].goto

    def is_terminal(self, key: str) -> bool:
        """A node with no options is an end of the dialogue."""
        return len(self.node(key).options) == 0
