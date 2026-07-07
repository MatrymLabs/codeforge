"""CARD: catalog -- the filing system. List world components by number.

Numbers are FILING AIDS: generated display ordinals, alphabetical by
label, stable for any given world snapshot. Labels are IDENTITY:
exits, saves, and code link by label, never by number.

This is the first World Console component: an admin view that
inspects world state without mutating it.
"""

from parts.npcs import NPCS, Npc
from parts.seed import Room, load_rooms
from parts.world import SEED_PATH


def room_catalog(rooms: dict[str, Room] | None = None) -> str:
    """Return the numbered room index as display text."""
    if rooms is None:
        rooms = load_rooms(SEED_PATH)
    header = f"{'#':<4}{'LABEL':<14}{'NAME':<26}EXITS"
    lines = [header, "-" * len(header)]
    for number, (label, room) in enumerate(sorted(rooms.items()), start=1):
        exits = ", ".join(f"{d}->{dest}" for d, dest in room["exits"].items()) or "(none)"
        lines.append(f"{number:<4}{label:<14}{room['name']:<26}{exits}")
    lines.append(f"\n{len(rooms)} rooms filed.")
    return "\n".join(lines)


def npc_catalog(npcs: dict[str, Npc] | None = None) -> str:
    """Return the numbered NPC index as display text."""
    if npcs is None:
        npcs = NPCS
    header = f"{'#':<4}{'LABEL':<14}{'NAME':<26}ROOM"
    lines = [header, "-" * len(header)]
    for number, (label, npc) in enumerate(sorted(npcs.items()), start=1):
        lines.append(f"{number:<4}{label:<14}{npc['name'].title():<26}{npc['location']}")
    lines.append(f"\n{len(npcs)} npcs filed.")
    return "\n".join(lines)


if __name__ == "__main__":
    print("ROOMS")
    print(room_catalog())
    print()
    print("NPCS")
    print(npc_catalog())
