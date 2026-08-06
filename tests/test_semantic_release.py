"""CF-402: semantic event and accessibility release gate."""

from __future__ import annotations

import pytest

from kernel.event_envelope import EventEnvelope
from kernel.semantic_release import SemanticReleaseError, collect_semantic_release


def _event(event_id: str = "evt-build") -> EventEnvelope:
    return EventEnvelope(
        protocol="codeforge.seed",
        version="1.0",
        event_id=event_id,
        seed_id="aethryn",
        session_id="session-1",
        event_type="build.completed",
        timestamp="2026-08-05T00:00:00Z",
        classification="internal",
        payload={"status": "passed"},
        text_fallback="The build passed.",
        accessibility_summary="Build passed.",
        correlation_id="corr-1",
        localization_key="build.completed",
        semantic_channel="build",
    )


def test_semantic_gate_keeps_automated_evidence_separate_from_human_validation() -> None:
    evidence = collect_semantic_release(
        "build-workflow",
        [_event()],
        transcript="Build passed.",
        keyboard_paths=("open build panel", "read result", "return to workspace"),
        reduced_motion_tested=True,
    )
    assert evidence.automated_checks_pass
    assert not evidence.release_ready
    assert evidence.human_validation == "pending"
    assert evidence.semantic_channels == ("build",)

    reviewed = collect_semantic_release(
        "build-workflow",
        [_event()],
        transcript="Build passed.",
        keyboard_paths=("open build panel", "read result", "return to workspace"),
        reduced_motion_tested=True,
        human_validation="passed",
        human_validator="screen-reader-reviewer",
        human_evidence_id="a11y-review-build-1",
        assistive_technology="NVDA 2026.1",
    )
    assert reviewed.release_ready

    with pytest.raises(SemanticReleaseError, match="human validation requires"):
        collect_semantic_release(
            "build-workflow",
            [_event("evt-build-no-human-record")],
            transcript="Build passed.",
            keyboard_paths=("read result",),
            reduced_motion_tested=True,
            human_validation="passed",
        )


def test_semantic_gate_rejects_events_without_localization_keys() -> None:
    raw = _event()
    event = EventEnvelope.from_dict({**raw.to_dict(), "localization_key": ""})
    with pytest.raises(SemanticReleaseError, match="localization key"):
        collect_semantic_release(
            "build-workflow",
            [event],
            transcript="Build passed.",
            keyboard_paths=("read result",),
            reduced_motion_tested=True,
        )
