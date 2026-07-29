"""CARD: bus -- a publish/subscribe seam: the network backing the event bus grows into (Phase 4).

The one architectural step to multi-process. Today the event bus (parts.world.events) delivers to
THIS process's connections; a second process (a second gateway, the admin surface) cannot see live
players or push to a session it does not own. This is the seam that fixes it: a MessageBus a caller
publishes topics onto and subscribes to, with a single-process default that behaves exactly like a
direct call, and a network adapter (Redis/socket pub-sub) that implements the SAME Protocol to fan
out across processes. The adapter is injected via set_bus, so no caller changes when the world grows
from one process to many.

The boundary is a seam, mocked in tests: the default InProcessBus needs no network, and a fake
implementing MessageBus proves the contract, so CI never touches a broker. A subscriber that raises
is isolated -- one bad handler never breaks a publish, exactly like a dead echo sink never breaks a
broadcast.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from typing import Any, Protocol

Handler = Callable[[dict[str, Any]], None]


class MessageBus(Protocol):
    """The pub/sub contract every backing satisfies (in-process now, a broker later)."""

    def publish(self, topic: str, payload: dict[str, Any]) -> None: ...

    def subscribe(self, topic: str, handler: Handler) -> None: ...

    def unsubscribe(self, topic: str, handler: Handler) -> None: ...


class InProcessBus:
    """The default single-process bus: publish delivers to this process's subscribers synchronously,
    so behaviour is identical to a direct call. It is the network adapter's stand-in until a real
    broker is injected; a broker implements the same Protocol and set_bus swaps it in unchanged."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = {}

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        for handler in list(self._subs.get(topic, ())):  # snapshot: a handler may unsubscribe
            with suppress(Exception):  # nosec B110 -- one bad subscriber never breaks a publish
                handler(payload)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subs.setdefault(topic, []).append(handler)

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        subs = self._subs.get(topic)
        if subs and handler in subs:
            subs.remove(handler)


_BUS: MessageBus = InProcessBus()


def get_bus() -> MessageBus:
    """The message bus in force. Single-process by default; a broker adapter once one is set."""
    return _BUS


def set_bus(bus: MessageBus) -> None:
    """Swap the backing bus (a network adapter in production, a fake in tests). Callers are
    unchanged; they always go through get_bus()."""
    global _BUS
    _BUS = bus


def reset_bus() -> None:
    """Restore the default single-process bus (for tests, so one test's bus never leaks onward)."""
    global _BUS
    _BUS = InProcessBus()
