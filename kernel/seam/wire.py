"""The Engine-2D wire schema, versioned and refused when it is not understood."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kernel.shelf.contract import Contract, Field

WIRE_VERSION = 1


class WireRefused(ValueError):  # noqa: N818
    """A frame was not a message this version of the protocol can safely use."""

    verdict = "REFUSED"


_FIELDS: dict[str, dict[str, type]] = {
    "hello": {"session": str},
    "move_intent": {"direction": str},
    "entity_state": {"entity_id": str, "x": int, "y": int},
    "tick": {"tick": int},
    "refused": {"verdict": str, "reason": str},
}


def _refuse(reason: str) -> WireRefused:
    return WireRefused(f"REFUSED: {reason}")


def _validate(message: Mapping[str, Any]) -> dict[str, Any]:
    message_type = message.get("type")
    if not isinstance(message_type, str) or message_type not in _FIELDS:
        raise _refuse("unknown message type")  # noqa: TRY003
    for name, expected_type in _FIELDS[message_type].items():
        if name not in message:
            raise _refuse(f"{message_type}.{name} is required")  # noqa: TRY003
        value = message[name]
        if expected_type is int:
            valid = isinstance(value, int) and not isinstance(value, bool)
        else:
            valid = isinstance(value, expected_type)
        if not valid:
            raise _refuse(f"{message_type}.{name} must be {expected_type.__name__}")  # noqa: TRY003
    return dict(message)


def _message(message_type: str, **fields: Any) -> dict[str, Any]:
    return _validate({"type": message_type, **fields})


def hello(*, session: str) -> dict[str, Any]:
    """Construct the first frame a connected Engine-2D client sends."""
    return _message("hello", session=session)


def move_intent(*, direction: str) -> dict[str, Any]:
    """Construct a movement request. Routing it to the world is a later packet."""
    return _message("move_intent", direction=direction)


def entity_state(*, entity_id: str, x: int, y: int) -> dict[str, Any]:
    """Construct one entity's client-visible spatial state."""
    return _message("entity_state", entity_id=entity_id, x=x, y=y)


def tick(*, tick: int) -> dict[str, Any]:
    """Construct a server timing frame."""
    return _message("tick", tick=tick)


def refused(*, reason: str) -> dict[str, Any]:
    """Construct a versioned refusal frame for an unsafe inbound message."""
    return _message("refused", verdict="REFUSED", reason=reason)


def encode(message: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an outbound message and add this schema's version."""
    if not isinstance(message, Mapping):
        raise _refuse("message must be an object")  # noqa: TRY003
    if "v" in message:
        raise _refuse("outbound messages must not set their own version")  # noqa: TRY003
    return {"v": WIRE_VERSION, **_validate(message)}


def decode(payload: Any) -> dict[str, Any]:
    """Refuse unknown versions and malformed frames before application code sees them."""
    if not isinstance(payload, Mapping):
        raise _refuse("message must be an object")  # noqa: TRY003
    version = payload.get("v")
    if not isinstance(version, int) or isinstance(version, bool):
        raise _refuse("message version is required")  # noqa: TRY003
    if version != WIRE_VERSION:
        raise _refuse(f"unknown message version {version}")  # noqa: TRY003
    return _validate({key: value for key, value in payload.items() if key != "v"})


CLIENT_CONTRACTS = (
    Contract(
        name="hello",
        consumer="godot-engine-2d",
        fields=(Field("v", int), Field("type", str), Field("session", str)),
    ),
)
