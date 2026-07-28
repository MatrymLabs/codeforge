"""Test twin for parts.telemetry -- the protocol spine (one typed frame contract, two wire codecs).

Acceptance: the JSON reference round-trips every frame; the protobuf codec round-trips them too and
AGREES with JSON (same payload out); and -- the crown jewel -- a frame encoded by the Go binding
from the same .proto decodes identically in Python, and vice versa (one contract, two languages).
Refusal: an unknown kind, an empty frame, or a payload missing a field all fail loud.

The protobuf + cross-language tests skip cleanly when the generated code / Go binary are absent (a
fresh clone with no protobuf toolchain), so the always-present JSON reference is what gates.
"""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

import pytest

from parts.telemetry import (
    JSON_CODEC,
    KINDS,
    PROTOBUF_CODEC,
    SpineError,
    kind_for_package,
    spine_backend,
)

# The canonical fixtures -- duplicated, on purpose, in native/spine/xcheck/main.go. Change one,
# change the other: that duplication IS the cross-language contract test.
CANONICAL: dict[str, dict[str, object]] = {
    "vitals": {
        "hp": 20,
        "maxhp": 40,
        "mp": 5,
        "maxmp": 10,
        "level": 3,
        "xp": 150,
        "nextlevel": 300,
    },
    "room": {
        "num": "forge",
        "name": "The Cold Forge",
        "exits": {"north": "courtyard", "east": "tunnel"},
    },
    "target": {
        "name": "A cinder wight",
        "hp": 30,
        "maxhp": 100,
        "element": "flame",
        "resists": {"stone": "Resist"},
    },
    "quest": {"name": "Relight the Beacons", "objective": "reach Emberreach"},
}

_XCHECK = Path(__file__).resolve().parent.parent / "native" / "spine" / "xcheck" / "xcheck"

_needs_protobuf = pytest.mark.skipif(
    PROTOBUF_CODEC is None, reason="protobuf codec not built (run `make proto`)"
)
_needs_xcheck = pytest.mark.skipif(
    PROTOBUF_CODEC is None or not _XCHECK.is_file(),
    reason="cross-language check needs the protobuf codec + the built Go xcheck binary",
)


# --- the JSON reference (always tested) --------------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
def test_json_codec_round_trips_every_frame(kind):
    data = JSON_CODEC.encode(kind, CANONICAL[kind])
    assert isinstance(data, bytes)
    assert JSON_CODEC.decode(data) == (kind, CANONICAL[kind])


def test_kind_for_package_bridges_gmcp_and_ignores_others():
    assert kind_for_package("Char.Vitals") == "vitals"
    assert kind_for_package("Room.Info") == "room"
    assert kind_for_package("Comm.Channel") is None  # not a spine frame


def test_an_unknown_kind_is_refused_loudly():
    with pytest.raises(SpineError, match="unknown telemetry kind"):
        JSON_CODEC.encode("inventory", {})


def test_a_frame_without_a_payload_is_refused():
    with pytest.raises(SpineError, match="missing its payload"):
        JSON_CODEC.decode(b'{"kind":"vitals"}')


# --- the protobuf accelerator (when built) -----------------------------------------------------


@_needs_protobuf
@pytest.mark.parametrize("kind", KINDS)
def test_protobuf_codec_round_trips_and_agrees_with_json(kind):
    assert spine_backend() == "protobuf"
    data = PROTOBUF_CODEC.encode(kind, CANONICAL[kind])
    assert PROTOBUF_CODEC.decode(data) == (kind, CANONICAL[kind])
    # the two codecs are two encodings of ONE contract: they recover the identical frame
    assert PROTOBUF_CODEC.decode(data) == JSON_CODEC.decode(
        JSON_CODEC.encode(kind, CANONICAL[kind])
    )


@_needs_protobuf
def test_protobuf_is_more_compact_than_json_on_a_real_frame():
    # not a benchmark, just the qualitative claim the spine rests on: binary beats text on the wire
    frame = CANONICAL["vitals"]
    assert len(PROTOBUF_CODEC.encode("vitals", frame)) < len(JSON_CODEC.encode("vitals", frame))


@_needs_protobuf
def test_an_empty_protobuf_frame_is_refused():
    with pytest.raises(SpineError, match="empty telemetry frame"):
        PROTOBUF_CODEC.decode(b"")


@_needs_protobuf
def test_a_protobuf_frame_missing_a_field_is_refused():
    with pytest.raises(SpineError, match="missing field"):
        PROTOBUF_CODEC.encode("quest", {"name": "Nameless"})  # no objective


# --- the cross-language proof: Go <-> Python, one .proto ---------------------------------------


@_needs_xcheck
@pytest.mark.parametrize("kind", KINDS)
def test_go_encoded_frame_decodes_in_python(kind):
    # Go encodes the canonical frame; Python (from the same .proto) must decode it field-for-field.
    out = subprocess.run(
        [str(_XCHECK), "encode", kind], capture_output=True, text=True, check=True, timeout=15
    )
    raw = base64.b64decode(out.stdout.strip())
    assert PROTOBUF_CODEC.decode(raw) == (kind, CANONICAL[kind])


@_needs_xcheck
@pytest.mark.parametrize("kind", KINDS)
def test_python_encoded_frame_decodes_in_go(kind):
    # Python encodes; Go decodes and reports the payload as JSON, which must match the fixture.
    raw = PROTOBUF_CODEC.encode(kind, CANONICAL[kind])
    b64 = base64.b64encode(raw).decode()
    out = subprocess.run(
        [str(_XCHECK), "decode"], input=b64, capture_output=True, text=True, check=True, timeout=15
    )
    reported = json.loads(out.stdout)
    assert reported == {"kind": kind, "payload": CANONICAL[kind]}
