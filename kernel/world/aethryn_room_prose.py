"""CARD: aethryn_room_prose -- deterministic room presentation generation and review."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

PRESENTATION_VERSION = "aethryn-room-v1"
_PLACEHOLDER_TERMS = (
    "default room description",
    "zone (levels",
    "placeholder",
    "todo",
    "tbd",
    "room description goes here",
)
_LEGACY_TERMS = (
    "forge metaphysics",
    "the unforging",
    "ember metaphysics",
    "unforging",
    "the forge is current",
    "ember is current",
)
_TEMPORAL_MARKERS = ("currently", "right now", "at present", "for now", "today")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class RoomProseFinding:
    """One actionable room prose finding."""

    code: str
    path: str
    message: str
    action: str


def _area_name(packet: Any, room: Mapping[str, Any]) -> str:
    explicit = str(room.get("area_name", "")).strip()
    if explicit:
        return explicit
    raw = str(room.get("parent_zone", packet.parent_zone))
    names = {
        "veridia_zone": "Veridia",
        "duskwood_vale": "Duskwood Vale",
        "caeloria_zone": "Caeloria",
    }
    if raw in names:
        return names[raw]
    return raw.replace("_", " ").title()


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_END.split(_text(text)) if part.strip()]


def _short_description(base: str) -> str:
    sentences = _sentences(base)
    if not sentences:
        return ""
    if len(sentences) == 1:
        words = sentences[0].split()
        if len(words) > 34:
            return " ".join(words[:34]).rstrip(" ,;:") + "."
        return sentences[0]
    return " ".join(sentences[:2])


def _record_room(record: Mapping[str, Any]) -> str:
    return str(record.get("location") or record.get("source_room") or "")


def _purpose_text(room: Mapping[str, Any]) -> str:
    purposes = [str(value).replace("_", " ") for value in room.get("purpose", ())]
    if not purposes:
        return "local work and passage"
    if len(purposes) == 1:
        return f"{purposes[0]} work"
    if len(purposes) == 2:
        return f"{purposes[0]} and {purposes[1]} work"
    return f"{', '.join(purposes[:2])}, and {purposes[2]} work"


def _context_sentence(packet: Any, room: Mapping[str, Any]) -> str:
    area = _area_name(packet, room)
    room_type = _text(room.get("room_type", "room")).lower()
    purpose = _purpose_text(room)
    terrain = _text(packet.geography_profile.get("terrain", "the local terrain"))
    architecture = _text(
        next(iter(packet.architecture_profile.values()), "locally maintained construction")
    )
    variants = (
        f"In {area}, this {room_type} exists for {purpose}; {terrain} gives the work its shape.",
        f"The {area} setting makes its {purpose} purpose visible in the {architecture} built "
        f"where {terrain} meets the route.",
        f"Its materials and position belong to {area}: {terrain} meets "
        f"{architecture} at this threshold.",
        f"This {room_type} is a working part of {area}, where {purpose} follows {terrain} "
        "and the local weather.",
    )
    label = str(room.get("id", ""))
    index = sum((position + 1) * ord(char) for position, char in enumerate(label)) % len(variants)
    return variants[index]


def _explicit_points(room: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = room.get("points_of_interest", ())
    if not isinstance(raw, list):
        return []
    return [dict(value) for value in raw if isinstance(value, dict)]


def _points_of_interest(
    room: Mapping[str, Any], records: Mapping[str, tuple[Mapping[str, Any], ...]]
) -> list[dict[str, Any]]:
    points = _explicit_points(room)
    known = {str(point.get("id")) for point in points}
    room_id = str(room.get("id", ""))
    for kind, actions in (
        ("items", ["examine", "take"]),
        ("resource_nodes", ["examine", "gather"]),
    ):
        for record in records.get(kind, ()):
            if _record_room(record) != room_id or str(record.get("id")) in known:
                continue
            record_id = str(record.get("id", ""))
            points.append(
                {
                    "id": record_id,
                    "display": str(record.get("display_name", record_id)),
                    "kind": "resource" if kind == "resource_nodes" else "object",
                    "actions": actions,
                    "source_record": record_id,
                }
            )
            known.add(record_id)
    return points


def _conditions(
    room: Mapping[str, Any], records: Mapping[str, tuple[Mapping[str, Any], ...]]
) -> list[dict[str, Any]]:
    room_id = str(room.get("id", ""))
    conditions: list[dict[str, Any]] = []
    for state in records.get("state_changes", ()):
        if str(state.get("room_id", "")) != room_id:
            continue
        key = str(state.get("key", ""))
        conditions.append(
            {
                "id": f"state:{key}",
                "kind": "state",
                "state_key": key,
                "values": list(state.get("reversible_values", [])),
                "display": str(state.get("visible_projection", "")),
            }
        )
    for pressure in records.get("quest_pressures", ()):
        affected = {str(value) for value in pressure.get("affected_records", ())}
        if room_id not in affected:
            continue
        pressure_id = str(pressure.get("id", ""))
        conditions.append(
            {
                "id": f"pressure:{pressure_id}",
                "kind": "pressure",
                "source_record": pressure_id,
                "display": str(pressure.get("pressure", "local pressure")),
            }
        )
    return conditions


def build_room_presentation(
    packet: Any,
    room: Mapping[str, Any],
    records: Mapping[str, tuple[Mapping[str, Any], ...]],
) -> dict[str, Any]:
    """Build a complete deterministic presentation without calling a model or network."""
    room_id = str(room.get("id", ""))
    base = _text(room.get("long_description", room.get("description", room.get("desc", ""))))
    short = _text(room.get("short_description")) or _short_description(base)
    long = _text(room.get("long_description")) or f"{base}\n\n{_context_sentence(packet, room)}"
    return {
        "presentation_version": PRESENTATION_VERSION,
        "area_name": _area_name(packet, room),
        "room_type": _text(room.get("room_type", "")),
        "primary_purpose": list(room.get("purpose", [])),
        "short_description": short,
        "long_description": long,
        "points_of_interest": _points_of_interest(room, records),
        "conditions": _conditions(room, records),
        "prose_status": str(room.get("prose_status", "GENERATED_LOCAL")),
        "prose_source": str(room.get("prose_source", "packet_description")),
        "exits": dict(room.get("exits", {})),
        "room_id": room_id,
    }


def build_packet_presentations(
    packet: Any, records: Mapping[str, tuple[Mapping[str, Any], ...]]
) -> dict[str, dict[str, Any]]:
    """Build all room presentations in stable packet order."""
    return {
        str(room["id"]): build_room_presentation(packet, room, records)
        for room in records.get("rooms", ())
    }


def similarity_report(presentations: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Report duplicates and repeated phrases without rejecting regional terminology."""
    descriptions = {
        room_id: _text(presentation.get("long_description", "")).casefold()
        for room_id, presentation in presentations.items()
    }
    groups: dict[str, list[str]] = {}
    for room_id, description in descriptions.items():
        groups.setdefault(description, []).append(room_id)
    duplicate_groups = [sorted(ids) for text, ids in groups.items() if text and len(ids) > 1]
    phrases: Counter[str] = Counter()
    for description in descriptions.values():
        words = re.findall(r"[a-z0-9']+", description)
        phrases.update(" ".join(words[index : index + 5]) for index in range(len(words) - 4))
    reused = [
        {"phrase": phrase, "count": count}
        for phrase, count in phrases.most_common()
        if count > 1 and len(set(phrase.split())) > 2
    ][:20]
    return {
        "presentation_version": PRESENTATION_VERSION,
        "room_count": len(descriptions),
        "unique_long_descriptions": len(set(descriptions.values())),
        "duplicate_groups": duplicate_groups,
        "reused_phrases": reused,
        "flags": ["exact_long_description_reuse"] if duplicate_groups else [],
    }


def validate_presentations(
    packet: Any,
    presentations: Mapping[str, Mapping[str, Any]],
    records: Mapping[str, tuple[Mapping[str, Any], ...]] | None = None,
) -> tuple[RoomProseFinding, ...]:
    """Validate complete room prose and return actionable findings."""
    findings: list[RoomProseFinding] = []
    seen: dict[str, str] = {}
    for room_id, presentation in presentations.items():
        path = f"records.rooms[{room_id}]"
        short = _text(presentation.get("short_description"))
        long = _text(presentation.get("long_description"))
        if not short:
            findings.append(
                RoomProseFinding(
                    "missing_short_description",
                    f"{path}.short_description",
                    "room has no short description",
                    "add short_description or a non-empty description",
                )
            )
        if not long:
            findings.append(
                RoomProseFinding(
                    "missing_long_description",
                    f"{path}.long_description",
                    "room has no long description",
                    "add long_description or a non-empty description",
                )
            )
        if len(_sentences(short)) > 2:
            findings.append(
                RoomProseFinding(
                    "short_description_too_long",
                    f"{path}.short_description",
                    "short description contains more than two sentences",
                    "reduce the short description to one or two immediate-identity sentences",
                )
            )
        if len(long.split()) < 20:
            findings.append(
                RoomProseFinding(
                    "long_description_too_short",
                    f"{path}.long_description",
                    "long description is too short to support look verbose",
                    "add room-specific environmental, material, or gameplay detail",
                )
            )
        lowered = f"{short} {long}".casefold()
        for term in (*_PLACEHOLDER_TERMS, *_LEGACY_TERMS):
            if term in lowered:
                findings.append(
                    RoomProseFinding(
                        "placeholder_or_legacy_prose",
                        path,
                        f"room prose contains forbidden text {term!r}",
                        "replace the placeholder or superseded metaphysics with supported "
                        "local evidence",
                    )
                )
        for marker in _TEMPORAL_MARKERS:
            if marker in lowered:
                findings.append(
                    RoomProseFinding(
                        "temporary_state_in_static_prose",
                        path,
                        f"static room prose contains temporary-state marker {marker!r}",
                        "move current occupants, weather, doors, resources, or hazards into "
                        "structured state",
                    )
                )
        previous = seen.get(long)
        if previous is not None and previous != room_id:
            findings.append(
                RoomProseFinding(
                    "duplicate_room_prose",
                    f"{path}.long_description",
                    f"long description is unchanged from room {previous!r}",
                    "write room-specific prose or declare an explicit authored override",
                )
            )
        seen[long] = room_id
        if not presentation.get("area_name"):
            findings.append(
                RoomProseFinding(
                    "missing_area_name",
                    f"{path}.area_name",
                    "room has no area display name",
                    "inherit parent_zone or declare area_name",
                )
            )
        if not presentation.get("primary_purpose"):
            findings.append(
                RoomProseFinding(
                    "missing_primary_purpose",
                    f"{path}.primary_purpose",
                    "room has no primary purpose",
                    "declare at least one room purpose",
                )
            )
        if not _text(presentation.get("room_type")):
            findings.append(
                RoomProseFinding(
                    "missing_room_type",
                    f"{path}.room_type",
                    "room has no declared room type",
                    "declare the room variant so its prose can be reviewed against its purpose",
                )
            )
        expected_area = str(packet.parent_region).replace("_", " ").casefold()
        actual_area = str(presentation.get("area_name", "")).casefold()
        if expected_area not in actual_area and actual_area not in {
            str(packet.parent_zone).replace("_", " ").casefold(),
            expected_area,
        }:
            findings.append(
                RoomProseFinding(
                    "incorrect_region_vocabulary",
                    f"{path}.area_name",
                    f"area {presentation.get('area_name')!r} does not identify packet region "
                    f"{packet.parent_region!r}",
                    "inherit the packet region or declare an approved regional display name",
                )
            )
        points = presentation.get("points_of_interest", [])
        if not isinstance(points, list) or any(
            not isinstance(point, dict) or not point.get("id") or not point.get("display")
            for point in points
        ):
            findings.append(
                RoomProseFinding(
                    "invalid_points_of_interest",
                    f"{path}.points_of_interest",
                    "points of interest need stable id and display fields",
                    "declare structured interactive records",
                )
            )
        prose = lowered
        exits = presentation.get("exits", {})
        if isinstance(exits, dict):
            for direction in exits:
                direction_text = str(direction).casefold()
                contradiction_markers = (
                    f"no {direction_text} exit",
                    f"no way {direction_text}",
                    f"without a {direction_text} route",
                )
                if any(marker in prose for marker in contradiction_markers):
                    findings.append(
                        RoomProseFinding(
                            "prose_exit_contradiction",
                            f"{path}.long_description",
                            f"prose denies the declared {direction_text} exit",
                            "rewrite the static description to agree with the packet topology",
                        )
                    )
    if records is not None:
        for kind in ("items", "resource_nodes"):
            for record in records.get(kind, ()):
                room_id = _record_room(record)
                record_id = str(record.get("id", ""))
                if not room_id or not record_id or room_id not in presentations:
                    continue
                points = presentations[room_id].get("points_of_interest", [])
                if not any(
                    isinstance(point, dict)
                    and str(point.get("source_record", point.get("id", ""))) == record_id
                    for point in points
                ):
                    findings.append(
                        RoomProseFinding(
                            "interactive_record_not_structured",
                            f"records.{kind}[{record_id}].source_room",
                            f"interactive record {record_id!r} is not exposed as a structured "
                            "point of interest",
                            "anchor the record to its room and expose its stable id and actions",
                        )
                    )
    return tuple(findings)
