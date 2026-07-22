"""Test twin for parts/service_health.py -- the practical adapter + the one-core proof."""

from parts.service_health import ServiceHealth
from parts.shelf.health import HealthRegistry


def test_a_service_is_ready_only_when_every_dependency_is_healthy():
    svc = ServiceHealth()
    svc.add_bool("database", lambda: True)
    svc.add_bool("cache", lambda: True)
    assert svc.ready() is True
    svc.add_bool("queue", lambda: False)  # one dependency down
    assert svc.ready() is False


def test_a_raising_dependency_makes_the_service_not_ready():
    svc = ServiceHealth()

    def boom() -> str:
        raise ConnectionError("upstream unreachable")

    svc.add("upstream", boom)
    assert svc.ready() is False  # unknown is never ready
    assert "unknown" in svc.report()


def test_one_core_powers_both_the_game_vitals_and_the_practical_service_health():
    import parts.vitals as game

    svc = ServiceHealth()
    assert isinstance(svc._registry, HealthRegistry)  # the practical probe uses the core
    assert isinstance(game._build_registry(), HealthRegistry)  # the game panel, same core
