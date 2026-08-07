"""Validated prose batches for expanding a world in small authoring drops.

Room batches are a controlled content layer over the assembled graph. A batch may describe an
existing room or add a fully linked room with explicit exits, but it cannot silently create a
topology fragment. That lets an author hand the build a finished set of places at a time while the
link gate still rejects stale or incomplete geography.

The build contract is intentionally strict:

* every batch has a permanent id, sequence, and ready status;
* batches may contain any positive number of rooms;
* existing targets are overlaid; new targets must declare exits;
* a room can be authored by only one batch;
* every description is substantial prose, not the engine fallback or a level-band stub.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from kernel.world.seed import SEED_DIR, Room, SeedError, _check_label, _UniqueKeyLoader

BATCH_DIR = SEED_DIR / "room_batches"
MIN_DESCRIPTION_WORDS = 20
READY_STATUSES = {"ready", "approved"}
PRESENTATION_FIELDS = {
    "presentation_version",
    "area_name",
    "primary_purpose",
    "short_description",
    "long_description",
    "points_of_interest",
    "conditions",
    "prose_status",
    "prose_source",
    "canon_status",
    "parent_region",
    "parent_zone",
    "source_design_ids",
    "generation_seed",
    "generator_name",
    "generator_version",
    "provenance",
    "content_digest",
}


def batch_files(directory: Path | None = None) -> list[Path]:
    """Return room-batch files in stable sequence/name order."""
    where = directory if directory is not None else BATCH_DIR
    return (
        sorted(where.glob("*.yaml"), key=lambda path: (_batch_sequence(path), path.name))
        if where.is_dir()
        else []
    )


def _batch_sequence(path: Path) -> int:
    """Read the declared sequence for ordering, leaving full validation to ``_load``."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    batch = raw.get("batch", {}) if isinstance(raw, dict) else {}
    sequence = batch.get("sequence") if isinstance(batch, dict) else None
    return sequence if isinstance(sequence, int) and not isinstance(sequence, bool) else 2**31


def _load(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(data, dict):
        raise SeedError(f"room batch {path.name!r} must be a mapping")
    batch = data.get("batch")
    rooms = data.get("rooms")
    if not isinstance(batch, dict) or not isinstance(rooms, dict) or not rooms:
        raise SeedError(f"room batch {path.name!r} needs non-empty 'batch' and 'rooms' sections")
    batch_id = batch.get("id")
    if not isinstance(batch_id, str) or not batch_id.strip():
        raise SeedError(f"room batch {path.name!r} needs a permanent batch.id")
    sequence = batch.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise SeedError(f"room batch {batch_id!r}: batch.sequence must be a positive integer")
    status = batch.get("status")
    if status not in READY_STATUSES:
        raise SeedError(
            f"room batch {batch_id!r}: status must be one of {sorted(READY_STATUSES)} "
            "before it can enter the world"
        )
    declared_size = batch.get("size", len(rooms))
    if declared_size != len(rooms):
        raise SeedError(
            f"room batch {batch_id!r}: declared size {declared_size} does not match "
            f"{len(rooms)} room records"
        )
    final = batch.get("final", False)
    if not isinstance(final, bool):
        raise SeedError(f"room batch {batch_id!r}: batch.final must be true or false")
    for label, record in rooms.items():
        _check_label(label, "Room batch target")
        if not isinstance(record, dict):
            raise SeedError(f"room batch {batch_id!r} room {label!r} must be a mapping")
        description = record.get("desc")
        if not isinstance(description, str) or len(description.split()) < MIN_DESCRIPTION_WORDS:
            raise SeedError(
                f"room batch {batch_id!r} room {label!r}: desc must contain at least "
                f"{MIN_DESCRIPTION_WORDS} words"
            )
        if "name" in record and not isinstance(record["name"], str):
            raise SeedError(f"room batch {batch_id!r} room {label!r}: name must be text")
        if "replace" in record and not isinstance(record["replace"], bool):
            raise SeedError(
                f"room batch {batch_id!r} room {label!r}: replace must be true or false"
            )
        exits = record.get("exits")
        if exits is not None and (
            not isinstance(exits, dict)
            or not all(
                isinstance(direction, str) and isinstance(destination, str)
                for direction, destination in exits.items()
            )
        ):
            raise SeedError(
                f"room batch {batch_id!r} room {label!r}: exits must be a "
                "direction-to-label mapping"
            )
        for field in ("occupants", "objects", "occupant_refs", "object_refs", "tags"):
            values = record.get(field)
            if values is not None and (
                not isinstance(values, list)
                or not all(isinstance(value, str) and value.strip() for value in values)
            ):
                raise SeedError(
                    f"room batch {batch_id!r} room {label!r}: {field} must be a list of text"
                )
        if batch.get("presentation_spec") == "aethryn-room-v1":
            required = (
                "name",
                "presentation_version",
                "area_name",
                "room_type",
                "primary_purpose",
                "short_description",
                "long_description",
                "points_of_interest",
                "conditions",
                "prose_status",
                "prose_source",
                "canon_status",
                "parent_region",
                "parent_zone",
                "source_design_ids",
                "generation_seed",
                "generator_name",
                "generator_version",
                "provenance",
                "content_digest",
                "exits",
            )
            missing = [field for field in required if field not in record]
            if missing:
                raise SeedError(
                    f"room batch {batch_id!r} room {label!r}: missing presentation fields "
                    f"{', '.join(missing)}; compile the packet through the Aethryn room prose pass"
                )
            if record.get("prose_status") not in {"GENERATED_LOCAL", "AUTHORED_LOCAL"}:
                raise SeedError(
                    f"room batch {batch_id!r} room {label!r}: generated prose status must be "
                    "GENERATED_LOCAL or AUTHORED_LOCAL; do not promote generated prose into canon"
                )
            if record.get("canon_status") not in {
                "CANON_LOCKED",
                "CANON_WORKING",
                "AUTHORED_LOCAL",
                "GENERATED_LOCAL",
                "RUMOR",
            }:
                raise SeedError(
                    f"room batch {batch_id!r} room {label!r}: canon_status is not a valid "
                    "authority-ladder value; use the packet's inherited status"
                )
            for field in ("area_name", "short_description", "long_description", "content_digest"):
                if not isinstance(record.get(field), str) or not record[field].strip():
                    raise SeedError(
                        f"room batch {batch_id!r} room {label!r}: {field} must be non-empty text"
                    )
            if record.get("presentation_version") != "aethryn-room-v1":
                raise SeedError(
                    f"room batch {batch_id!r} room {label!r}: presentation_version must be "
                    "aethryn-room-v1"
                )
            if not isinstance(record.get("exits"), dict):
                raise SeedError(
                    f"room batch {batch_id!r} room {label!r}: exits must be a direction mapping"
                )
            if (
                not isinstance(record.get("source_design_ids"), list)
                or not record["source_design_ids"]
            ):
                raise SeedError(
                    f"room batch {batch_id!r} room {label!r}: source_design_ids must be non-empty"
                )
            if not isinstance(record.get("generation_seed"), int) or isinstance(
                record["generation_seed"], bool
            ):
                raise SeedError(
                    f"room batch {batch_id!r} room {label!r}: generation_seed must be an integer"
                )
            for field in ("parent_region", "parent_zone", "generator_name", "generator_version"):
                if not isinstance(record.get(field), str) or not record[field].strip():
                    raise SeedError(
                        f"room batch {batch_id!r} room {label!r}: {field} must be non-empty text"
                    )
            if not isinstance(record.get("primary_purpose"), list) or not record["primary_purpose"]:
                raise SeedError(
                    f"room batch {batch_id!r} room {label!r}: primary_purpose must be a "
                    "non-empty list"
                )
            points = record.get("points_of_interest")
            if not isinstance(points, list):
                raise SeedError(
                    f"room batch {batch_id!r} room {label!r}: points_of_interest must be a list"
                )
            for point in points:
                if not isinstance(point, dict) or not point.get("id") or not point.get("display"):
                    raise SeedError(
                        f"room batch {batch_id!r} room {label!r}: every point_of_interest "
                        "needs id and display"
                    )
            if not isinstance(record.get("conditions"), list):
                raise SeedError(
                    f"room batch {batch_id!r} room {label!r}: conditions must be a list"
                )
            if not isinstance(record.get("provenance"), dict):
                raise SeedError(
                    f"room batch {batch_id!r} room {label!r}: provenance must be a mapping"
                )
        forbidden = (
            set(record)
            - {
                "desc",
                "name",
                "replace",
                "room_type",
                "tags",
                "notes",
                "exits",
                "occupants",
                "objects",
                "occupant_refs",
                "object_refs",
                "population_refs",
                "crowd_refs",
                "ambient_evidence_refs",
            }
            - PRESENTATION_FIELDS
        )
        if forbidden:
            fields = ", ".join(sorted(forbidden))
            raise SeedError(
                f"room batch {batch_id!r} room {label!r}: unsupported fields {fields}; "
                "room batches author prose only"
            )
    return batch, rooms


def _keywords(text: str) -> list[str]:
    words = [word for word in text.lower().replace("'", "").split() if word.isalnum()]
    return words or ["object"]


def _visible_name(line: str) -> str:
    """Turn an editorial visible-object sentence into a compact display name."""
    text = line.strip().rstrip(".")
    verbs = (
        " arranges ",
        " waits ",
        " checks ",
        " rests ",
        " records ",
        " hangs ",
        " leans ",
        " lies ",
        " cools ",
        " sorts ",
        " polishes ",
        " examines ",
        " pushes ",
        " studies ",
        " creaks ",
        " guides ",
        " repairs ",
        " follows ",
        " inspects ",
        " calls ",
        " argues ",
        " displays ",
        " stands ",
        " turns ",
        " carries ",
        " grazes ",
        " spans ",
        " points ",
        " holds ",
        " marks ",
        " runs ",
        " occupies ",
        " waits ",
    )
    for verb in verbs:
        if verb in text:
            return text.split(verb, 1)[0]
    return text


def apply_room_batches(
    world: dict[str, Room],
    npcs: dict[str, dict[str, Any]] | None = None,
    items: dict[str, dict[str, Any]] | None = None,
    directory: Path | None = None,
) -> dict[str, int]:
    """Validate and apply every ready prose batch to an assembled world.

    Existing rooms receive prose and optional metadata. New rooms must provide explicit exits;
    those rooms are added before exit validation so a batch can describe a connected pocket of the
    world in one file. Optional occupant/object lists become peaceful NPCs and visible item records.
    """
    seen_ids: set[str] = set()
    seen_sequences: set[int] = set()
    seen_rooms: set[str] = set()
    pending: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for path in batch_files(directory):
        batch, records = _load(path)
        batch_id = str(batch["id"])
        sequence = int(batch["sequence"])
        if batch_id in seen_ids:
            raise SeedError(f"Duplicate room batch id {batch_id!r}")
        if sequence in seen_sequences:
            raise SeedError(f"Duplicate room batch sequence {sequence} (batch {batch_id!r})")
        seen_ids.add(batch_id)
        seen_sequences.add(sequence)
        for label, record in records.items():
            if label in seen_rooms:
                if not record.get("replace", False):
                    raise SeedError(f"Room {label!r} is authored by more than one room batch")
            else:
                seen_rooms.add(label)
            pending.append((label, record, batch))

    # First install the complete room set, then check exits. A batch can therefore link two new
    # rooms regardless of their order in the YAML mapping.
    for label, record, batch in pending:
        if label not in world:
            exits = record.get("exits")
            if not isinstance(exits, dict) or not exits:
                raise SeedError(
                    f"room batch {batch['id']!r} adds room {label!r} without exits; "
                    "new rooms must declare their topology"
                )
            world[label] = Room(
                name=str(record.get("name", label.replace("_", " ").title())),
                desc=str(record["desc"]),
                exits=dict(exits),
            )
        else:
            world[label]["desc"] = str(record["desc"])
            if "name" in record:
                world[label]["name"] = str(record["name"])
            # A prose batch may repeat exits for editorial context, but topology belongs to the
            # assembled world unless the record explicitly declares a replacement. This prevents
            # decorative drop routes from erasing named canonical connections.
            if record.get("replace") and "exits" in record:
                world[label]["exits"] = dict(record["exits"])
        if "room_type" in record:
            world[label]["room_type"] = str(record["room_type"])
        if "tags" in record:
            world[label]["tags"] = list(record["tags"])
        for field in PRESENTATION_FIELDS:
            if field in record:
                cast(Any, world[label])[field] = record[field]

    for label, record, batch in pending:
        for direction, destination in world[label]["exits"].items():
            if destination not in world:
                raise SeedError(
                    f"room batch {batch['id']!r} room {label!r} exit {direction!r} -> "
                    f"{destination!r} targets an unknown room"
                )
        if npcs is not None:
            for index, occupant in enumerate(record.get("occupants", []), start=1):
                npc_label = f"{batch['id']}_{label}_occupant_{index}"
                display_name = _visible_name(occupant)
                if npc_label in npcs:
                    existing = npcs[npc_label]
                    if existing.get("location") == label and existing.get("name") in {
                        occupant,
                        display_name,
                    }:
                        existing["name"] = display_name
                        existing["keywords"] = _keywords(display_name)
                        existing["dialogue"] = [occupant]
                        continue
                    raise SeedError(f"room batch occupant label {npc_label!r} already exists")
                npcs[npc_label] = {
                    "name": display_name,
                    "keywords": _keywords(display_name),
                    "location": label,
                    "dialogue": [occupant],
                    "next_line": 0,
                    "hp": 0,
                    "hp_now": 0,
                    "xp": 0,
                    "atk": 0,
                    "aggressive": False,
                }
        if items is not None:
            for index, object_name in enumerate(record.get("objects", []), start=1):
                item_label = f"{batch['id']}_{label}_object_{index}"
                display_name = _visible_name(object_name)
                if item_label in items:
                    existing = items[item_label]
                    if existing.get("location") == f"room:{label}" and existing.get("name") in {
                        object_name,
                        display_name,
                    }:
                        existing["name"] = display_name
                        existing["keywords"] = _keywords(display_name)
                        existing["lore"] = object_name
                        continue
                    raise SeedError(f"room batch object label {item_label!r} already exists")
                items[item_label] = {
                    "name": display_name,
                    "keywords": _keywords(display_name),
                    "location": f"room:{label}",
                    "slot": "",
                    "mods": {},
                    "lore": object_name,
                }
    return {"batches": len(seen_ids), "rooms": len(pending)}
