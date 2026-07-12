"""Test twin for parts/health.py -- the health-check registry and its honest aggregation."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from parts.health import (
    DEGRADED,
    HEALTHY,
    UNHEALTHY,
    UNKNOWN,
    HealthCheckError,
    HealthRegistry,
    healthy_if,
)


def test_all_healthy_checks_report_healthy_overall():
    reg = HealthRegistry()
    reg.register("a", lambda: HEALTHY)
    reg.register("b", lambda: HEALTHY)
    assert reg.overall() == HEALTHY


def test_the_worst_status_wins():
    reg = HealthRegistry()
    reg.register("a", lambda: HEALTHY)
    reg.register("b", lambda: DEGRADED)
    reg.register("c", lambda: UNHEALTHY)
    assert reg.overall() == UNHEALTHY


def test_a_raising_check_is_unknown_never_healthy():
    reg = HealthRegistry()
    reg.register("ok", lambda: HEALTHY)

    def boom() -> str:
        raise RuntimeError("probe failed")

    reg.register("broken", boom)
    results = {r.name: r.status for r in reg.run()}
    assert results["broken"] == UNKNOWN
    assert reg.overall() != HEALTHY  # the load-bearing rule: unknown is not healthy


def test_an_unrecognized_return_is_unknown():
    reg = HealthRegistry()
    reg.register("weird", lambda: "purple")
    assert reg.run()[0].status == UNKNOWN


def test_an_empty_registry_is_unknown_not_healthy():
    assert HealthRegistry().overall() == UNKNOWN


def test_a_duplicate_check_name_fails_loud():
    reg = HealthRegistry()
    reg.register("a", lambda: HEALTHY)
    with pytest.raises(HealthCheckError):
        reg.register("a", lambda: HEALTHY)


def test_healthy_if_maps_a_predicate():
    reg = HealthRegistry()
    reg.register("up", healthy_if(lambda: True))
    reg.register("down", healthy_if(lambda: False))
    statuses = {r.name: r.status for r in reg.run()}
    assert statuses == {"up": HEALTHY, "down": UNHEALTHY}


def test_the_report_names_the_overall_and_each_check():
    reg = HealthRegistry()
    reg.register("db", lambda: HEALTHY)
    report = reg.report()
    assert "HEALTH: healthy" in report
    assert "db" in report


@pytest.mark.property
@given(
    statuses=st.lists(
        st.sampled_from([HEALTHY, DEGRADED, UNKNOWN, UNHEALTHY]), min_size=1, max_size=20
    )
)
def test_overall_is_healthy_iff_every_check_is_healthy(statuses):
    reg = HealthRegistry()
    for i, s in enumerate(statuses):
        reg.register(f"c{i}", (lambda s=s: s))
    assert (reg.overall() == HEALTHY) == all(s == HEALTHY for s in statuses)
