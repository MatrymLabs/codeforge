"""CARD: trace -- carry one correlation id across a multi-hop request so logs correlate end to end.

Clean-room reconstruction of the W3C Trace Context `traceparent` field
(`version-trace_id-span_id-flags`). Standard library only; no OpenTelemetry.

A Trace is an immutable correlation context. It is minted once at the edge
(start_trace), carried across a boundary as a `traceparent` string, continued on
the far side (continue_trace) where the inbound span becomes this hop's parent,
and bound into structured logs (log_fields). Propagation within a task or thread
is ambient via contextvars, so the pure-function tick signature never changes.

Signature-voice: a Trace threads a single thread through the whole request.
"""

from __future__ import annotations

import contextvars
import os
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

# ------------------------------------------------------------------ constants
_TRACE_ID_HEX = 32  # 16 bytes
_SPAN_ID_HEX = 16  # 8 bytes
_ZERO_TRACE = "0" * _TRACE_ID_HEX
_ZERO_SPAN = "0" * _SPAN_ID_HEX
_SUPPORTED_VERSION = "00"
_INVALID_VERSION = "ff"  # W3C reserves ff as invalid
FLAG_SAMPLED = 0x01

# W3C requires LOWERCASE hex; an uppercase id is malformed on purpose here.
_LOWER_HEX = re.compile(r"\A[0-9a-f]+\Z")
_TRACEPARENT = re.compile(r"\A[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}\Z")

# An id factory takes a byte count and returns that many bytes as lowercase hex.
# Injectable so tests can pin ids instead of drawing entropy.
IdFactory = Callable[[int], str]


def _default_id(n_bytes: int) -> str:
    return os.urandom(n_bytes).hex()


class TraceError(ValueError):
    """Raised when a trace id, span id, or traceparent header is malformed."""


def _require_hex(value: str, length: int, label: str) -> None:
    if not isinstance(value, str):
        raise TraceError(f"{label} must be a string, got {type(value).__name__}")
    if len(value) != length:
        raise TraceError(f"{label} must be {length} hex chars, got {len(value)}")
    if not _LOWER_HEX.match(value):
        raise TraceError(f"{label} must be lowercase hex: {value!r}")


# --------------------------------------------------------------------- Trace
@dataclass(frozen=True)
class Trace:
    """One correlation context. Immutable; validates on construction."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    sampled: bool = True

    def __post_init__(self) -> None:
        _require_hex(self.trace_id, _TRACE_ID_HEX, "trace_id")
        _require_hex(self.span_id, _SPAN_ID_HEX, "span_id")
        if self.trace_id == _ZERO_TRACE:
            raise TraceError("trace_id must not be all zero")
        if self.span_id == _ZERO_SPAN:
            raise TraceError("span_id must not be all zero")
        if self.parent_span_id is not None:
            _require_hex(self.parent_span_id, _SPAN_ID_HEX, "parent_span_id")
            if self.parent_span_id == _ZERO_SPAN:
                raise TraceError("parent_span_id must not be all zero")

    def traceparent(self) -> str:
        """Serialize to the W3C wire format for carrying across a boundary."""
        flags = "01" if self.sampled else "00"
        return f"{_SUPPORTED_VERSION}-{self.trace_id}-{self.span_id}-{flags}"

    def log_fields(self) -> dict[str, str]:
        """The non-secret fields to merge into a structured log line."""
        return {"trace_id": self.trace_id, "span_id": self.span_id}


# ------------------------------------------------------------------ minting
def _new_span(rng: IdFactory) -> str:
    return rng(_SPAN_ID_HEX // 2)


def _new_trace_id(rng: IdFactory) -> str:
    return rng(_TRACE_ID_HEX // 2)


def start_trace(*, rng: IdFactory = _default_id, sampled: bool = True) -> Trace:
    """Mint a fresh Trace at the edge of the system (no inbound context)."""
    return Trace(
        trace_id=_new_trace_id(rng),
        span_id=_new_span(rng),
        parent_span_id=None,
        sampled=sampled,
    )


def parse_traceparent(header: str) -> Trace:
    """Parse an inbound traceparent string into the REMOTE hop's Trace.

    The returned span_id is the remote span; use continue_trace to mint a local
    child under it.
    """
    if not isinstance(header, str):
        raise TraceError(f"traceparent must be a string, got {type(header).__name__}")
    if not _TRACEPARENT.match(header):
        raise TraceError(f"malformed traceparent: {header!r}")
    version, trace_id, span_id, flags = header.split("-")
    if version == _INVALID_VERSION:
        raise TraceError("traceparent version ff is invalid")
    if version != _SUPPORTED_VERSION:
        raise TraceError(f"unsupported traceparent version {version!r}")
    if trace_id == _ZERO_TRACE or span_id == _ZERO_SPAN:
        raise TraceError("traceparent contains an all-zero id")
    sampled = bool(int(flags, 16) & FLAG_SAMPLED)
    return Trace(trace_id=trace_id, span_id=span_id, sampled=sampled)


def continue_trace(header: str, *, rng: IdFactory = _default_id) -> Trace:
    """Continue an inbound trace: same trace_id, a NEW child span, parent = inbound span."""
    inbound = parse_traceparent(header)
    return Trace(
        trace_id=inbound.trace_id,
        span_id=_new_span(rng),
        parent_span_id=inbound.span_id,
        sampled=inbound.sampled,
    )


def child_span(parent: Trace, *, rng: IdFactory = _default_id) -> Trace:
    """Mint another span in the same trace, under the given parent."""
    return Trace(
        trace_id=parent.trace_id,
        span_id=_new_span(rng),
        parent_span_id=parent.span_id,
        sampled=parent.sampled,
    )


# ------------------------------------------------- ambient propagation
_current: contextvars.ContextVar[Trace | None] = contextvars.ContextVar(
    "codeforge_trace", default=None
)


def current() -> Trace | None:
    """The Trace active in this task/thread, or None."""
    return _current.get()


@contextmanager
def use_trace(trace: Trace) -> Iterator[Trace]:
    """Set the ambient Trace for the duration of the block, then restore."""
    token = _current.set(trace)
    try:
        yield trace
    finally:
        _current.reset(token)


@contextmanager
def enter_span(*, rng: IdFactory = _default_id) -> Iterator[Trace]:
    """Enter a child span of the current Trace (or start a fresh one), ambiently.

    The natural wrapper for a world-tick handling one command: whatever trace the
    gateway set becomes this span's parent, and the child is the ambient trace
    inside the block.
    """
    active = current()
    span = child_span(active, rng=rng) if active is not None else start_trace(rng=rng)
    with use_trace(span):
        yield span
