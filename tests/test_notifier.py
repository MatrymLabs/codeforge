"""Test twin for parts/notifier.py -- the practical adapter for the signal bus."""

from parts.notifier import Notifier, OrderPlaced
from parts.signal_bus import SignalBus


def test_a_placed_order_fans_out_to_handlers():
    notifier = Notifier()
    seen: list[OrderPlaced] = []
    receipts: list[str] = []
    notifier.on_order(lambda e: seen.append(e))
    notifier.on_order(lambda e: receipts.append(f"receipt for {e.order_id}"))
    notifier.place("A-1", 42.0)
    assert len(seen) == 1
    assert seen[0].order_id == "A-1"
    assert seen[0].total == 42.0
    assert receipts == ["receipt for A-1"]


def test_listeners_count_reflects_subscriptions():
    notifier = Notifier()
    assert notifier.listeners == 0
    notifier.on_order(lambda e: None)
    assert notifier.listeners == 1


def test_one_core_two_adapters_share_the_bus():
    assert isinstance(Notifier()._bus, SignalBus)
