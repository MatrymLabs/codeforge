"""Test twin for kernel/world/socket_bus.py -- the network MessageBus adapter (Phase 4).

The end-to-end proof that the seam reaches across processes. Two SocketBus clients on one Broker
stand in for two gateways: one publishes a cohort message, the other's handler receives it. A
publisher that also subscribes gets its own publish back (the round trip that replaces synchronous
local delivery). unsubscribe tells the broker to stop; close is clean and idempotent; set_bus wires
the adapter so the real bus module drives it. Exercised over socket.socketpair (no port, no network)
and once over the serve() daemon on a loopback ephemeral port. Distributed, so every assertion polls
with a deadline -- never asserts an instant.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable
from typing import Any

from kernel.world.broker import Broker, BrokerProtocolError, _SocketClient, decode_frame
from kernel.world.socket_bus import SocketBus


def _pump(broker: Broker, broker_sock: socket.socket) -> None:
    """Feed one broker-side connection's frames into the broker until it closes (the daemon's job,
    done inline here so socketpair needs no port)."""
    client = _SocketClient(broker_sock)
    rfile = broker_sock.makefile("rb")

    def loop() -> None:
        try:
            for line in rfile:
                if not line.strip():
                    continue
                try:
                    broker.on_frame(client, decode_frame(line))
                except BrokerProtocolError:
                    continue
        except OSError:
            pass
        finally:
            broker.drop(client)

    threading.Thread(target=loop, name="test-broker-pump", daemon=True).start()


def _wire(broker: Broker) -> SocketBus:
    """A SocketBus connected to the broker over an in-process socketpair (no listening port)."""
    client_sock, broker_sock = socket.socketpair()
    _pump(broker, broker_sock)
    return SocketBus(client_sock)


def _wait(pred: Callable[[], bool], timeout: float = 3.0) -> bool:
    """Poll a predicate to a deadline -- the house rule for distributed assertions."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.01)
    return pred()


def test_two_processes_exchange_a_cohort_message():
    broker = Broker()
    bus1, bus2 = _wire(broker), _wire(broker)
    got: list[Any] = []
    try:
        bus2.subscribe("delivery:echo", got.append)
        assert _wait(lambda: broker.topics().get("delivery:echo") == 1)
        bus1.publish("delivery:echo", {"text": "rally to me"})
        assert _wait(lambda: got == [{"text": "rally to me"}])
    finally:
        bus1.close()
        bus2.close()


def test_a_publisher_that_subscribes_receives_its_own_publish():
    # The round trip that replaces synchronous local delivery: this process's own delivery handler
    # only lands the message because the broker fans the publish back to the sender.
    broker = Broker()
    bus1 = _wire(broker)
    got: list[Any] = []
    try:
        bus1.subscribe("t", got.append)
        assert _wait(lambda: broker.topics().get("t") == 1)
        bus1.publish("t", {"n": 1})
        assert _wait(lambda: got == [{"n": 1}])
    finally:
        bus1.close()


def test_unsubscribe_tells_the_broker_to_stop():
    broker = Broker()
    bus1 = _wire(broker)
    got: list[Any] = []
    try:
        bus1.subscribe("t", got.append)
        assert _wait(lambda: broker.topics().get("t") == 1)
        bus1.unsubscribe("t", got.append)
        assert _wait(lambda: "t" not in broker.topics())
    finally:
        bus1.close()


def test_close_is_idempotent():
    broker = Broker()
    bus1 = _wire(broker)
    bus1.close()
    bus1.close()  # a second close must not raise


def test_set_bus_injects_the_adapter_and_the_real_bus_drives_it():
    from kernel.world import bus as busmod  # noqa: PLC0415

    broker = Broker()
    sbus = _wire(broker)
    got: list[Any] = []
    try:
        busmod.set_bus(sbus)  # fires rewire hooks; core subscribers re-attach over the socket
        busmod.get_bus().subscribe("t", got.append)
        assert _wait(lambda: broker.topics().get("t") == 1)
        busmod.get_bus().publish("t", {"n": 7})
        assert _wait(lambda: got == [{"n": 7}])
    finally:
        busmod.reset_bus()
        sbus.close()


def test_maybe_wire_broker_is_a_noop_when_unset():
    from kernel.world import bus as busmod  # noqa: PLC0415
    from kernel.world.socket_bus import maybe_wire_broker  # noqa: PLC0415

    before = busmod.get_bus()
    assert maybe_wire_broker({}) is None  # env not set
    assert maybe_wire_broker({"CODEFORGE_BUS_BROKER": "  "}) is None  # blank
    assert busmod.get_bus() is before  # the in-process bus is untouched


def test_maybe_wire_broker_connects_and_injects_when_set():
    from kernel.world import bus as busmod  # noqa: PLC0415
    from kernel.world.broker import serve  # noqa: PLC0415
    from kernel.world.socket_bus import maybe_wire_broker  # noqa: PLC0415

    server = serve("127.0.0.1", 0)
    host, port = server.server_address
    wired = None
    try:
        wired = maybe_wire_broker({"CODEFORGE_BUS_BROKER": f"{host}:{port}"})
        assert wired is not None
        assert busmod.get_bus() is wired  # the deployment's bus is now the socket adapter
    finally:
        busmod.reset_bus()
        if wired is not None:
            wired.close()
        server.shutdown()
        server.server_close()


def test_serve_and_connect_deliver_across_the_daemon():
    # The one loopback test: a real broker daemon on an ephemeral port, two clients over connect().
    from kernel.world.broker import serve  # noqa: PLC0415
    from kernel.world.socket_bus import connect  # noqa: PLC0415

    server = serve("127.0.0.1", 0)
    host, port = server.server_address
    a: SocketBus | None = None
    b: SocketBus | None = None
    got: list[Any] = []
    try:
        a = connect(host, port)
        b = connect(host, port)
        b.subscribe("delivery:echo", got.append)
        assert _wait(lambda: server.broker.topics().get("delivery:echo") == 1)
        a.publish("delivery:echo", {"text": "over the wire"})
        assert _wait(lambda: got == [{"text": "over the wire"}])
    finally:
        if a is not None:
            a.close()
        if b is not None:
            b.close()
        server.shutdown()
        server.server_close()
