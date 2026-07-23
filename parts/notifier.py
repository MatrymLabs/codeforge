"""CARD: notifier -- the practical adapter for the signal bus: fan a domain event to handlers.

The reverse of parts/chime: the SAME `SignalBus` core lets a practical app raise a domain event
(an order placed) and have any number of independent handlers react (audit log, receipt, metrics)
without the publisher knowing who listens. Its cousins are webhook fan-out, audit trails, and any
decoupled event notification.
"""

from __future__ import annotations

from dataclasses import dataclass

from parts.shelf.signal_bus import Handler, Signal, SignalBus


@dataclass(frozen=True)
class OrderPlaced(Signal):
    """A domain event: an order was placed for `total`."""

    order_id: str
    total: float


class Notifier:
    """Raise `OrderPlaced` events and fan each to every subscribed handler."""

    def __init__(self) -> None:
        self._bus = SignalBus()

    def on_order(self, handler: Handler) -> None:
        """Subscribe a handler to be notified of every order placed."""
        self._bus.subscribe(OrderPlaced, handler)

    def place(self, order_id: str, total: float) -> None:
        """Record an order by publishing the event to all subscribers."""
        self._bus.publish(OrderPlaced(order_id, total))

    @property
    def listeners(self) -> int:
        """How many handlers are listening for orders."""
        return self._bus.subscribers(OrderPlaced)
