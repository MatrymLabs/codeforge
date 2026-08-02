"""CARD: signal_bus -- a typed signal bus: subscribe handlers by signal type, publish to them.

Decouples the thing that raises an event from the things that react to it: publishers know only the
bus, subscribers know only the signal type they care about. Handlers are keyed by exact signal type,
so a subscriber to one signal never sees another. Framework-free and synchronous.

Harvested from codeforge-client's event bus (proven there driving its state reducer), reimplemented
here in the forge voice. One core, two adapters: an in-world `chime` that answers a world signal
(parts/chime) and a domain-event `Notifier` for a practical app (parts/notifier). Distinct from
parts/events (in-world echo broadcasts): this is a general typed pub/sub.

Provenance: original implementation of a standard pub/sub pattern. No code copied.
"""

from __future__ import annotations

from collections.abc import Callable


class Signal:
    """Marker base for a typed signal. Concrete signals are frozen dataclasses subclassing this."""


Handler = Callable[[Signal], None]


class SignalBus:
    """Typed pub/sub: subscribe handlers by signal type, publish a signal to its subscribers."""

    def __init__(self) -> None:
        self._subscribers: dict[type[Signal], list[Handler]] = {}

    def subscribe(self, signal_type: type[Signal], handler: Handler) -> None:
        """Register `handler` to receive signals of exactly `signal_type`."""
        self._subscribers.setdefault(signal_type, []).append(handler)

    def publish(self, signal: Signal) -> None:
        """Deliver `signal` to every handler subscribed to its exact type, in subscription order."""
        for handler in self._subscribers.get(type(signal), ()):
            handler(signal)

    def subscribers(self, signal_type: type[Signal]) -> int:
        """How many handlers are subscribed to `signal_type` (for diagnostics and tests)."""
        return len(self._subscribers.get(signal_type, ()))
