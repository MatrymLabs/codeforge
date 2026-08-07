#!/usr/bin/env python3
"""Compile the current Aethryn editorial room drops into anchored room batches.

The source manuscripts provide room prose and visible exit directions, but not canonical room IDs
or destination IDs. This adapter adds a zone namespace, preserves the importer’s ordered-route
inference, and installs one explicit link from an existing Aethryn anchor into each drop. The
result remains ordinary room-batch YAML and crosses the same runtime validation gate as every
other authored room.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from tools.import_mud_batch import compile_batches, parse_text


def _anchor_record(
    world: Mapping[str, Mapping[str, Any]],
    *,
    anchor_room: str,
    anchor_exit: str,
    first_room: str,
) -> dict[str, Any]:
    """Copy one existing room and add the reversible outbound drop link."""
    if anchor_room not in world:
        raise ValueError(f"anchor room {anchor_room!r} is not in the assembled Aethryn world")
    anchor = world[anchor_room]
    exits = dict(anchor["exits"])
    if anchor_exit in exits:
        raise ValueError(
            f"anchor room {anchor_room!r} already uses exit {anchor_exit!r} "
            f"for {exits[anchor_exit]!r}"
        )
    exits[anchor_exit] = first_room
    return {
        "name": anchor["name"],
        "desc": anchor["desc"],
        "exits": exits,
        "replace": True,
        "tags": ["aethryn", "room_drop_anchor"],
        "notes": f"Adds {anchor_exit} -> {first_room} to enter the imported drop.",
    }


def build_batch(
    source: Path,
    *,
    sequence: int,
    batch_id: str,
    label_prefix: str,
    tags: list[str],
    world: Mapping[str, Mapping[str, Any]],
    anchor_room: str,
    anchor_exit: str,
) -> dict[str, Any]:
    records = parse_text(source.read_text(encoding="utf-8"))
    batch = compile_batches(
        records,
        sequence,
        label_prefix=label_prefix,
        tags=tags,
    )[0]
    first_room = next(iter(batch["rooms"]))
    batch["rooms"][first_room]["exits"]["out"] = anchor_room
    batch["rooms"][anchor_room] = _anchor_record(
        world,
        anchor_room=anchor_room,
        anchor_exit=anchor_exit,
        first_room=first_room,
    )
    batch["batch"].update(
        {
            "id": batch_id,
            "size": len(batch["rooms"]),
            "source": source.name,
            "imported_rooms": len(records),
            "link_inference": "ordered_route",
            "anchor_room": anchor_room,
            "anchor_exit": anchor_exit,
        }
    )
    return batch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--sequence", type=int, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--label-prefix", required=True)
    parser.add_argument("--anchor-room", required=True)
    parser.add_argument("--anchor-exit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tag", action="append", required=True)
    args = parser.parse_args()

    from kernel.world.world import WORLD

    batch = build_batch(
        args.source,
        sequence=args.sequence,
        batch_id=args.batch_id,
        label_prefix=args.label_prefix,
        tags=args.tag,
        world=WORLD,
        anchor_room=args.anchor_room,
        anchor_exit=args.anchor_exit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(batch, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    print(
        f"compiled {args.output}: imported={batch['batch']['imported_rooms']} "
        f"batch_records={batch['batch']['size']}"
    )


if __name__ == "__main__":
    main()
