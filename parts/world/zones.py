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
  clock parts.world.aggression.menace uses, no background thread (architecture law 4). When an
  area comes due per its reset_mode + beats_between, `tick_zones` fires it.

The repop ACTION (shipped): when a due area fires, `_perform_reset` restocks its RESETTABLE items
-- any seed item flagged `resettable` that has gone missing from its home room respawns there as a
fresh instance (parts.world.items.clone). Object instancing keeps it safe: a respawn never collides
with a copy a player carried off, and opt-in `resettable` leaves quest items and keys untouched.
"""

from parts.world import items
from parts.world.respawn import SPAWN_RNG, pick_room
from parts.world.seed import SEED_DIR, Zone, load_zones
from parts.world.session import Session
from parts.world.spiral import load_spiral_config, spiral_zones
from parts.world.wildlands import load_wildlands_config, wildlands_zones
from parts.world.world import WORLD


def merged_zones(base: dict[str, Zone], spiral_cfg: dict | None) -> dict[str, Zone]:
    """The seed's authored areas plus the procedural Spiral's generated ones. When the seed ships a
    spiral.yaml, each generated Coil becomes its own named area (so the back half renders an area
    banner like the rest of the world); with no spiral, `base` is returned unchanged. Pure, so the
    merge is testable without booting a spiral seed."""
    zones = dict(base)
    if spiral_cfg is not None:
        zones.update(spiral_zones(spiral_cfg))
    return zones


ZONES: dict[str, Zone] = merged_zones(
    load_zones(SEED_DIR / "zones.yaml", set(WORLD)),
    load_spiral_config(SEED_DIR / "spiral.yaml"),
)
# The procedural wilderness regions carry their own metadata areas too (one per region), so every
# generated room belongs to geography exactly like the hand-authored and Spiral rooms.
_wildlands_cfg = load_wildlands_config(SEED_DIR / "wildlands.yaml")
if _wildlands_cfg is not None:
    ZONES.update(wildlands_zones(_wildlands_cfg))

# Per-area beat counter: world beats since this area last came due. Runtime state, never
# persisted (derive, don't store) -- a fresh boot starts every area at zero.
_beats: dict[str, int] = {label: 0 for label in ZONES}

# Reverse index: room label -> its owning area label. Built once from ZONES so `zone_of` is an O(1)
# lookup instead of a linear scan over every area's room list. At aethryn scale (28 areas spanning
# ~53k rooms in plain lists) the scan cost ~800us per call, on a path hit every move, render, and
# combat beat; the index makes it a single dict lookup. Cache invalidation is by IDENTITY: if ZONES
# is replaced (a seed swap, or a test's monkeypatch), the next lookup rebuilds from the new dict.
_room_zone: dict[str, str] = {}
_room_zone_source: dict[str, Zone] | None = None


def _room_zone_index() -> dict[str, str]:
    """The room -> area-label index, rebuilt only when ZONES has been swapped for a different dict.
    First area wins on the (undocumented) overlap case, exactly matching the old scan's
    first-match-returns behaviour, so this is a pure speedup with no change in what is returned."""
    global _room_zone, _room_zone_source
    if _room_zone_source is not ZONES:
        index: dict[str, str] = {}
        for label, zone in ZONES.items():
            for room in zone["rooms"]:
                index.setdefault(room, label)  # first area wins, as the linear scan did
        _room_zone = index
        _room_zone_source = ZONES
    return _room_zone


def zone_of(room: str) -> str | None:
    """The area label that owns this room, or None. A room belongs to at most one area.

    O(1) via a reverse index built once from ZONES (`_room_zone_index`); the earlier linear scan
    over every area's room list cost ~800us per call at aethryn's ~53k-room scale, on a hot path."""
    return _room_zone_index().get(room)


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
    fresh instance (parts.world.items.clone).

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
    _spawn_wanderers(rooms)


def _spawn_wanderers(rooms: set[str]) -> None:
    """The DYNAMIC spawn (respawn policy `wandering_spawn`): a wandering pickup (a `spawn_pool`
    item) appears at ONE pick_room-chosen site inside this area, but only when no instance of it is
    loose anywhere in its whole pool, and only when its rarity roll (`spawn_chance`) comes up. So
    the pickup moves between resets and is not always there -- avoiding static, predictable spots.

    The pool may span areas; restricting sites to this area's rooms while checking the WHOLE pool
    for a live instance keeps a wanderer single across the map (one loose copy at a time). A
    prototype at its instance ceiling is skipped, never a crash. Only engine logic mutates state;
    the beat fires this, respawn.pick_room chooses where."""
    from parts.world.climate import now, season_of

    for prototype, template in items.PROTOTYPES.items():
        pool = template.get("spawn_pool")
        if not pool:
            continue
        sites = [room for room in pool if room in rooms]
        if not sites:
            continue  # this area holds none of the wanderer's candidate rooms
        seasons = template.get("seasons")
        if seasons and season_of(now()) not in seasons:
            continue  # out of its season: a winter relic does not appear in summer
        if any(
            items.prototype_of(iid) == prototype
            for room in pool
            for iid in items.items_in(f"room:{room}")
        ):
            continue  # already loose somewhere in its pool -- one at a time, never duplicated
        chance = template.get("spawn_chance", 1)
        if chance > 1 and SPAWN_RNG.randrange(chance) != 0:
            continue  # rarity: this reset it stays hidden
        try:
            items.clone(prototype, pick_room(sites, rng=SPAWN_RNG))  # sites non-empty: a real room
        except items.ItemError:
            continue  # at the spawn ceiling: skip, keep the beat alive


def tick_zones(session: Session) -> str:
    """Advance every area's beat counter by one world beat, then fire any that are due.

    The player's command is the only clock (architecture law 4): this rides the same beat as
    parts.world.aggression.menace -- no background thread, no second door into world state. When an
    area comes due it is reset (its resettable items restock; see `_perform_reset`) and its counter
    returns to zero. Returns '' -- the restock is silent; the player sees it on their next look."""
    here = session.location
    for label in ZONES:
        _beats[label] = _beats.get(label, 0) + 1
    for label in zones_due(here):
        _perform_reset(label)
        _beats[label] = 0
    return ""
