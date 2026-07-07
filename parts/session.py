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


# The registry of connected sessions. Gateways and game_loop register
# here; 'who' reads it. One world, many seats.
SESSIONS: dict[str, Session] = {}


def roster() -> list[str]:
    """Names of everyone currently seated, alphabetized."""
    return sorted(SESSIONS)
