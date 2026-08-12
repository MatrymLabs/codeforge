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


# ---------------------------------------------------------------------------------------------
# The packet's own acceptance criterion, pinned properly.
#
# `definition_of_done` asks that "a SERVER-side test fails when a declared field is dropped or
# retyped". Re-verification found it did not: removing `session` from `_FIELDS["hello"]` left
# `decode({"v": 1, "type": "hello"})` ACCEPTING a frame with no session, and all thirteen tests
# still passed. Removing `Field("session")` from CLIENT_CONTRACTS also passed.
#
# The reason is worth keeping, because it is a trap the next protocol test will walk into too:
# the provider-side check built its sample by CALLING `hello(session="s1")`, so the sample carried
# `session` whether or not the schema required it, and the "dropped field" test deleted a key from
# an already-encoded payload rather than from the schema. Both pinned the INSTRUMENT (`verify`
# reports a missing key) instead of the INVARIANT (the schema cannot silently lose a field).
#
# WIRE_SURFACE below is deliberately a LITERAL, not derived from `_FIELDS`. A test that reads its
# cases out of the thing under test cannot notice a deletion from it: removing the field would
# remove the case that checks it, and the suite would stay green while the wire changed shape.
# ---------------------------------------------------------------------------------------------

WIRE_SURFACE: dict[str, dict[str, type]] = {
    "hello": {"session": str},
    "move_intent": {"direction": str},
    "entity_state": {"entity_id": str, "x": int, "y": int},
    "tick": {"tick": int},
    "refused": {"verdict": str, "reason": str},
}

_SAMPLE: dict[type, object] = {str: "s1", int: 7}


def test_the_declared_wire_surface_has_not_changed_shape() -> None:
    """Drop or retype a field in the schema and this fails, which is the criterion WO-S2 states."""
    from kernel.seam.wire import _FIELDS

    assert _FIELDS == WIRE_SURFACE, (
        "the wire schema no longer matches the surface this test declares. If the change is "
        "deliberate, update WIRE_SURFACE in the same commit and say why in the message; the point "
        "is that it cannot happen silently."
    )


@pytest.mark.parametrize(
    ("message_type", "field_name"),
    [(t, f) for t, fields in WIRE_SURFACE.items() for f in fields],
)
def test_every_declared_field_is_actually_required_by_decode(
    message_type: str, field_name: str
) -> None:
    """Behavioural half. The schema could match and still not be enforced by the validator."""
    frame = {"v": WIRE_VERSION, "type": message_type}
    frame.update({name: _SAMPLE[kind] for name, kind in WIRE_SURFACE[message_type].items()})
    del frame[field_name]

    with pytest.raises(WireRefused, match=f"{message_type}.{field_name} is required"):
        decode(frame)


@pytest.mark.parametrize(
    ("message_type", "field_name"),
    [(t, f) for t, fields in WIRE_SURFACE.items() for f in fields],
)
def test_every_declared_field_is_type_checked_by_decode(message_type: str, field_name: str) -> None:
    """The criterion says dropped OR RETYPED. A present-but-wrongly-typed field refuses too."""
    frame = {"v": WIRE_VERSION, "type": message_type}
    frame.update({name: _SAMPLE[kind] for name, kind in WIRE_SURFACE[message_type].items()})
    wrong = 1 if WIRE_SURFACE[message_type][field_name] is str else "not-an-int"
    frame[field_name] = wrong

    with pytest.raises(WireRefused, match=f"{message_type}.{field_name} must be"):
        decode(frame)


def test_the_consumer_contract_and_the_validator_cannot_drift_apart() -> None:
    """Catches the second sabotage: a field removed from CLIENT_CONTRACTS but still validated.

    Two declarations of one shape are two places to be wrong. Neither is authoritative alone, so
    the test that matters is that they agree.
    """
    from kernel.seam.wire import _FIELDS, CLIENT_CONTRACTS

    for contract in CLIENT_CONTRACTS:
        declared = {field.name for field in contract.fields} - {"v", "type"}
        validated = set(_FIELDS[contract.name])
        assert declared == validated, (
            f"contract {contract.name!r} declares {sorted(declared)} but the validator enforces "
            f"{sorted(validated)}; a Godot client reading the contract would be wrong"
        )
