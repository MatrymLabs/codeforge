#!/usr/bin/env python3
"""Compile classic plain-text MUD room drops into validated Aethryn batch YAML.

The editorial source stays human-readable: title, bracketed room type, prose paragraphs, three
visible-content lines, and ``Obvious exits``. Since that format names directions but not destination
IDs, this compiler makes the smallest deterministic assumption available: the drop's room order is
a continuous route, and each declared direction is wired to a nearby room along that route. The
compiled YAML carries ``link_inference: ordered_route`` in its batch metadata for later cartography.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml

_SEPARATOR = re.compile(r"^[=\-]{8,}$")
_EXIT_PREFIX = "Obvious exits:"
_CONTENT_WORDS = (
    "acolyte",
    "apprentice",
    "boy",
    "child",
    "clerk",
    "dog",
    "farmer",
    "ferryman",
    "fisher",
    "guard",
    "herbalist",
    "keeper",
    "merchant",
    "miller",
    "patrol",
    "recruit",
    "ranger",
    "seller",
    "shepherd",
    "smith",
    "tanner",
    "trader",
    "vendor",
    "watchman",
    "woman",
    "man",
    "worker",
    "boatman",
    "carter",
    "stablehand",
    "innkeeper",
    "musician",
)


def _label(title: str) -> str:
    value = re.sub(r"\([^)]*\)", "", title.casefold())
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "room"


def _visible_name(line: str) -> str:
    return line.rstrip(".").strip()


def _split_visible(lines: list[str]) -> tuple[list[str], list[str]]:
    occupants: list[str] = []
    objects: list[str] = []
    for line in lines:
        lower = line.casefold()
        if any(word in lower for word in _CONTENT_WORDS):
            occupants.append(_visible_name(line))
        else:
            objects.append(_visible_name(line))
    return occupants, objects


def parse_text(text: str) -> list[dict[str, Any]]:
    lines = [line.rstrip() for line in text.splitlines()]
    records: list[dict[str, Any]] = []
    index = 0
    while index < len(lines) - 1:
        title = lines[index].strip()
        room_type = lines[index + 1].strip()
        if not title or not room_type.startswith("[") or not room_type.endswith("]"):
            index += 1
            continue
        index += 2
        body: list[str] = []
        while index < len(lines) and not lines[index].strip().startswith(_EXIT_PREFIX):
            if not _SEPARATOR.match(lines[index].strip()):
                body.append(lines[index].strip())
            index += 1
        if index >= len(lines):
            raise ValueError(f"room {title!r} is missing an Obvious exits line")
        exits = [value.strip().rstrip(".") for value in lines[index].split(":", 1)[1].split(",")]
        exits = [value for value in exits if value]
        index += 1
        while index < len(lines) and (
            not lines[index].strip() or _SEPARATOR.match(lines[index].strip())
        ):
            index += 1
        visible = [value for value in body if value]
        if len(visible) < 4:
            raise ValueError(f"room {title!r} needs prose plus three visible-content lines")
        prose = "\n\n".join(visible[:-3])
        occupants, objects = _split_visible(visible[-3:])
        records.append(
            {
                "label": _label(title),
                "name": title,
                "room_type": room_type[1:-1],
                "desc": prose,
                "source_exits": exits,
                "occupants": occupants,
                "objects": objects,
            }
        )
    if not records:
        raise ValueError("no room blocks found")
    return records


def _wire(records: list[dict[str, Any]]) -> None:
    """Turn directional exit lists into one deterministic connected route."""
    labels = [record["label"] for record in records]
    for index, record in enumerate(records):
        source = record.pop("source_exits")
        if not source:
            source = ["east"]
        targets: dict[str, str] = {}
        for direction in source:
            if direction in {"west", "south", "southwest", "northwest", "out", "up"}:
                target_index = max(0, index - 1)
            else:
                target_index = min(len(labels) - 1, index + 1)
            targets[direction] = labels[target_index]
        if index < len(labels) - 1:
            forward = next(
                (
                    direction
                    for direction in source
                    if direction not in {"west", "south", "out", "up"}
                ),
                source[0],
            )
            targets[forward] = labels[index + 1]
        record["exits"] = targets


def compile_batches(
    records: list[dict[str, Any]],
    sequence: int,
    *,
    label_prefix: str = "",
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Compile parsed room records with an optional stable namespace and tag set."""
    if label_prefix:
        prefix = _label(label_prefix)
        for record in records:
            record["label"] = f"{prefix}_{record['label']}"
    _wire(records)
    room_tags = tags if tags is not None else ["veridia", "imported_text_drop"]
    rooms: dict[str, dict[str, Any]] = {}
    for record in records:
        label = record["label"]
        rooms[label] = {
            "name": record["name"],
            "room_type": record["room_type"],
            "desc": record["desc"],
            "exits": record["exits"],
            "occupants": record["occupants"],
            "objects": record["objects"],
            "replace": True,
            "tags": list(room_tags),
        }
    return [
        {
            "batch": {
                "id": f"aethryn_text_drop_{sequence:04d}",
                "sequence": sequence,
                "status": "ready",
                "size": len(rooms),
                "final": True,
                "link_inference": "ordered_route",
            },
            "rooms": rooms,
        }
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--sequence", type=int, default=2)
    parser.add_argument("--batch-id", help="override the generated batch identifier")
    parser.add_argument("--tag", action="append", default=[], help="room tag to add")
    parser.add_argument("--output-name", help="output YAML filename")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    records = parse_text(args.source.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for batch in compile_batches(records, args.sequence):
        if args.batch_id:
            batch["batch"]["id"] = args.batch_id
        if args.tag:
            for room in batch["rooms"].values():
                room["tags"] = args.tag
        sequence = batch["batch"]["sequence"]
        filename = args.output_name or f"text_drop_{sequence:04d}.yaml"
        path = args.output_dir / filename
        path.write_text(
            yaml.safe_dump(batch, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        print(f"compiled {path}: {batch['batch']['size']} rooms")
    print(f"total rooms: {len(records)}")


if __name__ == "__main__":
    main()
