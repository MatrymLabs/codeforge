"""CARD: world -- world graph, direction aliases, movement.

The world is data -- and now it lives in a seed file, not in Python.
resolve_move is the only function that changes a player's location.
"""

from itertools import zip_longest

from parts.world.armory import arm_guardians
from parts.world.creator_workshop import install_workshop
from parts.world.delve import generate_delves, load_dungeons, wire_delve_mouths
from parts.world.delve_sets import forge_delve_sets
from parts.world.doors import DOORS, barred_door_for
from parts.world.gearsets import register_sets
from parts.world.inscriptions import carve_inscriptions
from parts.world.items import ITEMS, register_prototypes
from parts.world.landmarks import raise_landmarks
from parts.world.npcs import NPCS
from parts.world.relics import arm_deep_bosses
from parts.world.rumors import seed_rumors
from parts.world.seed import SEED_DIR, Npc, Room, inspect_world_links, load_rooms
from parts.world.spiral import extend_world_with_road, load_spiral_config
from parts.world.townsfolk import load_settlements, populate_settlements
from parts.world.travel import load_waystones
from parts.world.wardens import name_wardens
from parts.world.wildlands import (
    generate_wildlands,
    load_wildlands_config,
    wire_attach_exits,
)

SEED_PATH = SEED_DIR / "rooms.yaml"

WORLD: dict[str, Room] = load_rooms(SEED_PATH)
# Procedurally extend the Forgeward Road outward across the wilds if the seed opts in (spiral.yaml).
# The generated marches are seed-shaped data, merged BEFORE validation so the same loader gates
# check them, and the seed's attach room grows an `east` exit onto the first march (flat, no climb).
_spiral_config = load_spiral_config(SEED_DIR / "spiral.yaml")
if _spiral_config is not None:
    extend_world_with_road(WORLD, NPCS, _spiral_config)

# Procedurally grow wilderness REGIONS if the seed opts in (wildlands.yaml): a compact config per
# region expands into a connected, biome-varied trail-network with ambient life, through the
# loader gates. This is how the world reaches world-generation scale without hand-authoring every
# room (parts.world.wildlands, a sibling of the Spiral). Merged BEFORE validation, so a bad config
# fails loud; each region's attach room grows one exit onto its trail-head.
_wildlands_configs = load_wildlands_config(SEED_DIR / "wildlands.yaml")
if _wildlands_configs is not None:
    _wild_rooms, _wild_npcs = generate_wildlands(_wildlands_configs, set(WORLD))
    WORLD.update(_wild_rooms)
    NPCS.update(_wild_npcs)
    wire_attach_exits(WORLD, _wildlands_configs)
    # Forge a themed gear drop for every generated guardian (parts.world.armory), so felling a named
    # hunt target can drop something to wear; the affix factory rolls rarity on top at defeat.
    # Registered as prototypes (not just appended to ITEMS) before the link audit, so a guardian's
    # drop can be cloned and passes the same gate as authored gear.
    register_prototypes(arm_guardians(_wild_npcs))

# Sink a multi-room delve below every dungeon mouth (seeds/<world>/dungeons.yaml): a descent of
# escalating foes ending in a named deep boss (parts.world.delve). The bosses are armed with gear
# like the wildlands guardians. Merged before the link audit so the new rooms/drops pass its gate.
_dungeons = load_dungeons(SEED_DIR / "dungeons.yaml")
if _dungeons is not None:
    _delve_rooms, _delve_npcs = generate_delves(_dungeons)
    WORLD.update(_delve_rooms)
    NPCS.update(_delve_npcs)
    wire_delve_mouths(WORLD, _dungeons)
    # Name each deep boss for its dungeon (parts.world.wardens), BEFORE the bounty board reads the
    # foe set -- so rumour, inscription, relic, bounty, and the foe itself all name the one keeper.
    name_wardens(_dungeons, _delve_npcs)
    register_prototypes(arm_guardians(_delve_npcs))
    # Give every deep boss a SIGNATURE legendary relic (a named, readable payoff on top of its
    # generic gear), so felling one is a memorable event, not just a drop (parts.world.relics).
    register_prototypes(arm_deep_bosses(_dungeons, _delve_npcs))
    # Carve a readable lore inscription into each dungeon's boss chamber (parts.world.inscriptions):
    # environmental storytelling naming the dungeon + relic, closing the rumour->depths loop.
    ITEMS.update(carve_inscriptions(_dungeons))
    # Forge a matched three-piece gear SET per dungeon, one piece on each delve trash foe, so
    # clearing the whole descent earns a set bonus (parts.world.delve_sets): a collect-it loot goal.
    _set_items, _delve_sets = forge_delve_sets(_dungeons, _delve_npcs)
    register_prototypes(_set_items)
    register_sets(_delve_sets)

# Populate the map's settlements (seeds/<world>/settlements.yaml) with townsfolk and a merchant at
# each town's level band (parts.world.townsfolk) -- the economy sink and the towns' life. Merged
# before the link audit, so each merchant's shop wares are cross-checked like an authored shop.
_settlements = load_settlements(SEED_DIR / "settlements.yaml")
_town_npcs: dict[str, Npc] = {}
if _settlements is not None:
    _town_npcs = populate_settlements(_settlements)
    NPCS.update(_town_npcs)

# Every generated world carries the Creator's Workshop: a Grand Library linked to the spawn, and a
# concealed Creator's Door onto an isolated administrative instance only the Seed Owner may cross
# (parts.world.workshop). Installed after the seed and generators, before the link audit, so the
# canonical rooms pass the same gates as authored ones.
install_workshop(WORLD)

inspect_world_links(WORLD, ITEMS, NPCS)

# With the full foe set assembled (seed + the procedural Spiral), generate a hunt-contract for
# every combatant foe -- side-content at volume, folded into the quest engine (parts.world.quest).
from parts.world.quest import (  # noqa: E402 -- after NPCS ready
    register_bounties,
    register_errands,
    register_spine,
    register_storylines,
)

register_bounties(NPCS)

# The Waystone travel network: the seed's zone hubs a player may pay to cross between
# (parts.world.travel). {} when the seed ships no network (first-forge/spiral-ascent).
WAYSTONES = load_waystones(SEED_DIR / "waystones.yaml") or {}


# Travel-errands: one per settlement, each sending a player to a distinct destination on the map --
# a town, a dungeon, or a waystone hub -- so the notice board carries exploration content, not only
# kills (parts.world.errands). The three kinds are INTERLEAVED so a board of errands reads varied,
# not one repeated kind.
def _interleave(*lists: list[dict[str, object]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in zip_longest(*lists):
        out.extend(item for item in row if item is not None)
    return out


_errand_destinations = _interleave(
    [{"room": c["room"], "name": c["name"], "kind": "dungeon"} for c in (_dungeons or [])],
    [{"room": room, "name": cfg["name"], "kind": "hub"} for room, cfg in WAYSTONES.items()],
    [{"room": c["room"], "name": c["name"], "kind": "town"} for c in (_settlements or [])],
)
if _settlements:
    register_errands(_settlements, _errand_destinations)

# Zone storylines: a three-beat narrative chain per zone that pairs a town with a dungeon -- reach
# the dungeon, slay its deep boss, bear word home -- woven from the world's own geography
# (parts.world.storylines). This is the DEPTH counterpart to the errands' VOLUME. The zone metadata
# is loaded straight from the seed here (zones.py owns the live scheduler; we only need the room
# grouping), so the story arcs thread the same rooms the reset areas do.
from parts.world.seed import load_zones  # noqa: E402 -- WORLD must exist for the room gate

_story_zones = [dict(z) for z in load_zones(SEED_DIR / "zones.yaml", set(WORLD)).values()]
if _settlements and _dungeons:
    register_storylines(_story_zones, _settlements, _dungeons)

# Zone landmarks: a readable monument in each zone's hub naming the region, its level band, and any
# dungeon within (parts.world.landmarks) -- surface storytelling, the twin of the depths' lore.
if _dungeons is not None:
    ITEMS.update(raise_landmarks(_story_zones, _dungeons))

# The world spine: one main-road campaign quest (the Forgeward Road) that guides a player through
# the zones in level order, giving the sprawling world a through-line (parts.world.spine). It lives
# in the `quest` log, not the notice board -- the spine the side-content hangs on.
register_spine(_story_zones)

# Living rumours: give each town resident gossip that NAMES the zone's dungeon and the relic it
# guards (parts.world.rumors), so the plaza becomes a signpost toward content, not just flavour. The
# NPCs are already in NPCS (same objects), so mutating them here after the link audit is safe.
if _town_npcs and _dungeons:
    seed_rumors(_town_npcs, _story_zones, _dungeons)

# The spawn point is seed-defined, not hardcoded: the FIRST room in rooms.yaml.
# (first-forge -> "forge"; spiral-ascent -> "spiral_landing".)
START_ROOM: str = next(iter(WORLD))

# The compass a Forger can walk: four cardinals, four diagonals, and the vertical pair, each with a
# one- or two-letter shorthand. A room's exit may also be keyed by a NOUN (`gate`, `market`, `in`,
# `out`) -- those are not listed here; they are typed literally and resolved against the room's own
# exits (see _go_cmd and the noun-exit fallback in forge._route). The metaphor: the compass is
# fixed, but a threshold can be named for the place it opens onto.
DIRECTIONS: dict[str, str] = {
    "north": "north",
    "n": "north",
    "south": "south",
    "s": "south",
    "east": "east",
    "e": "east",
    "west": "west",
    "w": "west",
    "northeast": "northeast",
    "ne": "northeast",
    "northwest": "northwest",
    "nw": "northwest",
    "southeast": "southeast",
    "se": "southeast",
    "southwest": "southwest",
    "sw": "southwest",
    "up": "up",
    "u": "up",
    "down": "down",
    "d": "down",
}


def render_room(room_id: str) -> str:
    room = WORLD[room_id]
    exits = ", ".join(room["exits"]) or "none"
    return f"\n== {room['name']} ==\n{room['desc']}\nExits: {exits}"


def dynamic_capability(room_id: str) -> str:
    """The live capability a room surfaces on look (seed-declared `dynamic`), or "" for none."""
    room = WORLD.get(room_id)
    return room.get("dynamic", "") if room is not None else ""


def resolve_move(location: str, direction: str) -> tuple[str, str]:
    """Pure movement: returns (new_location, message).

    On success: (destination, ""). On failure: (same location, why).
    The world layer never prints -- rendering belongs to the caller."""
    blocked = barred_door_for(location, direction)
    if blocked:
        return (location, f"{DOORS[blocked]['name'].capitalize()} is locked.")
    exits = WORLD[location]["exits"]
    if direction in exits:
        return (exits[direction], "")
    return (location, "You can't go that way.")
