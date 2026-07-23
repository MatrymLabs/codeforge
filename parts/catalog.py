"""CARD: catalog -- the filing system. List world components by number.

Numbers are FILING AIDS: generated display ordinals, alphabetical by
label, stable for any given world snapshot. Labels are IDENTITY:
exits, saves, and code link by label, never by number.

This is the first World Console component: an admin view that
inspects world state without mutating it.
"""

from parts.world.items import ITEMS
from parts.world.npcs import NPCS, Npc
from parts.world.seed import Item, Room, load_rooms
from parts.world.session import sentence_case
from parts.world.world import SEED_PATH


def _filed_index(
    label_head: str, name_head: str, tail_head: str, rows: list[tuple[str, str, str]]
) -> list[str]:
    """Render a numbered index, sizing each column to its widest cell. Labels are DATA (a seed
    may name a room 'cinderhearth_square'), so a fixed column width once collided the LABEL and
    NAME columns on longer worlds; the widths are computed, never assumed."""
    num_w = max(len("#"), len(str(len(rows)))) + 2
    label_w = max(len(label_head), *(len(r[0]) for r in rows)) + 1 if rows else len(label_head) + 1
    name_w = max(len(name_head), *(len(r[1]) for r in rows)) + 1 if rows else len(name_head) + 1
    header = f"{'#':<{num_w}}{label_head:<{label_w}}{name_head:<{name_w}}{tail_head}"
    lines = [header, "-" * len(header)]
    for number, (label, name, tail) in enumerate(rows, start=1):
        lines.append(f"{number:<{num_w}}{label:<{label_w}}{name:<{name_w}}{tail}")
    return lines


def room_catalog(rooms: dict[str, Room] | None = None) -> str:
    """Return the numbered room index as display text."""
    if rooms is None:
        rooms = load_rooms(SEED_PATH)
    rows = [
        (
            label,
            room["name"],
            ", ".join(f"{d}->{dest}" for d, dest in room["exits"].items()) or "(none)",
        )
        for label, room in sorted(rooms.items())
    ]
    lines = _filed_index("LABEL", "NAME", "EXITS", rows)
    lines.append(f"\n{len(rooms)} rooms filed.")
    return "\n".join(lines)


def item_catalog(items: dict[str, Item] | None = None) -> str:
    """Return the numbered item index as display text."""
    if items is None:
        items = ITEMS
    rows = [
        (label, sentence_case(item["name"]), item["location"].removeprefix("room:"))
        for label, item in sorted(items.items())
    ]
    lines = _filed_index("LABEL", "NAME", "WHERE", rows)
    lines.append(f"\n{len(items)} items filed.")
    return "\n".join(lines)


def npc_catalog(npcs: dict[str, Npc] | None = None) -> str:
    """Return the numbered NPC index as display text."""
    if npcs is None:
        npcs = NPCS
    rows = [
        (label, sentence_case(npc["name"]), npc["location"]) for label, npc in sorted(npcs.items())
    ]
    lines = _filed_index("LABEL", "NAME", "ROOM", rows)
    lines.append(f"\n{len(npcs)} npcs filed.")
    return "\n".join(lines)


if __name__ == "__main__":
    print("ROOMS")
    print(room_catalog())
    print()
    print("ITEMS")
    print(item_catalog())
    print()
    print("NPCS")
    print(npc_catalog())
