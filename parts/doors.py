"""CARD: doors -- lockable barriers between rooms.

A door is world state, not text. It blocks one exit until unlocked.
MUD-IL shape: verb=unlock, direct_object=door, instrument=key.

A door is the smallest finite-state machine: `locked --unlock[key_fits]--> open`. Its
canonical fact stays the `locked` bool; the state label is *derived* from it (ADR-0002),
the machine decides whether the move is legal (ADR-0004), and this module applies the
effect. It is the proof that any lifecycle in the world can compose onto `parts/statemachine`.

Note: we import the items MODULE, not its globals, so tests that
swap items.ITEMS still affect us. Import modules, not mutable state.
"""

from collections.abc import Mapping
from typing import TypedDict, cast

from parts import items
from parts.statemachine import Guard, Refusal, Transition, advance, build


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


def barred_door_for(room_id: str, direction: str) -> str | None:
    """Return the id of a LOCKED door blocking this exit, if any."""
    for did, door in DOORS.items():
        if door["blocks"] == (room_id, direction) and door["locked"]:
            return did
    return None


def trace_door(word: str, room_id: str) -> str | None:
    """Match a player's word against doors in this room."""
    for did, door in DOORS.items():
        if door["blocks"][0] == room_id and word in door["keywords"]:
            return did
    return None


# A door is a two-state machine. The state label is derived from the canonical `locked`
# bool; the machine owns legality (you cannot unlock an open door), the guard owns the
# key check, and this module applies the "open" effect. State is data; only we mutate.
_LOCKED = "locked"
_OPEN = "open"


def _key_fits(ctx: Mapping[str, object]) -> str | None:
    """Guard for the unlock edge: is the actor carrying the key that fits this door?"""
    door = cast(Door, ctx["door"])
    key_word = cast(str, ctx["key_word"])
    key_iid = items.trace_item(key_word, "player")
    if key_iid is None:
        return "You aren't carrying that."
    if key_iid != door["key_id"]:
        return f"{items.ITEMS[key_iid]['name'].capitalize()} doesn't fit the lock."
    return None


_DOOR_MACHINE = build(
    states={_LOCKED, _OPEN},
    start=_LOCKED,
    transitions=[Transition(_LOCKED, "unlock", _OPEN, guard="key_fits", effect="open")],
)
_DOOR_GUARDS: dict[str, Guard] = {"key_fits": _key_fits}


def _door_state(door: Door) -> str:
    """Derive the machine state from the canonical fact (ADR-0002: derive, don't store)."""
    return _LOCKED if door["locked"] else _OPEN


def unlock(door_word: str, key_word: str, room_id: str) -> str:
    did = trace_door(door_word, room_id)
    if did is None:
        return "You don't see that here."
    door = DOORS[did]
    ctx: dict[str, object] = {"door": door, "key_word": key_word, "room_id": room_id}
    outcome = advance(_DOOR_MACHINE, _door_state(door), "unlock", ctx, _DOOR_GUARDS)
    if isinstance(outcome, Refusal):
        # An open door has no unlock edge (no_transition); a locked door refuses via the guard.
        if not door["locked"]:
            return f"{door['name'].capitalize()} is already unlocked."
        return outcome.reason

    # Fired(effect="open"): the machine decided; this module applies the effect.
    door["locked"] = False
    key_iid = items.trace_item(key_word, "player")
    assert key_iid is not None  # the key_fits guard already proved the key is carried
    return f"You unlock {door['name']} with {items.ITEMS[key_iid]['name']}."
