"""CARD: telemetry -- the protocol spine: one typed frame contract, two wire codecs.

The telemetry frames the engine projects to a client (Char.Vitals / Room.Info / Char.Target /
Char.Quest) have ONE schema, defined once in `proto/telemetry.proto` and compiled to every language
(Python + Go today, C++ later). This module is the Python end of that spine: a frame is a
`(kind, payload)` pair, and two codecs serialise it.

- **JSON codec** -- the Python-first reference (stdlib `json`). Always available; the game falls
  back to it and the protobuf codec is proven against its behaviour.
- **Protobuf codec** -- the optional accelerator (compact binary, and byte-compatible with the Go
  binding from the same `.proto`). Present only when `proto/telemetry_pb2.py` has been generated
  (`make proto`); absent on a fresh clone, so the spine still works with no protobuf toolchain.

The JSON GMCP frames the live client speaks are unchanged: this schema is the typed transport for
cross-language services (a Go telemetry channel, analytics), proven to carry the very frames
`kernel/gmcp.py` emits. Keep the two in step.

Inputs:  a frame kind (one of KINDS) + its payload dict (the GMCP shape for that kind).
Outputs: wire bytes (encode) / the same (kind, payload) back (decode). Unknown kinds fail loud.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

# The four telemetry frames the spine carries, matching kernel/gmcp.py's projections.
KINDS = ("vitals", "room", "target", "quest")

# The GMCP package name each spine kind corresponds to, so a caller can bridge the live GMCP
# projections into the typed spine without hard-coding the mapping twice.
_PACKAGE_TO_KIND = {
    "Char.Vitals": "vitals",
    "Room.Info": "room",
    "Char.Target": "target",
    "Char.Quest": "quest",
}


class SpineError(ValueError):
    """A frame that violates the contract: an unknown kind, or a payload missing a field."""


def kind_for_package(package: str) -> str | None:
    """Map a GMCP package name (e.g. 'Char.Vitals') to a spine kind, or None if it is not a spine
    frame. Lets kernel/gmcp.py feed its projections through the spine without a second mapping."""
    return _PACKAGE_TO_KIND.get(package)


def _require(kind: str) -> None:
    if kind not in KINDS:
        raise SpineError(f"unknown telemetry kind {kind!r}; expected one of {KINDS}")


# --- the JSON codec: the Python-first reference (always available) -----------------------------


class JsonCodec:
    """Serialise a frame as compact JSON: the reference implementation and always-there fallback."""

    name = "json"

    def encode(self, kind: str, payload: Mapping[str, object]) -> bytes:
        _require(kind)
        return json.dumps({"kind": kind, "payload": dict(payload)}, separators=(",", ":")).encode()

    def decode(self, data: bytes) -> tuple[str, dict[str, object]]:
        obj = json.loads(data)
        kind = obj.get("kind")
        if kind not in KINDS:
            raise SpineError(f"decoded an unknown telemetry kind {kind!r}")
        payload = obj.get("payload")
        if not isinstance(payload, dict):
            raise SpineError("telemetry frame is missing its payload object")
        return kind, payload


# --- the protobuf codec: the optional cross-language accelerator -------------------------------

# The generated binding is loaded dynamically and typed Any: a string import mypy cannot resolve to
# a partial `proto` package (which would be attr-defined when the submodule is absent), so the type
# surface stays consistent whether or not `make proto` has been run.
try:  # pragma: no cover - presence depends on whether `make proto` has been run
    import importlib

    _pb: Any = importlib.import_module("proto.telemetry_pb2")
    _HAS_PROTOBUF = True
except ImportError:  # pragma: no cover - the fallback path (no protobuf toolchain / not generated)
    _pb = None
    _HAS_PROTOBUF = False


def _vitals_to_pb(frame: Any, p: Mapping[str, object]) -> None:
    v = frame.vitals
    v.hp, v.maxhp, v.mp, v.maxmp = p["hp"], p["maxhp"], p["mp"], p["maxmp"]
    v.level, v.xp, v.nextlevel = p["level"], p["xp"], p["nextlevel"]


def _vitals_from_pb(v: Any) -> dict[str, object]:
    return {k: getattr(v, k) for k in ("hp", "maxhp", "mp", "maxmp", "level", "xp", "nextlevel")}


def _room_to_pb(frame: Any, p: Mapping[str, object]) -> None:
    r = frame.room
    r.num, r.name = p["num"], p["name"]
    for direction, dest in dict(p["exits"]).items():  # type: ignore[call-overload]
        r.exits[direction] = dest


def _room_from_pb(r: Any) -> dict[str, object]:
    return {"num": r.num, "name": r.name, "exits": dict(r.exits)}


def _target_to_pb(frame: Any, p: Mapping[str, object]) -> None:
    t = frame.target
    t.name, t.hp, t.maxhp = p["name"], p["hp"], p["maxhp"]
    if p.get("element"):  # additive/optional: only set when the foe is typed
        t.element = p["element"]
    for elem, level in dict(p.get("resists", {})).items():  # type: ignore[call-overload]
        t.resists[elem] = level


def _target_from_pb(t: Any) -> dict[str, object]:
    out: dict[str, object] = {"name": t.name, "hp": t.hp, "maxhp": t.maxhp}
    if t.element:
        out["element"] = t.element
    if t.resists:
        out["resists"] = dict(t.resists)
    return out


def _quest_to_pb(frame: Any, p: Mapping[str, object]) -> None:
    q = frame.quest
    q.name, q.objective = p["name"], p["objective"]


def _quest_from_pb(q: Any) -> dict[str, object]:
    return {"name": q.name, "objective": q.objective}


_TO_PB = {
    "vitals": _vitals_to_pb,
    "room": _room_to_pb,
    "target": _target_to_pb,
    "quest": _quest_to_pb,
}
_FROM_PB = {
    "vitals": _vitals_from_pb,
    "room": _room_from_pb,
    "target": _target_from_pb,
    "quest": _quest_from_pb,
}


class ProtobufCodec:
    """Serialise a frame as Protocol Buffers -- compact, and byte-compatible with the Go binding
    generated from the same .proto. Only usable when the generated module has been built."""

    name = "protobuf"

    def __init__(self) -> None:
        if not _HAS_PROTOBUF:
            raise SpineError(
                "protobuf codec unavailable: run `make proto` to generate proto/telemetry_pb2.py"
            )

    def encode(self, kind: str, payload: Mapping[str, object]) -> bytes:
        _require(kind)
        frame = _pb.Frame()
        try:
            _TO_PB[kind](frame, payload)
        except KeyError as missing:
            raise SpineError(f"telemetry {kind} frame missing field {missing}") from missing
        return frame.SerializeToString()

    def decode(self, data: bytes) -> tuple[str, dict[str, object]]:
        frame = _pb.Frame()
        frame.ParseFromString(data)
        kind = frame.WhichOneof("body")
        if kind is None:
            raise SpineError("decoded an empty telemetry frame (no body set)")
        return kind, _FROM_PB[kind](getattr(frame, kind))


# --- backend selection (ADR-0010/0011): protobuf when built, else the json reference ------------

JSON_CODEC = JsonCodec()
PROTOBUF_CODEC: ProtobufCodec | None = ProtobufCodec() if _HAS_PROTOBUF else None


def spine_backend() -> str:
    """Which codec the spine would prefer right now: 'protobuf' when generated, else 'json'."""
    return "protobuf" if _HAS_PROTOBUF else "json"


def default_codec() -> JsonCodec | ProtobufCodec:
    """The preferred codec: the protobuf accelerator when built, else the json reference."""
    return PROTOBUF_CODEC if PROTOBUF_CODEC is not None else JSON_CODEC
