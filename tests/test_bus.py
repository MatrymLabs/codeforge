"""Test twin for kernel/world/bus.py -- the pub/sub seam the event bus grows into (Phase 4).

Acceptance: a subscriber receives what is published on its topic; unsubscribe stops delivery;
set_bus swaps the backing (the network-adapter injection point) and get_bus reports it. Refusal /
robustness: a subscriber that raises is isolated so one bad handler never breaks a publish; a topic
with no subscribers is a silent no-op; a fake bus satisfies the Protocol without any network.
"""

from __future__ import annotations

from typing import Any

import pytest

from kernel.world import bus


@pytest.fixture(autouse=True)
def _fresh_bus() -> Any:
    bus.reset_bus()  # each test starts on a clean in-process bus
    yield
    bus.reset_bus()


def test_a_subscriber_receives_a_published_payload() -> None:
    seen: list[dict[str, Any]] = []
    bus.get_bus().subscribe("chan", seen.append)
    bus.get_bus().publish("chan", {"n": 1})
    assert seen == [{"n": 1}]


def test_a_publish_reaches_every_subscriber_on_the_topic() -> None:
    a: list[dict[str, Any]] = []
    b: list[dict[str, Any]] = []
    bus.get_bus().subscribe("chan", a.append)
    bus.get_bus().subscribe("chan", b.append)
    bus.get_bus().publish("chan", {"hi": True})
    assert a == b == [{"hi": True}]


def test_delivery_is_scoped_to_the_topic() -> None:
    seen: list[dict[str, Any]] = []
    bus.get_bus().subscribe("here", seen.append)
    bus.get_bus().publish("elsewhere", {"x": 1})  # different topic
    assert seen == []


def test_unsubscribe_stops_delivery() -> None:
    seen: list[dict[str, Any]] = []
    bus.get_bus().subscribe("chan", seen.append)
    bus.get_bus().unsubscribe("chan", seen.append)
    bus.get_bus().publish("chan", {"n": 1})
    assert seen == []


def test_publish_to_an_empty_topic_is_a_silent_noop() -> None:
    bus.get_bus().publish("nobody-here", {"n": 1})  # must not raise


def test_a_raising_subscriber_never_breaks_a_publish() -> None:
    delivered: list[str] = []

    def explode(_: dict[str, Any]) -> None:
        raise RuntimeError("bad handler")  # noqa: TRY003

    bus.get_bus().subscribe("chan", explode)
    bus.get_bus().subscribe("chan", lambda _p: delivered.append("ok"))
    bus.get_bus().publish("chan", {})  # the good handler still runs
    assert delivered == ["ok"]


def test_unsubscribe_of_an_unknown_handler_is_harmless() -> None:
    bus.get_bus().unsubscribe("chan", lambda _p: None)  # never subscribed -> no error


def test_set_bus_swaps_the_backing_and_get_bus_reports_it() -> None:
    # A fake standing in for a network adapter: it satisfies the Protocol with no network,
    # proving the seam is mockable exactly as the fleet rule requires.
    class FakeBus:
        def __init__(self) -> None:
            self.published: list[tuple[str, dict[str, Any]]] = []

        def publish(self, topic: str, payload: dict[str, Any]) -> None:
            self.published.append((topic, payload))

        def subscribe(self, topic: str, handler: Any) -> None:
            pass

        def unsubscribe(self, topic: str, handler: Any) -> None:
            pass

    fake = FakeBus()
    bus.set_bus(fake)
    assert bus.get_bus() is fake
    bus.get_bus().publish("chan", {"n": 9})
    assert fake.published == [("chan", {"n": 9})]


def test_reset_bus_restores_a_clean_default() -> None:
    seen: list[dict[str, Any]] = []
    bus.get_bus().subscribe("chan", seen.append)
    bus.reset_bus()  # a fresh InProcessBus with no subscribers
    bus.get_bus().publish("chan", {"n": 1})
    assert seen == []  # the old subscription did not carry over
