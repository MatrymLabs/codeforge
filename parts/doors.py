"""CARD: doors -- lockable barriers between rooms.

A door is world state, not text. It blocks one exit until unlocked.
MUD-IL shape: verb=unlock, direct_object=door, instrument=key.

Note: we import the items MODULE, not its globals, so tests that
swap items.ITEMS still affect us. Import modules, not mutable state.
"""

from typing import TypedDict

from parts import items


class Door(TypedDict):
    """The shape every door must have."""

    name: str
    keywords: list[str]
    blocks: tuple[str, str]  # (room_id, direction) -- mypy enforces the pair
    locked: bool
    key_id: str


DOORS: dict[str, Door] = {
    "oak_door": {
        "name": "the oak door",
        "keywords": ["door", "oak", "oak door"],
        "blocks": ("library", "north"),
        "locked": True,
        "key_id": "copper_key",
    },
}


def door_blocking(room_id: str, direction: str) -> str | None:
    """Return the id of a LOCKED door blocking this exit, if any."""
    for did, door in DOORS.items():
        if door["blocks"] == (room_id, direction) and door["locked"]:
            return did
    return None


def find_door(word: str, room_id: str) -> str | None:
    """Match a player's word against doors in this room."""
    for did, door in DOORS.items():
        if door["blocks"][0] == room_id and word in door["keywords"]:
            return did
    return None


def unlock(door_word: str, key_word: str, room_id: str) -> str:
    did = find_door(door_word, room_id)
    if did is None:
        return "You don't see that here."
    door = DOORS[did]
    if not door["locked"]:
        return f"{door['name'].capitalize()} is already unlocked."

    key_iid = items.find_item(key_word, "player")
    if key_iid is None:
        return "You aren't carrying that."
    if key_iid != door["key_id"]:
        return f"{items.ITEMS[key_iid]['name'].capitalize()} doesn't fit the lock."

    door["locked"] = False
    return f"You unlock {door['name']} with {items.ITEMS[key_iid]['name']}."
