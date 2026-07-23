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
from typing import cast

from parts import items
from parts.seed import SEED_DIR, Door, load_doors
from parts.session import sentence_case
from parts.shelf.hourglass import WORLD_SANDS
from parts.shelf.statemachine import Guard, Refusal, Transition, advance, build

# The world is data: a seed's barriers live in its own doors.yaml (empty if it ships none).
DOORS: dict[str, Door] = load_doors(SEED_DIR / "doors.yaml")


def open_gate(door_id: str) -> bool:
    """Open a door by engine decree (e.g. a quest reforges a bridge) -- no key required. Returns
    True if a locked door was opened, False if it was unknown or already open. Only engine logic
    mutates world state; a quest names the effect, this applies it.

    A quest-opened door is PERMANENT: it never schedules a reclose (a reforged bridge stays
    reforged). Only a player unlocking a `recloses_after` door arms the self-closing timer."""
    door = DOORS.get(door_id)
    if door is None or not door["locked"]:
        return False
    door["locked"] = False
    return True


def _arm_reclose(door_id: str, door: Door) -> None:
    """A self-closing door, freshly unlocked by a player, schedules its own relock on the shared
    world timer (parts.shelf.hourglass): the world beat slams it shut after `recloses_after` beats.
    Doors without the field never arm, so ordinary and quest doors are untouched."""
    recloses = door.get("recloses_after", 0)
    if recloses:
        WORLD_SANDS.schedule(f"reclose:{door_id}", after=recloses, payload=("reclose", door_id))


def reclose(door_id: str) -> tuple[str, str] | None:
    """Relock a self-closing door (the effect the world beat applies when its timer fires).
    Returns (room_label, door_name) if it actually closed, or None if the door is unknown or was
    already shut -- idempotent, so a door reopened before its timer fires is not double-slammed.
    Only engine logic mutates world state; the beat names the effect, this applies it."""
    door = DOORS.get(door_id)
    if door is None or door["locked"]:
        return None
    door["locked"] = True
    return door["blocks"][0], door["name"]


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
    # Match by PROTOTYPE, not instance id: a door keyed to `copper_key` opens for any instance of
    # copper_key (a seed key or a cloned one). A seed key's prototype is its own label, so this is
    # unchanged for the singleton case.
    if items.prototype_of(key_iid) != door["key_id"]:
        return f"{sentence_case(items.ITEMS[key_iid]['name'])} doesn't fit the lock."
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
            return f"{sentence_case(door['name'])} is already unlocked."
        return outcome.reason

    # Fired(effect="open"): the machine decided; this module applies the effect.
    door["locked"] = False
    _arm_reclose(did, door)  # a self-closing door starts its relock countdown now
    key_iid = items.trace_item(key_word, "player")
    assert key_iid is not None  # the key_fits guard already proved the key is carried
    return f"You unlock {door['name']} with {items.ITEMS[key_iid]['name']}."
