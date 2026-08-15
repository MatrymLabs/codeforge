"""CARD: engine -- the game-facing position contract.

The World Package owns the meaning of a player's position. The platform's seam instrument imports
this contract to measure two engines, but the game can consume its own contract without reaching
into the platform.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class NodePosition:
    """Engine-0D: position IS the node. D3."""

    room: str


@runtime_checkable
class Engine(Protocol):
    """The game-facing position contract shared by interchangeable engines."""

    name: str

    def place(self, room: str) -> object:
        """Put a session in a room, in this engine's own position representation."""
        ...

    def room_of(self, position: object) -> str:
        """Return the semantic room label for an engine-native position."""
        ...

    def carry_limit(self) -> int:
        """Return the engine-independent carry limit used by the seam battery."""
        ...


class Engine0D:
    """The text engine: position is a node on a graph. The engine CodeForge runs today."""

    name = "0D"

    def place(self, room: str) -> NodePosition:
        return NodePosition(room=room)

    def room_of(self, position: object) -> str:
        assert isinstance(position, NodePosition)
        return position.room

    def carry_limit(self) -> int:
        return 10
