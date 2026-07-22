# Pattern family: Observability

*Fourth family doc for the Hardware Store's pattern shelf. Research basis: "Full-Stack Design Patterns
for CodeForge" (section 15, Telemetry / Observability). This doc covers the health-check registry;
structured logs and metrics already ship as the separate `observability` part.*

## Provenance

- **Origin:** `independently_implemented_pattern`. The health-check / readiness-probe pattern is a
  standard operations practice (Kubernetes liveness/readiness, `/healthz`). **No code was copied**;
  the behavior was reimplemented from the concept.
- **Independently implemented:** the registry, the status severity ordering, the "unknown is never
  healthy" rule, the failure containment, and both adapters.
- **License:** MIT · **owner:** MatrymLabs · **human review:** built and reviewed this session.

## The part: `health-registry`

`parts/shelf/health.py` -- a `HealthRegistry` of named checks (each a `Callable[[], str]` returning a
status, or a bool via `healthy_if`). `run()` returns a `HealthResult` per check; `overall()`
aggregates by **worst-wins** severity; `report()` renders a panel. The **load-bearing rule**: an
**UNKNOWN state is never reported as healthy**. A check that raises or returns an unrecognized value
becomes `UNKNOWN` (contained, never crashing the report), and an empty registry is `UNKNOWN` -- no
evidence is not the same as health.

**Invariants (tested, incl. property-based):** overall is `healthy` iff every check is healthy; a
raising check is `unknown`, not healthy; the worst status wins. It reports health; it does **not**
prove a system is secure or compliant.

## GAME-TO-PRACTICAL TRANSLATION

- **Game component:** a world-vitals panel (`parts/vitals.py`).
- **Core behavior:** run subsystem checks and report an honest aggregate status.
- **Game-specific presentation:** "HEALTH: healthy" with engine / npcs / callings rows.
- **Reusable domain logic:** the whole `HealthRegistry` (game-free).
- **Practical applications:** `/healthz` and `/readyz` probes, dashboards, ops alerts.
- **Required abstraction:** a check as a plain callable + a severity aggregation; already in the core.
- **Adapters required:** a game verb; a practical readiness probe.
- **Security implications:** never report a degraded/unknown control as an all-clear.
- **Testing implications:** the "unknown is never healthy" invariant; worst-wins aggregation.
- **Hardware Store candidate:** YES (stocked as `health-registry`).

## Adapters (one core, two lives)

- **Game:** `parts/vitals.py` -- the `vitals` verb renders a panel of the world's subsystems
  (engine liveness, NPCs and callings loaded from the seed). Tick-reachable.
- **Practical:** `parts/service_health.py` -- `ServiceHealth` aggregates dependency checks;
  `ready()` is True only when all are healthy. A `/readyz` probe for any service.

## Evidence

- Tests: `tests/test_health.py` (unit + property), `tests/test_vitals.py` (game + tick),
  `tests/test_service_health.py` (practical + a one-core proof).
- Manifest: `docs/hardware/health-registry.yaml`. Trace it: `make loop PART=health-registry`.
- **Maturity: `beta`** -- demonstrated in two contexts and tested, but not `stable` (no async checks,
  timeouts, or HTTP endpoint yet).

## Deferred (needs Josh's approval)

Async checks with timeouts, an HTTP `/healthz` endpoint, and Prometheus export are later slices.
