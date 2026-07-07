"""CARD: session -- one player's connection state.

A Session is everything that belongs to ONE player: identity,
position, liveness. World state stays canonical and SHARED;
sessions are each player's lens onto it.

This card deletes the engine's single-player assumption -- the
prerequisite for gateways. Tomorrow, every connected socket gets
its own Session pointed at the same world.
"""

from dataclasses import dataclass


@dataclass
class Session:
    """One player's seat at the world."""

    player_id: str
    location: str = "forge"
    alive: bool = True
