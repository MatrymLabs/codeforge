#!/usr/bin/env python3
"""Validate and report the ready room-prose batches for the selected seed."""

from __future__ import annotations

from kernel.world.room_batches import apply_room_batches
from kernel.world.world import ITEMS, NPCS, WORLD


def main() -> None:
    report = apply_room_batches(WORLD, NPCS, ITEMS)
    print("room prose batches: valid")
    print(f"  batches: {report['batches']}")
    print(f"  rooms: {report['rooms']}")
    print(f"  assembled_world_rooms: {len(WORLD)}")


if __name__ == "__main__":
    main()
