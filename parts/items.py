"""CARD: items -- objects, containment, take/drop/inventory.

Design rule: an item stores its own location. Nothing else does.
Locations are tagged strings: "room:library" or "player".
Items are born from the seed (seeds/first-forge/items.yaml).
Functions RETURN text; the game loop decides what to print.
"""

from parts.seed import SEED_DIR, Item, load_items

ITEMS: dict[str, Item] = load_items(SEED_DIR / "items.yaml")


def items_in(location: str) -> list[str]:
    """All item ids currently at a location. Containment is a query."""
    return [iid for iid, item in ITEMS.items() if item["location"] == location]


def trace_item(word: str, location: str) -> str | None:
    """Match a player's word against keywords of items at a location."""
    for iid in items_in(location):
        if word in ITEMS[iid]["keywords"]:
            return iid
    return None


def take(word: str, room_id: str) -> str:
    iid = trace_item(word, f"room:{room_id}")
    if iid is None:
        return "You don't see that here."
    ITEMS[iid]["location"] = "player"
    return f"You take {ITEMS[iid]['name']}."


def drop(word: str, room_id: str) -> str:
    iid = trace_item(word, "player")
    if iid is None:
        return "You aren't carrying that."
    ITEMS[iid]["location"] = f"room:{room_id}"
    return f"You drop {ITEMS[iid]['name']}."


def inventory_text() -> str:
    carried = items_in("player")
    if not carried:
        return "You are carrying nothing."
    lines = "\n".join(f"  {ITEMS[iid]['name']}" for iid in carried)
    return f"You are carrying:\n{lines}"


def room_items_text(room_id: str) -> str:
    """Extra line(s) for room rendering. Empty string if nothing here."""
    here = items_in(f"room:{room_id}")
    if not here:
        return ""
    return "\n".join(f"You see {ITEMS[iid]['name']} here." for iid in here)
