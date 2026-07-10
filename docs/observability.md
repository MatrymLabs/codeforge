# Observability: structured logs + Prometheus metrics

`parts/observability.py` gives the HTTP surface two senior-grade signals, wired on with one
middleware.

## Structured logs (structlog)

Every request becomes one **JSON event**, not a prose line:

```json
{"method": "GET", "route": "/api/status", "status": 200, "duration_ms": 37.58,
 "event": "http_request", "level": "info", "timestamp": "2026-07-10T23:21:25Z"}
```

Structured logs are queryable (by route, status, latency), which prose logs are not.
`get_logger(name)` returns a configured structlog logger for any module that wants one.

## Metrics (`GET /metrics`)

Prometheus text exposition, ready for a scraper:

```
# TYPE codeforge_requests_total counter
codeforge_requests_total{method="GET",route="/health",status="200"} 2
# TYPE codeforge_request_duration_seconds_sum counter
codeforge_request_duration_seconds_sum{method="GET",route="/health",status="200"} 0.005876
```

- Content type is the exact `text/plain; version=0.0.4; charset=utf-8` Prometheus expects.
- Series are keyed by the matched **route template** (e.g. `/ui/blueprint/{blueprint_id}`),
  never the raw path, so a parameterized route does not explode metric cardinality.
- The registry is a small, thread-safe, **stdlib** counter table; the exposition format is
  rendered directly (no scraping library). It records a request count and a latency sum per
  series - enough for rate and average-latency queries. It is not a full histogram (no
  buckets), and says so honestly.

## How it is wired

`install_observability(app)` (called in `parts/api.py`) adds an HTTP middleware that times
each request, records the metric, and emits the structured log, plus the `/metrics` route. It
touches only the HTTP surface; the MUD engine and the tick never log through it, so the
`structlog` dependency stays bounded to `parts/observability.py`.
