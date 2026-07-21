"""CARD: items -- objects, containment, take/drop/inventory.

Design rule: an item stores its own location. Nothing else does.
Locations are tagged strings: "room:library" or "player".
Items are born from the seed (seeds/first-forge/items.yaml).
Functions RETURN text; the game loop decides what to print.
"""

import copy

from parts.seed import SEED_DIR, Item, load_items

ITEMS: dict[str, Item] = load_items(SEED_DIR / "items.yaml")

# Prototypes: the seed templates, captured pristine at load. A seed label is a PROTOTYPE (a
# template); runtime items are INSTANCES cloned from it. Keeping the templates apart from the
# live instances lets clone() mint a fresh one even after every instance has left play -- the
# spawn primitive repop, loot, and @sg all build on. Instancing generalizes what @sg already
# did (mint a unique label); a seed-placed item is simply its own first instance.
PROTOTYPES: dict[str, Item] = {label: copy.deepcopy(item) for label, item in ITEMS.items()}


class ItemError(ValueError):
    """A bad item operation (e.g. cloning an unknown prototype): fail loud."""


def prototype_of(iid: str) -> str:
    """The prototype label an item is an instance of (its own id if it declares none). Callers
    match items by prototype -- a door's key, a quest's pickup -- so a clone counts as the real
    thing."""
    item = ITEMS.get(iid)
    return item.get("prototype", iid) if item else iid


def _mint_instance_id(prototype: str) -> str:
    """A fresh, unique instance id for a prototype: the clean label for the first, then
    `<prototype>_2`, `_3`, ... so cloning a prototype twice yields two distinct instances."""
    if prototype not in ITEMS:
        return prototype  # the first instance keeps the clean label
    n = 2
    while f"{prototype}_{n}" in ITEMS:
        n += 1
    return f"{prototype}_{n}"


def clone(prototype: str, location: str) -> str:
    """Mint a new INSTANCE of a prototype item at a location; returns its instance id. This is the
    spawn primitive: repop, loot drops, and system generation all place fresh instances this way.
    `location` may be a room label, a tagged `room:<label>`, or `player`. Raises ItemError on an
    unknown prototype (fail loud, never spawn a ghost)."""
    template = PROTOTYPES.get(prototype)
    if template is None:
        raise ItemError(f"unknown item prototype {prototype!r}; cannot clone it")
    iid = _mint_instance_id(prototype)
    tagged = "player" if location == "player" else f"room:{location.removeprefix('room:')}"
    ITEMS[iid] = Item(
        name=template["name"],
        keywords=list(template["keywords"]),
        location=tagged,
        slot=template["slot"],
        mods=dict(template["mods"]),
        prototype=prototype,
    )
    return iid


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
