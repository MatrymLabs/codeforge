"""CARD: chime -- the game adapter for the signal bus: a gate-chime answers a world signal.

When a traveller arrives, the world publishes a `TravellerArrived` signal and a subscribed chime
rings. The `chime` verb shows the bus at work: publishers raise signals, subscribers react, neither
knowing the other. The SAME bus core fans domain events to handlers in a practical app
(parts/notifier).
"""

from __future__ import annotations

from dataclasses import dataclass

from parts.session import Session
from parts.shelf.signal_bus import Signal, SignalBus


@dataclass(frozen=True)
class TravellerArrived(Signal):
    """A traveller reached the gate."""

    who: str


def chime(session: Session, arg: str = "") -> str:
    """The `chime` verb: ring the gate-chime for each traveller a world signal announces."""
    bus = SignalBus()
    rung: list[str] = []

    def ring(signal: Signal) -> None:
        assert isinstance(signal, TravellerArrived)  # the bus only routes this type here
        rung.append(f"The gate-chime rings for {signal.who}.")

    bus.subscribe(TravellerArrived, ring)
    for name in ("a merchant", "a pilgrim"):
        bus.publish(TravellerArrived(name))
    return "\n".join(rung)
