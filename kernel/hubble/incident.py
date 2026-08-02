"""CARD: hubble.incident -- a typed, queryable incident record that emits corrective controls.

RD-2026-0002 #14. The fleet has an incident-response RUNBOOK (prose) but no typed record, so an
incident leaves a retrospective document, not reusable controls. This is the record the Clinical
Workflow research specifies: a validated `Incident` with severity, type (including `hallucination`,
the AI-specific failure mode), containment (was a rollback executed, a kill-switch used), root
causes, corrective actions, and follow-up checks. Its point is the last clause: corrective_controls
turns each incident into pinned regressions (a follow-up check the chronicle can guard-pin), so the
same defect cannot recur silently -- "every event generates corrective controls, not just a
retrospective."

Validated + JSON round-tripping (fail loud on a bad severity/type), stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Severity ladder (sev1 worst). Type includes the AI-specific `hallucination` failure mode.
SEVERITIES = ("sev1_critical", "sev2_high", "sev3_medium", "sev4_low")
INCIDENT_TYPES = (
    "security",
    "data_loss",
    "outage",
    "regression",
    "hallucination",  # AI produced an ungrounded/incorrect change that reached prod
    "supply_chain",
    "config_error",
)


class IncidentError(ValueError):
    """Raised on a malformed incident (unknown severity/type, missing id)."""


@dataclass(frozen=True)
class Incident:
    """One incident: what happened, how bad, how contained, and what prevents recurrence."""

    incident_id: str
    severity: str  # a SEVERITIES value
    type: str  # an INCIDENT_TYPES value
    summary: str
    root_causes: tuple[str, ...] = ()
    corrective_actions: tuple[str, ...] = ()
    follow_up_checks: tuple[
        str, ...
    ] = ()  # pinnable regression checks (the corrective-control seed)
    rollback_executed: bool = False
    kill_switch_used: bool = False
    detected_by: str = ""

    def __post_init__(self) -> None:
        if not self.incident_id.strip():
            raise IncidentError("incident needs an id")
        if self.severity not in SEVERITIES:
            raise IncidentError(f"unknown severity {self.severity!r}; choose {SEVERITIES}")
        if self.type not in INCIDENT_TYPES:
            raise IncidentError(f"unknown type {self.type!r}; choose {INCIDENT_TYPES}")
        if not self.summary.strip():
            raise IncidentError(f"incident {self.incident_id!r} needs a summary")


@dataclass(frozen=True)
class CorrectiveControl:
    """A reusable control derived from an incident: a check to pin so the defect cannot recur."""

    incident_id: str
    control: str  # the follow-up check to enforce
    kind: str  # "regression_test" | "gate" | "review"


def corrective_controls(incident: Incident) -> list[CorrectiveControl]:
    """Turn an incident's follow-up checks into pinnable corrective controls (not a retrospective).

    Each follow-up check becomes a regression control keyed to the incident, so the chronicle can
    guard-pin it. An incident with no follow-up checks yields none - and that absence is itself a
    signal (a closed incident that pinned nothing did not actually learn)."""
    return [
        CorrectiveControl(incident.incident_id, check, "regression_test")
        for check in incident.follow_up_checks
    ]


def to_dict(incident: Incident) -> dict[str, Any]:
    """Serialize to a plain dict (JSON/YAML-simple), round-tripping with from_dict."""
    return {
        "incident_id": incident.incident_id,
        "severity": incident.severity,
        "type": incident.type,
        "summary": incident.summary,
        "root_causes": list(incident.root_causes),
        "corrective_actions": list(incident.corrective_actions),
        "follow_up_checks": list(incident.follow_up_checks),
        "rollback_executed": incident.rollback_executed,
        "kill_switch_used": incident.kill_switch_used,
        "detected_by": incident.detected_by,
    }


def _strs(raw: Any, name: str, incident_id: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str) or not hasattr(raw, "__iter__"):
        raise IncidentError(f"incident {incident_id!r}: {name!r} must be a list of strings")
    return tuple(str(item) for item in raw)


def from_dict(raw: Any) -> Incident:
    """Parse an incident from a plain dict. A bad field fails loud (a gate, like any loader)."""
    if not isinstance(raw, dict):
        raise IncidentError("an incident record must be a mapping")
    incident_id = str(raw.get("incident_id", "")).strip()
    if not incident_id:
        raise IncidentError("incident record missing 'incident_id'")
    return Incident(
        incident_id=incident_id,
        severity=str(raw.get("severity", "")),
        type=str(raw.get("type", "")),
        summary=str(raw.get("summary", "")),
        root_causes=_strs(raw.get("root_causes"), "root_causes", incident_id),
        corrective_actions=_strs(raw.get("corrective_actions"), "corrective_actions", incident_id),
        follow_up_checks=_strs(raw.get("follow_up_checks"), "follow_up_checks", incident_id),
        rollback_executed=bool(raw.get("rollback_executed", False)),
        kill_switch_used=bool(raw.get("kill_switch_used", False)),
        detected_by=str(raw.get("detected_by", "")),
    )
