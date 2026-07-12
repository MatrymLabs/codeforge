"""CARD: vitals -- the game adapter for the health registry: a world-vitals panel.

A player (or operator) runs `vitals` to see a green/amber/red panel of the world's subsystems: the
engine liveness, whether NPCs and callings loaded from the seed. Each is a check in a
`HealthRegistry` (parts/health). The SAME registry core backs a service-readiness probe in a
practical app (parts/service_health); only the adapter differs.
"""

from __future__ import annotations

from parts.health import HEALTHY, HealthRegistry, healthy_if
from parts.jobs import JOBS
from parts.npcs import NPCS
from parts.session import Session


def _build_registry() -> HealthRegistry:
    registry = HealthRegistry()
    registry.register("engine", lambda: HEALTHY)  # a liveness ping
    registry.register("npcs", healthy_if(lambda: bool(NPCS)))
    registry.register("callings", healthy_if(lambda: bool(JOBS)))
    return registry


def vitals(session: Session, arg: str = "") -> str:
    """The `vitals` verb: a health panel of the world's subsystems."""
    return _build_registry().report()
