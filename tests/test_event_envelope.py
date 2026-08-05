from __future__ import annotations

import pytest

from kernel.event_envelope import EventEnvelope, EventEnvelopeError


def _event() -> EventEnvelope:
    return EventEnvelope(
        protocol="codeforge.seed",
        version="1.0",
        event_id="evt-1",
        seed_id="seed-a",
        session_id="session-a",
        event_type="build.completed",
        timestamp="2026-08-05T12:00:00+00:00",
        classification="internal",
        payload={"passed": True},
        text_fallback="Build completed successfully.",
        accessibility_summary="The build passed.",
        correlation_id="job-1",
    )


def test_event_round_trips_and_has_fallbacks():
    event = _event()
    assert EventEnvelope.from_dict(event.to_dict()) == event
    assert event.render() == "Build completed successfully."
    assert event.render(accessible=True) == "The build passed."


@pytest.mark.parametrize("field", ["event_id", "text_fallback", "accessibility_summary"])
def test_required_text_is_validated(field: str):
    values = _event().to_dict()
    values[field] = ""
    with pytest.raises(EventEnvelopeError):
        EventEnvelope.from_dict(values)


def test_invalid_payload_and_timestamp_are_rejected():
    values = _event().to_dict()
    values["payload"] = {"bad": object()}
    with pytest.raises(EventEnvelopeError):
        EventEnvelope.from_dict(values)
    values = _event().to_dict()
    values["timestamp"] = "tomorrow"
    with pytest.raises(EventEnvelopeError):
        EventEnvelope.from_dict(values)
