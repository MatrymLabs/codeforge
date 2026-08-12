"""The wire protocol: versioned messages, refused when unknown, pinned by a consumer contract.

The sprint calls the schema "the one artifact both sides import" and asks for coordination by
discipline. This makes it mechanical: the client's declared reads are registered as a Contract, and
the SERVER's own test fails when a field it promised disappears. Without that, a protocol change
breaks the client at runtime, in a language the server's suite cannot see, across a process and a
machine boundary. That is the worst available place to discover a contract break.
"""

from __future__ import annotations

import pytest

from kernel.seam.wire import (
    WIRE_VERSION,
    WireRefused,
    decode,
    encode,
    hello,
)


def test_every_message_carries_its_version() -> None:
    assert encode(hello(session="s1"))["v"] == WIRE_VERSION


def test_a_message_from_an_unknown_version_is_REFUSED_not_parsed() -> None:
    """A protocol that guesses will one day act on a message three versions ahead of it."""
    with pytest.raises(WireRefused):
        decode({"v": WIRE_VERSION + 999, "type": "hello", "session": "s1"})


def test_a_message_with_NO_version_is_refused() -> None:
    """Absent is not 'probably current'."""
    with pytest.raises(WireRefused):
        decode({"type": "hello", "session": "s1"})


def test_an_unknown_message_type_is_refused() -> None:
    with pytest.raises(WireRefused):
        decode({"v": WIRE_VERSION, "type": "not_a_real_message"})


def test_encode_decode_round_trips() -> None:
    original = hello(session="s1")
    assert decode(encode(original)) == original


@pytest.mark.parametrize("hostile", [None, [], "hello", 0, {"v": "one", "type": "hello"}])
def test_a_hostile_payload_is_refused_rather_than_crashing(hostile) -> None:
    """The transport is a network. Everything arriving on it is hostile until parsed."""
    with pytest.raises(WireRefused):
        decode(hostile)


def test_the_client_contract_is_satisfied_by_the_server_message() -> None:
    """Contract Jig, consumed where it sits. The consumer declares what it reads; this test is the
    PROVIDER-side check that the server still sends it."""
    from kernel.seam.wire import CLIENT_CONTRACTS
    from kernel.shelf.contract import verify

    assert CLIENT_CONTRACTS, "a registry with no contracts pins nothing"
    for contract in CLIENT_CONTRACTS:
        sample = encode(hello(session="s1"))
        if contract.name == "hello":
            assert verify(contract, sample) == [], f"the server no longer satisfies {contract.name}"


def test_dropping_a_field_the_client_reads_fails_HERE_not_in_the_client() -> None:
    """The whole point of the packet. A server-side test must catch it."""
    from kernel.seam.wire import CLIENT_CONTRACTS
    from kernel.shelf.contract import verify

    hello_contract = next((c for c in CLIENT_CONTRACTS if c.name == "hello"), None)
    assert hello_contract is not None
    broken = {k: v for k, v in encode(hello(session="s1")).items() if k != "v"}
    assert verify(hello_contract, broken) != [], (
        "a dropped field passed the provider-side contract check, so it would have surfaced in "
        "the Godot client at runtime instead"
    )


def test_the_engine_2d_route_returns_a_versioned_hello() -> None:
    from fastapi.testclient import TestClient

    from adapters.web_gateway import app

    with TestClient(app).websocket_connect("/ws/engine-2d") as ws:
        ws.send_json(encode(hello(session="s1")))
        assert ws.receive_json() == encode(hello(session="s1"))
