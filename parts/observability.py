"""CARD: observability -- structured logs (structlog) + a Prometheus /metrics endpoint.

The forge's telemetry. Two senior-grade signals, wired onto the FastAPI surface:

- **Structured logs** via structlog: every HTTP request is one JSON event (method, path,
  status, duration) instead of a prose line, so logs are queryable, not just readable.
- **Metrics** at `GET /metrics` in Prometheus text-exposition format: request counts and
  latency by method, route template, and status. The registry is stdlib (a tiny thread-safe
  counter table) -- we render the exposition format ourselves, no scraping library.

One HTTP middleware times each request, emits the structured log, and records the metric.
Route TEMPLATES (e.g. `/ui/blueprint/{blueprint_id}`) are used, never raw paths, so metric
cardinality stays bounded.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import TYPE_CHECKING

import structlog
from fastapi.responses import Response

if TYPE_CHECKING:
    from fastapi import FastAPI, Request

# Prometheus text exposition wants this exact content type.
_PROM_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

_configured = False


def configure_logging() -> None:
    """Configure structlog to emit JSON events (idempotent). Called once at app start."""
    global _configured
    if _configured:
        return
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str = "codeforge") -> structlog.stdlib.BoundLogger:
    """A structured logger. Configures logging on first use so callers need no setup."""
    configure_logging()
    return structlog.get_logger(name)


class Metrics:
    """A tiny, thread-safe metrics registry rendered as Prometheus text exposition.

    Records a request count and a latency sum/count per (method, route, status) -- enough for
    rate and average-latency queries. Not a full histogram (no buckets); labeled honestly."""

    def __init__(self) -> None:
        self._count: dict[tuple[str, str, str], int] = defaultdict(int)
        self._dur_sum: dict[tuple[str, str, str], float] = defaultdict(float)
        self._lock = Lock()

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        key = (method, route, str(status))
        with self._lock:
            self._count[key] += 1
            self._dur_sum[key] += seconds

    def reset(self) -> None:
        """Clear all series (for tests)."""
        with self._lock:
            self._count.clear()
            self._dur_sum.clear()

    def render(self) -> str:
        """The Prometheus text exposition of every recorded series."""
        lines = [
            "# HELP codeforge_requests_total Total HTTP requests.",
            "# TYPE codeforge_requests_total counter",
        ]
        with self._lock:
            counts = dict(self._count)
            sums = dict(self._dur_sum)
        for (method, route, status), n in sorted(counts.items()):
            lines.append(f"codeforge_requests_total{{{_labels(method, route, status)}}} {n}")
        lines += [
            "# HELP codeforge_request_duration_seconds_sum Cumulative request duration.",
            "# TYPE codeforge_request_duration_seconds_sum counter",
        ]
        for (method, route, status), total in sorted(sums.items()):
            lines.append(
                f"codeforge_request_duration_seconds_sum"
                f"{{{_labels(method, route, status)}}} {total:.6f}"
            )
        return "\n".join(lines) + "\n"


def _labels(method: str, route: str, status: str) -> str:
    """Prometheus label set with values escaped (backslash, quote, newline)."""

    def esc(v: str) -> str:
        return v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    return f'method="{esc(method)}",route="{esc(route)}",status="{esc(status)}"'


METRICS = Metrics()


def install_observability(app: FastAPI) -> None:
    """Wire structured request logging + the /metrics endpoint onto a FastAPI app."""
    configure_logging()
    log = get_logger("codeforge.http")

    @app.middleware("http")
    async def _observe(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        # The matched route template keeps metric cardinality bounded (not the raw path).
        route = getattr(request.scope.get("route"), "path", request.url.path)
        METRICS.observe(request.method, route, response.status_code, elapsed)
        log.info(
            "http_request",
            method=request.method,
            route=route,
            status=response.status_code,
            duration_ms=round(elapsed * 1000, 2),
        )
        return response

    @app.get("/metrics")
    def metrics() -> Response:
        """Prometheus metrics: request counts and latency by method, route, and status."""
        return Response(METRICS.render(), media_type=_PROM_CONTENT_TYPE)
