"""Validated, accessible, replayable Seed event envelopes.

This is an original additive contract over the existing GMCP and world Frame projections.
It carries authoritative event metadata without making the client authoritative. Text and
accessibility fallbacks remain mandatory so a structured-capable client is never required.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

CLASSIFICATIONS = frozenset({"public", "internal", "sensitive"})
SEMANTIC_CHANNELS = frozenset(
    {
        "navigation",
        "dialogue",
        "combat",
        "status",
        "urgent",
        "build",
        "test",
        "security",
        "accessibility",
        "deployment",
        "administrative",
        "background",
    }
)


class EventEnvelopeError(ValueError):
    """An event envelope is malformed or unsafe to publish."""


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EventEnvelopeError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_timestamp(value: str) -> str:
    candidate = _required_text(value, "timestamp").replace("Z", "+00:00")
    try:
        datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise EventEnvelopeError("timestamp must be ISO-8601") from exc
    return value


def _json_object(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise EventEnvelopeError("payload must be a JSON object")
    payload = dict(value)
    try:
        json.dumps(payload, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise EventEnvelopeError("payload must contain JSON-serializable values") from exc
    return payload


@dataclass(frozen=True)
class EventEnvelope:
    """The canonical Seed event projection contract."""

    protocol: str
    version: str
    event_id: str
    seed_id: str
    session_id: str
    event_type: str
    timestamp: str
    classification: str
    payload: Mapping[str, object]
    text_fallback: str
    accessibility_summary: str
    correlation_id: str
    localization_key: str = ""
    semantic_channel: str = "status"

    def __post_init__(self) -> None:
        for field in (
            "protocol",
            "version",
            "event_id",
            "seed_id",
            "session_id",
            "event_type",
            "correlation_id",
        ):
            object.__setattr__(self, field, _required_text(getattr(self, field), field))
        object.__setattr__(self, "timestamp", _validate_timestamp(self.timestamp))
        classification = _required_text(self.classification, "classification")
        if classification not in CLASSIFICATIONS:
            raise EventEnvelopeError(f"classification must be one of {sorted(CLASSIFICATIONS)}")
        object.__setattr__(self, "classification", classification)
        object.__setattr__(self, "payload", _json_object(self.payload))
        object.__setattr__(
            self,
            "text_fallback",
            _required_text(self.text_fallback, "text_fallback"),
        )
        object.__setattr__(
            self,
            "accessibility_summary",
            _required_text(self.accessibility_summary, "accessibility_summary"),
        )
        if self.localization_key and not isinstance(self.localization_key, str):
            raise EventEnvelopeError("localization_key must be a string")
        channel = _required_text(self.semantic_channel, "semantic_channel")
        if channel not in SEMANTIC_CHANNELS:
            raise EventEnvelopeError(
                f"semantic_channel must be one of {sorted(SEMANTIC_CHANNELS)}"
            )
        object.__setattr__(self, "semantic_channel", channel)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe wire representation."""
        return {
            "protocol": self.protocol,
            "version": self.version,
            "event_id": self.event_id,
            "seed_id": self.seed_id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "classification": self.classification,
            "payload": dict(self.payload),
            "text_fallback": self.text_fallback,
            "accessibility_summary": self.accessibility_summary,
            "correlation_id": self.correlation_id,
            "localization_key": self.localization_key,
            "semantic_channel": self.semantic_channel,
        }

    @classmethod
    def from_dict(cls, value: object) -> EventEnvelope:
        """Validate an untrusted decoded event object."""
        if not isinstance(value, dict):
            raise EventEnvelopeError("event envelope must be an object")
        required = (
            "protocol",
            "version",
            "event_id",
            "seed_id",
            "session_id",
            "event_type",
            "timestamp",
            "classification",
            "payload",
            "text_fallback",
            "accessibility_summary",
            "correlation_id",
        )
        missing = [field for field in required if field not in value]
        if missing:
            raise EventEnvelopeError(f"event envelope missing: {', '.join(missing)}")
        return cls(
            **{
                key: value[key]
                for key in (*required, "localization_key", "semantic_channel")
                if key in value
            }
        )

    def render(self, *, accessible: bool = False) -> str:
        """Render the appropriate human-readable projection."""
        return self.accessibility_summary if accessible else self.text_fallback
