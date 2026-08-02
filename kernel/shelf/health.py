"""CARD: health -- a health-check registry: run named checks, aggregate an honest overall status.

Register named checks; run them all; get a per-check result and an overall status (the worst one
wins). The load-bearing rule: an UNKNOWN state is NEVER reported as healthy. A check that raises, or
returns an unrecognized value, becomes UNKNOWN (not healthy); an empty registry is UNKNOWN (no
evidence is not health). This is the standard health/readiness pattern, reimplemented from the
concept -- no code copied.

Framework-free: a check is any `Callable[[], str]` returning a status; the registry catches its
failures so one broken check cannot crash the report. One core, two lives: a world-vitals panel in
the game (`parts/vitals`) and a service-readiness probe in a practical app (`parts/service_health`).

Provenance: independently_implemented_pattern (health-check registry). No code copied.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

HEALTHY, DEGRADED, UNKNOWN, UNHEALTHY = "healthy", "degraded", "unknown", "unhealthy"
_STATUSES = (HEALTHY, DEGRADED, UNKNOWN, UNHEALTHY)
# Severity, worst wins. UNKNOWN outranks DEGRADED so an unknown check is never called healthy.
_SEVERITY = {HEALTHY: 0, DEGRADED: 1, UNKNOWN: 2, UNHEALTHY: 3}

Check = Callable[[], str]


class HealthCheckError(ValueError):
    """A health check was registered badly (e.g. a duplicate name)."""


@dataclass(frozen=True)
class HealthResult:
    """One check's outcome: its name, its status, and an optional detail."""

    name: str
    status: str
    detail: str = ""


def healthy_if(predicate: Callable[[], bool]) -> Check:
    """Wrap a bool predicate as a check: True -> healthy, False -> unhealthy."""
    return lambda: HEALTHY if predicate() else UNHEALTHY


class HealthRegistry:
    """A registry of named checks. `overall()` is healthy only if every check is."""

    def __init__(self) -> None:
        self._checks: dict[str, Check] = {}

    def register(self, name: str, check: Check) -> None:
        """Add a named check. Raises HealthCheckError on a duplicate name."""
        if name in self._checks:
            raise HealthCheckError(f"a check named {name!r} is already registered")
        self._checks[name] = check

    def run(self) -> list[HealthResult]:
        """Run every check. A raising or unrecognized check becomes UNKNOWN, never healthy."""
        results: list[HealthResult] = []
        for name, check in self._checks.items():
            try:
                value = check()
            except Exception as exc:  # a broken check must not crash the report
                results.append(HealthResult(name, UNKNOWN, f"check raised: {exc!r}"))
                continue
            if value in _STATUSES:
                results.append(HealthResult(name, value))
            else:
                results.append(HealthResult(name, UNKNOWN, f"unrecognized status {value!r}"))
        return results

    def overall(self) -> str:
        """The worst status across all checks. An empty registry is UNKNOWN (no evidence)."""
        results = self.run()
        if not results:
            return UNKNOWN
        return max((r.status for r in results), key=lambda s: _SEVERITY[s])

    def report(self) -> str:
        """A readable panel: the overall status and each check."""
        results = self.run()
        lines = [f"HEALTH: {self.overall()}"]
        for r in results:
            suffix = f"  ({r.detail})" if r.detail else ""
            lines.append(f"  [{r.status:<9}] {r.name}{suffix}")
        return "\n".join(lines)
