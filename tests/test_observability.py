"""Test twin for parts/shelf/observability.py -- structured logs + Prometheus /metrics.

Acceptance: the metrics registry renders valid Prometheus exposition; the middleware records
a request by method/route/status; /metrics serves it with the right content type; the logger
is available. Refusal/robustness: label values with hostile characters are escaped; the
registry is thread-safe-shaped and resettable.
"""

import pytest
from fastapi.testclient import TestClient

from parts.api import app
from parts.shelf.observability import METRICS, Metrics, configure_logging, get_logger


@pytest.fixture(autouse=True)
def _fresh_metrics():
    METRICS.reset()
    yield
    METRICS.reset()


# --- the registry -----------------------------------------------------------


def test_render_is_valid_prometheus_exposition():
    m = Metrics()
    m.observe("GET", "/health", 200, 0.01)
    m.observe("GET", "/health", 200, 0.02)
    text = m.render()
    assert "# TYPE codeforge_requests_total counter" in text
    assert 'codeforge_requests_total{method="GET",route="/health",status="200"} 2' in text
    assert (
        'codeforge_request_duration_seconds_sum{method="GET",route="/health",status="200"} 0.030000'
        in text
    )


def test_empty_registry_still_renders_headers():
    text = Metrics().render()
    assert "# HELP codeforge_requests_total" in text
    assert text.endswith("\n")


def test_label_values_are_escaped():
    m = Metrics()
    m.observe('GET"x', "/a\\b", 200, 0.0)
    text = m.render()
    assert 'method="GET\\"x"' in text
    assert 'route="/a\\\\b"' in text


def test_reset_clears_series():
    m = Metrics()
    m.observe("GET", "/x", 200, 0.1)
    m.reset()
    assert "codeforge_requests_total{" not in m.render()


# --- the logger -------------------------------------------------------------


def test_get_logger_is_usable():
    configure_logging()  # idempotent
    log = get_logger("test")
    log.info("hello", key="value")  # must not raise


# --- wired onto the app -----------------------------------------------------


@pytest.fixture()
def client():
    return TestClient(app)


def test_metrics_endpoint_serves_prometheus(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/plain; version=0.0.4; charset=utf-8"
    assert "codeforge_requests_total" in resp.text


def test_middleware_records_a_request_by_route_template(client):
    client.get("/health")
    text = client.get("/metrics").text
    assert 'route="/health",status="200"' in text
    # A parameterized route is recorded by its TEMPLATE, not the raw path (bounded cardinality).
    client.get("/ui/blueprint/npc_combat")
    text = client.get("/metrics").text
    assert 'route="/ui/blueprint/{blueprint_id}"' in text
    assert "npc_combat" not in text
