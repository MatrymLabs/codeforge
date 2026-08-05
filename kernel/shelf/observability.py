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
from typing import TYPE_CHECKING, Any

import structlog
from fastapi.responses import Response

from kernel.shelf import trace as trace_ctx

if TYPE_CHECKING:
    from fastapi import FastAPI
    from starlette.types import Receive, Scope, Send

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


class ObservabilityMiddleware:
    """Pure ASGI request observer.

    This deliberately avoids Starlette's ``BaseHTTPMiddleware``. Besides reducing one task-group
    boundary, the pure ASGI form remains usable by synchronous and asynchronous test transports
    in constrained environments where cross-task response streaming can otherwise wait forever.
    """

    def __init__(self, app: Any) -> None:
        self.app = app
        self.log = get_logger("codeforge.http")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        inbound = next((v for k, v in scope.get("headers", []) if k == b"traceparent"), None)
        inbound_text = inbound.decode("latin-1") if inbound else None
        try:
            span = (
                trace_ctx.continue_trace(inbound_text) if inbound_text else trace_ctx.start_trace()
            )
        except trace_ctx.TraceError:
            span = trace_ctx.start_trace()
        start = time.perf_counter()
        status = 500

        async def observed_send(message: dict[str, Any]) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
                headers = list(message.get("headers", []))
                headers.append((b"traceparent", span.traceparent().encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        with trace_ctx.use_trace(span):
            await self.app(scope, receive, observed_send)
        elapsed = time.perf_counter() - start
        raw_route = getattr(scope.get("route"), "path", scope.get("path", ""))
        route = raw_route if isinstance(raw_route, str) else str(raw_route)
        METRICS.observe(scope.get("method", ""), route, status, elapsed)
        self.log.info(
            "http_request",
            method=scope.get("method", ""),
            route=route,
            status=status,
            duration_ms=round(elapsed * 1000, 2),
            **span.log_fields(),
        )


def install_observability(app: FastAPI) -> None:
    """Wire structured request logging + the /metrics endpoint onto a FastAPI app."""
    configure_logging()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/metrics")
    async def metrics() -> Response:
        """Prometheus metrics: request counts and latency by method, route, and status."""
        return Response(METRICS.render(), media_type=_PROM_CONTENT_TYPE)
