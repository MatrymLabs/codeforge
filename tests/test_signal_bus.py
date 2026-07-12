"""Test twin for parts/signal_bus.py -- a typed signal bus."""

from dataclasses import dataclass

from parts.signal_bus import Signal, SignalBus


@dataclass(frozen=True)
class Ping(Signal):
    value: int


@dataclass(frozen=True)
class Pong(Signal):
    pass


def test_delivers_only_to_matching_type():
    bus = SignalBus()
    pings: list[Ping] = []
    pongs: list[Pong] = []
    bus.subscribe(Ping, lambda s: pings.append(s))
    bus.subscribe(Pong, lambda s: pongs.append(s))
    bus.publish(Ping(7))
    bus.publish(Pong())
    assert len(pings) == 1
    assert len(pongs) == 1
    assert pings[0].value == 7


def test_publish_with_no_subscribers_is_a_noop():
    SignalBus().publish(Ping(1))  # must not raise


def test_multiple_handlers_fire_in_order():
    bus = SignalBus()
    order: list[str] = []
    bus.subscribe(Ping, lambda s: order.append("a"))
    bus.subscribe(Ping, lambda s: order.append("b"))
    bus.publish(Ping(1))
    assert order == ["a", "b"]


def test_subscribers_count():
    bus = SignalBus()
    assert bus.subscribers(Ping) == 0
    bus.subscribe(Ping, lambda s: None)
    assert bus.subscribers(Ping) == 1
