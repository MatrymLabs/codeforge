#!/usr/bin/env python3
"""Create a draft template for the next unclaimed room prose batch."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from kernel.world.room_batches import BATCH_DIR, batch_files
from kernel.world.seed import _UniqueKeyLoader
from kernel.world.world import WORLD


def _claimed_rooms() -> set[str]:
    claimed: set[str] = set()
    for path in batch_files():
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
        if isinstance(data, dict) and isinstance(data.get("rooms"), dict):
            claimed.update(str(label) for label in data["rooms"])
    return claimed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", type=int, required=True, help="permanent batch sequence")
    parser.add_argument("--count", type=int, default=100, help="rooms to include")
    parser.add_argument("--final", action="store_true", help="mark the batch as the final drop")
    parser.add_argument(
        "--output",
        type=Path,
        help="draft path (default: room_batches/incoming/batch_<sequence>.yaml)",
    )
    args = parser.parse_args()
    if args.sequence < 1:
        parser.error("--sequence must be positive")
    if args.count < 1:
        parser.error("--count must be positive")

    claimed = _claimed_rooms()
    available = [label for label in WORLD if label not in claimed]
    selected = available[: args.count]
    if len(selected) < args.count:
        parser.error(f"only {len(selected)} unclaimed rooms remain in the assembled world")
    output = args.output or BATCH_DIR / "incoming" / f"batch_{args.sequence:04d}.yaml"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "batch": {
            "id": f"aethryn_rooms_{args.sequence:04d}",
            "sequence": args.sequence,
            "status": "draft",
            "size": len(selected),
            "final": args.final,
        },
        "rooms": {
            label: {
                "desc": "REPLACE THIS DRAFT WITH THE FINISHED ROOM DESCRIPTION.",
                "tags": [],
                "notes": "",
            }
            for label in selected
        },
    }
    output.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    print(f"draft room batch: {output}")
    print(f"  sequence: {args.sequence}")
    print(f"  rooms: {len(selected)}")
    print("  next_step: edit descriptions, set status: ready, then move the file to room_batches/")


if __name__ == "__main__":
    main()
