"""CARD: broker -- the stdlib pub/sub broker the bus fans across processes (Phase 4).

The network backing behind the MessageBus seam. When one gateway is not enough, every process opens
a socket to ONE broker; each SUBSCRIBES to the topics of the players it hosts and PUBLISHES the
cohort and broadcast messages its players generate. The broker fans a publish to every process
subscribed to that topic, so a party split across two gateways is reached on both. No Redis, no
dependency: a line-delimited-JSON protocol over a stdlib ThreadingTCPServer -- our architecture is
the spine.

The wire is a seam. The protocol (encode_frame/decode_frame) is pure and fully tested; the Broker is
transport-agnostic (it fans to any client with a send(bytes)), so a fake client proves the routing
with no socket at all, and a socketpair proves the end-to-end path with no port and no network. The
daemon (serve) is a thin StreamRequestHandler over the same tested Broker.
"""

from __future__ import annotations

import json
import socketserver
import threading
from contextlib import suppress
from typing import Any, Protocol


class BrokerProtocolError(ValueError):
    """A frame that is not a valid protocol message (malformed JSON, missing op/topic)."""


class Client(Protocol):
    """Anything the broker can push bytes to: a real socket wrapper, or a fake in a test."""

    def send(self, data: bytes) -> None: ...


def encode_frame(op: str, topic: str, payload: Any) -> bytes:
    """One protocol message as a line of JSON. op is sub/unsub/pub; payload is null except a pub."""
    return (json.dumps({"op": op, "topic": topic, "payload": payload}) + "\n").encode("utf-8")


def decode_frame(line: bytes) -> dict[str, Any]:
    """Parse one line into a frame, or fail loud. A blank line (keep-alive) is not a frame."""
    try:
        frame = json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BrokerProtocolError(f"not JSON: {line!r}") from exc
    if not isinstance(frame, dict) or "op" not in frame or "topic" not in frame:
        raise BrokerProtocolError(f"missing op/topic: {frame!r}")
    return frame


class Broker:
    """Routes subscriptions and publishes across connected clients. Transport-agnostic: a client is
    anything with send(bytes), so the routing is provable without a socket."""

    def __init__(self) -> None:
        self._subs: dict[str, set[Client]] = {}
        self._lock = threading.Lock()

    def on_frame(self, client: Client, frame: dict[str, Any]) -> None:
        """Handle one decoded frame from a client: record a subscription, drop one, or fan a pub."""
        op = frame.get("op")
        topic = frame.get("topic")
        if not isinstance(topic, str):
            return
        if op == "sub":
            with self._lock:
                self._subs.setdefault(topic, set()).add(client)
        elif op == "unsub":
            with self._lock:
                self._subs.get(topic, set()).discard(client)
        elif op == "pub":
            self._fan(topic, frame.get("payload"))

    def _fan(self, topic: str, payload: Any) -> None:
        """Push a publish to every client subscribed to the topic, including the sender (its own
        delivery subscriber turns the frame into local sink writes). A dead client never breaks it.
        """
        data = encode_frame("pub", topic, payload)
        with self._lock:
            targets = list(self._subs.get(topic, ()))
        for client in targets:
            with suppress(Exception):  # nosec B110 -- a dead client never breaks the fan-out
                client.send(data)

    def drop(self, client: Client) -> None:
        """Remove a client from every topic (it disconnected)."""
        with self._lock:
            for subs in self._subs.values():
                subs.discard(client)

    def topics(self) -> dict[str, int]:
        """Subscriber count per topic -- a broker health read for ops."""
        with self._lock:
            return {topic: len(subs) for topic, subs in self._subs.items() if subs}


class _SocketClient:
    """A broker-side view of one connected process: send(bytes) writes to its socket, serialised so
    two fan-outs never interleave on the wire."""

    def __init__(self, sock: Any) -> None:
        self._sock = sock
        self._lock = threading.Lock()

    def send(self, data: bytes) -> None:
        with self._lock:
            self._sock.sendall(data)


class _BrokerServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr: tuple[str, int], broker: Broker) -> None:
        self.broker = broker
        super().__init__(addr, _BrokerHandler)


class _BrokerHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        broker: Broker = self.server.broker  # type: ignore[attr-defined]
        client = _SocketClient(self.connection)
        try:
            for line in self.rfile:  # line-delimited frames
                if not line.strip():
                    continue  # keep-alive / blank
                try:
                    frame = decode_frame(line)
                except BrokerProtocolError:
                    continue  # a garbled frame never drops the connection
                broker.on_frame(client, frame)
        except OSError:
            pass  # the process dropped; the finally cleans up
        finally:
            broker.drop(client)


def serve(host: str = "127.0.0.1", port: int = 4900) -> _BrokerServer:
    """Start the broker daemon on host:port and return the running server (call shutdown() to stop).

    A thin shell over the tested Broker: each connection is one process; its frames route through
    on_frame; a disconnect drops it from every topic. Port 0 binds an ephemeral port (tests)."""
    server = _BrokerServer((host, port), Broker())
    thread = threading.Thread(target=server.serve_forever, name="broker", daemon=True)
    thread.start()
    return server
