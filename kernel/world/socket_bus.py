"""CARD: socket_bus -- the MessageBus adapter that rides a socket to the broker (Phase 4).

The network implementation of the bus seam. A process injects one of these (bus.set_bus) and every
caller keeps going through get_bus() unchanged: publish writes a frame to the broker, subscribe
tells the broker this process wants a topic and registers a handler, and a background reader turns
the broker's fan-out back into local handler calls. So announce_to/push_gmcp/presence, already
publishing onto the bus, now reach every process on the broker without a single caller change.

The one behaviour that differs from the in-process bus: delivery is a round trip (publish -> broker
-> reader -> handler) instead of synchronous, so a message to a player on THIS process comes back
through the broker too. That is the price of one shared roster across processes; tests poll with a
deadline rather than assert an instant, the house rule for anything distributed.
"""

from __future__ import annotations

import socket
import threading
from contextlib import suppress
from typing import Any

from kernel.world.broker import BrokerProtocolError, decode_frame, encode_frame

Handler = (
    Any  # Callable[[dict[str, Any]], None]; kept loose so the reader can pass raw JSON payloads
)


class SocketBus:
    """A MessageBus backed by a socket to the broker. Satisfies the same Protocol as InProcessBus,
    so set_bus swaps it in and callers never change."""

    def __init__(self, conn: socket.socket) -> None:
        self._conn = conn
        self._rfile = conn.makefile("rb")
        self._send_lock = threading.Lock()
        self._subs_lock = threading.Lock()
        self._subs: dict[str, list[Handler]] = {}
        self._alive = True
        self._reader = threading.Thread(
            target=self._read_loop, name="socketbus-reader", daemon=True
        )
        self._reader.start()

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        self._write(encode_frame("pub", topic, payload))

    def subscribe(self, topic: str, handler: Handler) -> None:
        with self._subs_lock:
            first = topic not in self._subs
            self._subs.setdefault(topic, []).append(handler)
        if first:  # tell the broker this process wants the topic (once per topic)
            self._write(encode_frame("sub", topic, None))

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        emptied = False
        with self._subs_lock:
            handlers = self._subs.get(topic)
            if handlers and handler in handlers:
                handlers.remove(handler)
            if topic in self._subs and not self._subs[topic]:
                del self._subs[topic]
                emptied = True
        if emptied:  # no local interest left -> the broker can stop sending this topic
            self._write(encode_frame("unsub", topic, None))

    def _write(self, data: bytes) -> None:
        if not self._alive:
            return
        # a dropped broker connection never crashes a publish
        with self._send_lock, suppress(OSError):
            self._conn.sendall(data)

    def _read_loop(self) -> None:
        """Turn the broker's fan-out back into local handler calls until the connection closes."""
        try:
            for line in self._rfile:
                if not self._alive:
                    break
                if not line.strip():
                    continue
                try:
                    frame = decode_frame(line)
                except BrokerProtocolError:
                    continue
                if frame.get("op") != "pub":
                    continue
                topic = frame.get("topic")
                if not isinstance(topic, str):
                    continue
                payload = frame.get("payload")
                with self._subs_lock:
                    handlers = list(self._subs.get(topic, ()))
                for handler in handlers:
                    # One bad handler must not break delivery.
                    with suppress(Exception):  # nosec B110
                        handler(payload)
        except OSError:
            pass  # the broker went away; close() handles the rest

    def close(self) -> None:
        """Stop the reader and drop the broker connection."""
        self._alive = False
        with suppress(OSError):
            self._conn.shutdown(socket.SHUT_RDWR)
        with suppress(OSError):
            self._conn.close()


def connect(host: str = "127.0.0.1", port: int = 4900, timeout: float = 5.0) -> SocketBus:
    """Open a SocketBus to the broker at host:port. The caller injects it with bus.set_bus."""
    conn = socket.create_connection((host, port), timeout=timeout)
    conn.settimeout(None)  # blocking reads for the reader thread
    return SocketBus(conn)


def maybe_wire_broker(env: dict[str, str] | None = None) -> SocketBus | None:
    """If CODEFORGE_BUS_BROKER=host:port is set, connect a SocketBus and inject it as the bus, so
    this process joins a multi-process deployment. Absent, the in-process bus stays and this is a
    no-op. Called once at gateway boot; returns the SocketBus it wired, or None. A malformed spec
    fails loud (better a clear boot error than a silent single-process fallback)."""
    import os  # noqa: PLC0415

    from kernel.world import bus  # noqa: PLC0415

    spec = (env if env is not None else os.environ).get("CODEFORGE_BUS_BROKER", "").strip()
    if not spec:
        return None
    host, _, port_text = spec.partition(":")
    sbus = connect(host or "127.0.0.1", int(port_text or "4900"))
    bus.set_bus(sbus)  # fires the rewire hooks: delivery + presence re-attach over the socket
    return sbus
