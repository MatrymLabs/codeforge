"""CARD: service_health -- the practical adapter for the health registry: a service readiness probe.

The reverse of parts/vitals: the SAME `HealthRegistry` core aggregates a service's dependency checks
(database, cache, queue, upstreams) into a readiness answer. `ready()` is True only if every check
is healthy -- an unknown or failing dependency is never reported ready. This is the /healthz or
/readyz probe practical services expose; its cousins are liveness checks and dashboards.
"""

from __future__ import annotations

from collections.abc import Callable

from parts.shelf.health import HEALTHY, Check, HealthRegistry, healthy_if


class ServiceHealth:
    """A service's readiness: register dependency checks; ready() only when all are healthy."""

    def __init__(self) -> None:
        self._registry = HealthRegistry()

    def add(self, name: str, check: Check) -> None:
        """Register a check that returns a status string."""
        self._registry.register(name, check)

    def add_bool(self, name: str, predicate: Callable[[], bool]) -> None:
        """Register a check from a bool predicate (True -> healthy, False -> unhealthy)."""
        self._registry.register(name, healthy_if(predicate))

    def ready(self) -> bool:
        """True only when every registered check is healthy."""
        return self._registry.overall() == HEALTHY

    def report(self) -> str:
        """The full health panel (overall + per-check), for a status endpoint or log."""
        return self._registry.report()
