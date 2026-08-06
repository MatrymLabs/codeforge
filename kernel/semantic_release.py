"""Machine-checkable semantic and accessibility release evidence for one workflow."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from kernel.event_envelope import EventEnvelope
from kernel.shelf.atomic_write import atomic_write_text

HUMAN_RESULTS = ("passed", "pending", "failed")
_SAFE = re.compile(r"^[A-Za-z0-9_.:-]+$")


class SemanticReleaseError(ValueError):
    """Semantic release evidence is incomplete or malformed."""


@dataclass(frozen=True)
class SemanticReleaseEvidence:
    """Evidence packet for a text-first, accessible workflow projection."""

    workflow_id: str
    event_ids: tuple[str, ...]
    transcript: str
    keyboard_paths: tuple[str, ...]
    reduced_motion_tested: bool
    human_validation: str
    localization_keys: tuple[str, ...]
    human_validator: str = ""
    human_evidence_id: str = ""
    assistive_technology: str = ""
    semantic_channels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _SAFE.fullmatch(self.workflow_id.strip()):
            raise SemanticReleaseError("workflow_id must be a safe identifier")
        if not self.event_ids or any(not _SAFE.fullmatch(item) for item in self.event_ids):
            raise SemanticReleaseError("event_ids must be safe and non-empty")
        if not self.transcript.strip():
            raise SemanticReleaseError("transcript must not be empty")
        if not self.keyboard_paths or any(not item.strip() for item in self.keyboard_paths):
            raise SemanticReleaseError("keyboard paths must be recorded")
        if self.human_validation not in HUMAN_RESULTS:
            raise SemanticReleaseError("human_validation has an unknown result")
        if len(self.localization_keys) != len(self.event_ids) or any(
            not item.strip() for item in self.localization_keys
        ):
            raise SemanticReleaseError("every event must have a localization key")
        if self.human_validation == "passed" and not all(
            item.strip()
            for item in (
                self.human_validator,
                self.human_evidence_id,
                self.assistive_technology,
            )
        ):
            raise SemanticReleaseError(
                "passed human validation requires validator, evidence, and assistive technology"
            )
        if self.semantic_channels and len(self.semantic_channels) != len(self.event_ids):
            raise SemanticReleaseError("every event must have a semantic channel")

    @property
    def automated_checks_pass(self) -> bool:
        return (
            bool(self.transcript.strip())
            and bool(self.keyboard_paths)
            and self.reduced_motion_tested
        )

    @property
    def release_ready(self) -> bool:
        """Only human validation can complete the accessibility release gate."""
        return (
            self.automated_checks_pass
            and self.human_validation == "passed"
            and bool(self.human_validator.strip())
            and bool(self.human_evidence_id.strip())
            and bool(self.assistive_technology.strip())
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "workflow_id": self.workflow_id,
            "event_ids": list(self.event_ids),
            "transcript": self.transcript,
            "keyboard_paths": list(self.keyboard_paths),
            "reduced_motion_tested": self.reduced_motion_tested,
            "human_validation": self.human_validation,
            "localization_keys": list(self.localization_keys),
            "human_validator": self.human_validator,
            "human_evidence_id": self.human_evidence_id,
            "assistive_technology": self.assistive_technology,
            "semantic_channels": list(self.semantic_channels),
            "automated_checks_pass": self.automated_checks_pass,
            "release_ready": self.release_ready,
        }

    def save(self, path: Path) -> None:
        atomic_write_text(Path(path), json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")


def collect_semantic_release(
    workflow_id: str,
    events: Iterable[EventEnvelope],
    *,
    transcript: str,
    keyboard_paths: tuple[str, ...],
    reduced_motion_tested: bool,
    human_validation: str = "pending",
    human_validator: str = "",
    human_evidence_id: str = "",
    assistive_technology: str = "",
) -> SemanticReleaseEvidence:
    """Build evidence only from events that satisfy the Seed envelope's semantic fallbacks."""
    collected = tuple(events)
    if not collected:
        raise SemanticReleaseError("workflow must emit at least one event")
    for event in collected:
        if not event.text_fallback.strip() or not event.accessibility_summary.strip():
            raise SemanticReleaseError(f"event {event.event_id!r} lacks a semantic fallback")
        if not event.localization_key.strip():
            raise SemanticReleaseError(f"event {event.event_id!r} lacks a localization key")
    return SemanticReleaseEvidence(
        workflow_id=workflow_id,
        event_ids=tuple(event.event_id for event in collected),
        transcript=transcript,
        keyboard_paths=keyboard_paths,
        reduced_motion_tested=reduced_motion_tested,
        human_validation=human_validation,
        localization_keys=tuple(event.localization_key for event in collected),
        human_validator=human_validator,
        human_evidence_id=human_evidence_id,
        assistive_technology=assistive_technology,
        semantic_channels=tuple(event.semantic_channel for event in collected),
    )
