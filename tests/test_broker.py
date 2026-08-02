"""Test twin for kernel/world/broker.py -- the stdlib pub/sub broker behind the bus seam (Phase 4).

Acceptance: encode/decode round-trips a frame; the Broker fans a publish to every subscriber of a
topic (including the sender, whose own delivery handler needs it); unsub and drop stop delivery;
topics() reports the live counts. Refusal: a malformed line fails loud in decode; a frame missing
op/topic is ignored by the Broker, not crashed on; a client whose send() raises never breaks the
fan-out to the others. Transport-agnostic: a fake client with a list proves the routing, no socket.
"""

from __future__ import annotations

import pytest

from kernel.world.broker import (
    Broker,
    BrokerProtocolError,
    decode_frame,
    encode_frame,
)


class FakeClient:
    """A broker client that records the frames pushed to it, so routing is provable with no wire."""

    def __init__(self, explode: bool = False) -> None:
        self.received: list[bytes] = []
        self._explode = explode

    def send(self, data: bytes) -> None:
        if self._explode:
            raise OSError("dead socket")
        self.received.append(data)


def _payloads(client: FakeClient) -> list[object]:
    return [decode_frame(line)["payload"] for line in client.received]


def test_encode_decode_round_trips_a_frame():
    line = encode_frame("pub", "delivery:echo", {"text": "hi"})
    assert line.endswith(b"\n")
    frame = decode_frame(line)
    assert frame == {"op": "pub", "topic": "delivery:echo", "payload": {"text": "hi"}}


def test_decode_rejects_non_json():
    with pytest.raises(BrokerProtocolError, match="not JSON"):
        decode_frame(b"{not json\n")


def test_decode_rejects_a_frame_missing_op_or_topic():
    with pytest.raises(BrokerProtocolError, match="missing op/topic"):
        decode_frame(b'{"op": "pub"}\n')


def test_publish_fans_to_every_subscriber_of_the_topic():
    broker = Broker()
    a, b = FakeClient(), FakeClient()
    broker.on_frame(a, {"op": "sub", "topic": "t", "payload": None})
    broker.on_frame(b, {"op": "sub", "topic": "t", "payload": None})
    broker.on_frame(a, {"op": "pub", "topic": "t", "payload": {"n": 1}})
    # Both subscribers receive it -- INCLUDING the sender a, whose delivery handler turns it into
    # local sink writes (the in-process path did this synchronously; here it round-trips).
    assert _payloads(a) == [{"n": 1}]
    assert _payloads(b) == [{"n": 1}]


def test_publish_is_scoped_to_the_topic():
    broker = Broker()
    a = FakeClient()
    broker.on_frame(a, {"op": "sub", "topic": "here", "payload": None})
    broker.on_frame(a, {"op": "pub", "topic": "elsewhere", "payload": {"n": 1}})
    assert a.received == []


def test_unsub_stops_delivery():
    broker = Broker()
    a = FakeClient()
    broker.on_frame(a, {"op": "sub", "topic": "t", "payload": None})
    broker.on_frame(a, {"op": "unsub", "topic": "t", "payload": None})
    broker.on_frame(a, {"op": "pub", "topic": "t", "payload": {"n": 1}})
    assert a.received == []


def test_drop_removes_a_client_from_every_topic():
    broker = Broker()
    a, b = FakeClient(), FakeClient()
    broker.on_frame(a, {"op": "sub", "topic": "t", "payload": None})
    broker.on_frame(b, {"op": "sub", "topic": "t", "payload": None})
    broker.drop(a)  # a disconnected
    broker.on_frame(b, {"op": "pub", "topic": "t", "payload": {"n": 1}})
    assert a.received == []  # dropped
    assert _payloads(b) == [{"n": 1}]  # b still served


def test_a_dead_client_never_breaks_the_fan_out():
    broker = Broker()
    dead, live = FakeClient(explode=True), FakeClient()
    broker.on_frame(dead, {"op": "sub", "topic": "t", "payload": None})
    broker.on_frame(live, {"op": "sub", "topic": "t", "payload": None})
    broker.on_frame(live, {"op": "pub", "topic": "t", "payload": {"n": 1}})  # must not raise
    assert _payloads(live) == [{"n": 1}]  # the live client still received


def test_a_frame_missing_op_or_topic_is_ignored_not_crashed():
    broker = Broker()
    a = FakeClient()
    broker.on_frame(a, {"op": "sub", "payload": None})  # no topic -> ignored
    broker.on_frame(a, {"topic": "t", "payload": None})  # no op -> ignored
    assert broker.topics() == {}


def test_topics_reports_live_subscriber_counts():
    broker = Broker()
    a, b = FakeClient(), FakeClient()
    broker.on_frame(a, {"op": "sub", "topic": "t", "payload": None})
    broker.on_frame(b, {"op": "sub", "topic": "t", "payload": None})
    broker.on_frame(a, {"op": "sub", "topic": "u", "payload": None})
    assert broker.topics() == {"t": 2, "u": 1}
