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

The repop ACTION is deferred by design (see `_perform_reset`): safe area repopulation needs
machinery CodeForge does not yet have. The scheduler and grouping are proven; the mutation
lands once that model is decided.
"""

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
    """The repop action for a due area. DEFERRED by design: a safe no-op until the model is
    decided. Safe area repopulation needs machinery CodeForge does not yet have:
    - object instancing for item restock (items are singletons keyed by label, so a naive
      restock would duplicate a quest item or pull it from a player's pack);
    - a resettable-vs-quest-permanent model for doors (re-locking the reforged bridge would
      soft-lock the arc);
    - a decision on whether felled NPCs stay down (combat reassembles them in place today, and
      healing a foe mid-fight would break combat).
    Kept as the single seam where the action will land, so wiring it later touches one place."""
    return None


def tick_zones(session: Session) -> str:
    """Advance every area's beat counter by one world beat, then fire any that are due.

    The player's command is the only clock (architecture law 4): this rides the same beat as
    parts.aggression.menace -- no background thread, no second door into world state. When an
    area comes due it is reset and its counter returns to zero. Returns '' -- the beat is silent
    to the player (the repop action is a documented no-op; see `_perform_reset`)."""
    here = session.location
    for label in ZONES:
        _beats[label] = _beats.get(label, 0) + 1
    for label in zones_due(here):
        _perform_reset(label)
        _beats[label] = 0
    return ""
