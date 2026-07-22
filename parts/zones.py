"""CARD: zones -- areas that group rooms and refill on the world's beat.

Grouping over the flat room graph (regions/areas with a reset policy) is a mechanism
common to the MUD tradition, best documented in the Diku/Circle/tbaMUD family (LGPL,
license class B). This is an ORIGINAL Python implementation studied clean-room from the
public behavior (research/legacy_muds/behavior_specs/zone_reset.md); no historical code,
names, or structure was copied.

Two halves live here:
- Grouping (shipped): a seed declares AREAS in zones.yaml; a room render gains an area
  banner; labels, not vnums.
- The reset SCHEDULER (shipped): a per-area beat counter rides the world beat -- the same
  clock parts.aggression.menace uses, no background thread (architecture law 4). When an
  area comes due per its reset_mode + beats_between, `tick_zones` fires it.

The repop ACTION (shipped): when a due area fires, `_perform_reset` restocks its RESETTABLE items
-- any seed item flagged `resettable` that has gone missing from its home room respawns there as a
fresh instance (parts.items.clone). Object instancing makes this safe: a respawn never collides
with a copy a player carried off, and opt-in `resettable` leaves quest items and keys untouched.
"""

from parts import items
from parts.seed import SEED_DIR, Zone, load_zones
from parts.session import Session
from parts.world import WORLD

ZONES: dict[str, Zone] = load_zones(SEED_DIR / "zones.yaml", set(WORLD))

# Per-area beat counter: world beats since this area last came due. Runtime state, never
# persisted (derive, don't store) -- a fresh boot starts every area at zero.
_beats: dict[str, int] = {label: 0 for label in ZONES}


def zone_of(room: str) -> str | None:
    """The area label that owns this room, or None. A room belongs to at most one area."""
    for label, zone in ZONES.items():
        if room in zone["rooms"]:
            return label
    return None


def area_line(room: str) -> str:
    """The area banner for a room render, or '' if the room is in no area. Additive: a room
    outside every area renders exactly as before (so a seed with no zones.yaml is unchanged)."""
    label = zone_of(room)
    if label is None:
        return ""
    return f"[Area: {ZONES[label]['name']}]"


def _occupied(zone: Zone, here: str) -> bool:
    """POC occupancy proxy: is the acting player standing in this area right now? A full
    multi-occupant check rides the future session registry; for now the beat's own actor is
    the occupancy signal (a documented limitation, not a hidden one)."""
    return here in zone["rooms"]


def zones_due(here: str = "") -> list[str]:
    """Areas whose beat counter has reached their cadence and are eligible to reset now, given
    where the acting player stands. A read-only query: no mutation, no counter change."""
    due: list[str] = []
    for label, zone in ZONES.items():
        mode = zone["reset_mode"]
        if mode == "never":
            continue
        if _beats.get(label, 0) < zone["beats_between"]:
            continue
        if mode == "empty_only" and _occupied(zone, here):
            continue
        due.append(label)
    return due


def _perform_reset(label: str) -> None:
    """Restock a due area's RESETTABLE items: any item flagged `resettable` in the seed whose home
    room is in this area, and which is currently absent from that room, is respawned there as a
    fresh instance (parts.items.clone).

    Object instancing (which the earlier deferral waited on) makes this safe: the respawn is a new
    instance, so it never collides with a copy a player carried off, and opt-in `resettable` means
    quest items, keys, and the reforged bridge are never touched. A prototype at its spawn ceiling
    is skipped, never a crash. Doors and NPC respawn stay out of scope (doors carry quest-permanent
    state; felled NPCs already reassemble in combat) -- item repop is the safe, observable slice.
    Only engine logic mutates world state; the beat names the effect, this applies it."""
    rooms = set(ZONES[label]["rooms"])
    for prototype, template in items.PROTOTYPES.items():
        if not template.get("resettable"):
            continue
        home = template["location"]  # "room:<label>" for a placed item
        if not home.startswith("room:") or home.removeprefix("room:") not in rooms:
            continue
        if any(items.prototype_of(iid) == prototype for iid in items.items_in(home)):
            continue  # an instance is already home -- nothing to restock
        try:
            items.clone(prototype, home)
        except items.ItemError:
            continue  # at the spawn ceiling: skip this one, keep the beat alive


def tick_zones(session: Session) -> str:
    """Advance every area's beat counter by one world beat, then fire any that are due.

    The player's command is the only clock (architecture law 4): this rides the same beat as
    parts.aggression.menace -- no background thread, no second door into world state. When an
    area comes due it is reset (its resettable items restock; see `_perform_reset`) and its counter
    returns to zero. Returns '' -- the restock is silent; the player sees it on their next look."""
    here = session.location
    for label in ZONES:
        _beats[label] = _beats.get(label, 0) + 1
    for label in zones_due(here):
        _perform_reset(label)
        _beats[label] = 0
    return ""
