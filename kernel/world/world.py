"""CARD: world -- world graph, direction aliases, movement.

The world is data -- and now it lives in a seed file, not in Python.
resolve_move is the only function that changes a player's location.
"""

from itertools import zip_longest

from kernel.world.armory import arm_guardians
from kernel.world.authored_towns import install_authored_towns
from kernel.world.creator_workshop import install_workshop
from kernel.world.delve import generate_delves, load_dungeons, wire_delve_mouths
from kernel.world.delve_sets import forge_delve_sets
from kernel.world.doors import DOORS, barred_door_for
from kernel.world.fieldzone import FieldZone, build_field_zone, load_field_configs
from kernel.world.gearsets import register_sets
from kernel.world.inscriptions import carve_inscriptions
from kernel.world.items import ITEMS, register_prototypes
from kernel.world.landmarks import raise_landmarks
from kernel.world.npcs import NPCS
from kernel.world.relics import arm_deep_bosses
from kernel.world.rumors import seed_rumors
from kernel.world.seed import SEED_DIR, Npc, Room, Zone, inspect_world_links, load_rooms
from kernel.world.spiral import extend_world_with_road, load_spiral_config
from kernel.world.townsfolk import load_settlements, populate_settlements
from kernel.world.travel import load_waystones
from kernel.world.wardens import name_wardens
from kernel.world.wildlands import (
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
# room (kernel.world.wildlands, a sibling of the Spiral). Merged BEFORE validation, so a bad config
# fails loud; each region's attach room grows one exit onto its trail-head.
_wildlands_configs = load_wildlands_config(SEED_DIR / "wildlands.yaml")
if _wildlands_configs is not None:
    _wild_rooms, _wild_npcs = generate_wildlands(_wildlands_configs, set(WORLD))
    WORLD.update(_wild_rooms)
    NPCS.update(_wild_npcs)
    wire_attach_exits(WORLD, _wildlands_configs)
    # Forge a themed gear drop for each generated guardian (kernel.world.armory): felling a named
    # hunt target can drop something to wear; the affix factory rolls rarity on top at defeat.
    # Registered as prototypes (not just appended to ITEMS) before the link audit, so a guardian's
    # drop can be cloned and passes the same gate as authored gear.
    register_prototypes(arm_guardians(_wild_npcs))

# Grow FIELD-backed wilderness zones if the seed opts in (fields.yaml): a zone that wants an OPEN
# WORLD instead of a linear trail-chain declares a compact field row (size, seed, biome, levels,
# optional river + landmarks) and kernel.world.fieldzone expands it into a WORLD-shaped LIVING field
# (rivers, elevation, roads, foes, gather nodes, guardians) grafted onto its hub. This is the
# trail-to-field upgrade of the World Topology Doctrine; each field's AREA metadata is published in
# FIELD_ZONES so kernel.world.zones registers it for the scheduler + zone_of, exactly like a trail.
FIELD_ZONES: dict[str, Zone] = {}
_field_configs = load_field_configs(SEED_DIR / "fields.yaml")
if _field_configs is not None:
    for _cfg in _field_configs:
        _fz: FieldZone = build_field_zone(_cfg, set(WORLD))
        WORLD.update(_fz.rooms)
        NPCS.update(_fz.npcs)
        WORLD[_fz.attach]["exits"].setdefault(_fz.attach_dir, _fz.gate)  # hub -> field entrance
        register_prototypes(arm_guardians(_fz.npcs))
        FIELD_ZONES[_fz.label] = _fz.zone

# Sink a multi-room delve below every dungeon mouth (seeds/<world>/dungeons.yaml): a descent of
# escalating foes ending in a named deep boss (kernel.world.delve). The bosses are armed with gear
# like the wildlands guardians. Merged before the link audit so the new rooms/drops pass its gate.
_dungeons = load_dungeons(SEED_DIR / "dungeons.yaml")
if _dungeons is not None:
    _delve_rooms, _delve_npcs = generate_delves(_dungeons)
    WORLD.update(_delve_rooms)
    NPCS.update(_delve_npcs)
    wire_delve_mouths(WORLD, _dungeons)
    # Name each deep boss for its dungeon (kernel.world.wardens), BEFORE the bounty board reads the
    # foe set -- so rumour, inscription, relic, bounty, and the foe itself all name the one keeper.
    name_wardens(_dungeons, _delve_npcs)
    register_prototypes(arm_guardians(_delve_npcs))
    # Give every deep boss a SIGNATURE legendary relic (a named, readable payoff on top of its
    # generic gear), so felling one is a memorable event, not just a drop (kernel.world.relics).
    register_prototypes(arm_deep_bosses(_dungeons, _delve_npcs))
    # Carve a lore inscription into each dungeon's boss chamber (kernel.world.inscriptions):
    # environmental storytelling naming the dungeon + relic, closing the rumour->depths loop.
    ITEMS.update(carve_inscriptions(_dungeons))
    # Forge a matched three-piece gear SET per dungeon, one piece on each delve trash foe, so
    # clearing whole descent earns a set bonus (kernel.world.delve_sets): a collect-it loot goal.
    _set_items, _delve_sets = forge_delve_sets(_dungeons, _delve_npcs)
    register_prototypes(_set_items)
    register_sets(_delve_sets)

# Populate the map's settlements (seeds/<world>/settlements.yaml) with townsfolk and a merchant at
# each town's level band (kernel.world.townsfolk) -- the economy sink and the towns' life. Merged
# before the link audit, so each merchant's shop wares are cross-checked like an authored shop.
_settlements = load_settlements(SEED_DIR / "settlements.yaml")
_town_npcs: dict[str, Npc] = {}
if _settlements is not None:
    _town_npcs = populate_settlements(_settlements)
    NPCS.update(_town_npcs)
    # Give every settlement an inn to step into (kernel.world.inns): a warm interior and its keeper,
    # the town's twin of the delve. Merged before the link audit so the new rooms + `in` exits pass
    # the same gate as authored rooms.
    from kernel.world.inns import raise_inns, wire_inn_doors

    _inn_rooms, _inn_npcs = raise_inns(_settlements)
    WORLD.update(_inn_rooms)
    NPCS.update(_inn_npcs)
    wire_inn_doors(WORLD, _settlements)
    # ...and a general store (kernel.world.stores): the materials market off the plaza, the coin
    # SOURCE for gatherers that the draught-selling merchant (a sink) is the counterpart to. Its buy
    # list is filtered to materials the loaded seed has, so the boot cross-check always holds.
    from kernel.world.stores import raise_stores, wire_store_doors

    _store_rooms, _store_npcs = raise_stores(_settlements, set(ITEMS))
    WORLD.update(_store_rooms)
    NPCS.update(_store_npcs)
    wire_store_doors(WORLD, _settlements)

# Raise every hand-authored town interior (kernel.world.authored_towns): each polished settlement
# off its map hub, with its residents, items, and the rooms its quest turns on. Data-driven -- a new
# town is a file in seeds/aethryn/authored/. A no-op for any town whose hub this world lacks (only
# aethryn has them), so other seeds are untouched. Merged before the link audit, so every authored
# room/NPC/item passes the same gate as the generated world.
register_prototypes(install_authored_towns(WORLD, NPCS))

# Every generated world carries the Creator's Workshop: a Grand Library linked to the spawn, and a
# concealed Creator's Door onto an isolated administrative instance only the Seed Owner may cross
# (kernel.world.workshop). Installed after the seed and generators, before the link audit, so the
# canonical rooms pass the same gates as authored ones.
install_workshop(WORLD)

inspect_world_links(WORLD, ITEMS, NPCS)

# With the full foe set assembled (seed + the procedural Spiral), generate a hunt-contract for
# every combatant foe -- side-content at volume, folded into the quest engine (kernel.world.quest).
from kernel.world.quest import (  # noqa: E402 -- after NPCS ready
    register_bounties,
    register_crawls,
    register_culls,
    register_errands,
    register_forages,
    register_spine,
    register_storylines,
)

register_bounties(NPCS)

# Arm the auction house's recurring expiry sweep on the scheduler, so a lapsed listing is mailed
# back to its seller (kernel.world.auction). Registered once at world assembly, off any thread.
from kernel.world.auction import register_sweep as _register_auction_sweep  # noqa: E402

_register_auction_sweep()

# The Waystone travel network: the seed's zone hubs a player may pay to cross between
# (kernel.world.travel). {} when the seed ships no network (first-forge/spiral-ascent).
WAYSTONES = load_waystones(SEED_DIR / "waystones.yaml") or {}


# Travel-errands: one per settlement, each sending a player to a distinct destination on the map --
# a town, a dungeon, or a waystone hub -- so the notice board carries exploration content, not only
# kills (kernel.world.errands). The three kinds are INTERLEAVED so a board of errands reads varied,
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

# Delivery contracts: carry a parcel from one town to its trade-partner (kernel.world.delivery) -- a
# two-beat courier archetype (take the parcel, arrive at the destination). The generator also mints
# the parcel items, placed here at their source towns before the notice board reads them.
from kernel.world.delivery import generate_deliveries  # noqa: E402
from kernel.world.quest import register_specs  # noqa: E402

if _settlements:
    _delivery_specs, _parcels = generate_deliveries(_settlements)
    ITEMS.update(_parcels)
    register_specs(_delivery_specs)

# Zone storylines: a three-beat narrative chain per zone that pairs a town with a dungeon -- reach
# the dungeon, slay its deep boss, bear word home -- woven from the world's own geography
# (kernel.world.storylines). This is the DEPTH counterpart to the errands' VOLUME. The zone metadata
# is loaded straight from the seed here (zones.py owns the live scheduler; we only need the room
# grouping), so the story arcs thread the same rooms the reset areas do.
from kernel.world.seed import load_zones  # noqa: E402 -- WORLD must exist for the room gate

_story_zones = [dict(z) for z in load_zones(SEED_DIR / "zones.yaml", set(WORLD)).values()]
if _settlements and _dungeons:
    register_storylines(_story_zones, _settlements, _dungeons)

# Dungeon-crawl contracts: one descent per dungeon, rewarding reaching the deep boss's chamber
# (kernel.world.dungeon_crawl) -- an exploration archetype over the delve geography.
if _dungeons:
    register_crawls(_dungeons)

# Cull contracts: 'fell N of a kind HERE' at volume, the MMO's most common quest (kernel.world.cull)
# -- one per ZONE x each creature type of its biome x count-tier, each SCOPED to its zone so kills
# only count where they happen (honest volume, not one quest cloned per place). We rebuild the full
# zone set (authored + Spiral + wilderness regions, where the creatures live) from the SAME pure
# builders kernel.world.zones uses, so the scope labels match zone_of -- without importing zones.py
# (which imports WORLD, a cycle).
from kernel.world.spiral import spiral_zones  # noqa: E402 -- same builder zones.py uses
from kernel.world.wildlands import wildlands_zones  # noqa: E402 -- same builder zones.py uses

_all_zones = dict(load_zones(SEED_DIR / "zones.yaml", set(WORLD)))
if _spiral_config is not None:
    _all_zones.update(spiral_zones(_spiral_config))
if _wildlands_configs is not None:
    _all_zones.update(wildlands_zones(_wildlands_configs))
_all_zones.update(FIELD_ZONES)  # field-backed zones live where their creatures do, too
_cull_zones: list[dict[str, object]] = [
    {"label": lbl, "name": z["name"], "biome": z.get("biome", ""), "level_max": z.get("level_max")}
    for lbl, z in _all_zones.items()
]
register_culls(_cull_zones)

# Forage contracts: 'gather N of a material HERE' at volume (kernel.world.forage) -- the non-combat
# twin of the cull board, one per zone x material its biome yields x count-tier, reusing the same
# zone-scoped keys the gather action fires.
register_forages(_cull_zones)

# Zone landmarks: a readable monument in each zone's hub naming the region, its level band, and any
# dungeon within (kernel.world.landmarks) -- surface storytelling, the twin of the depths' lore.
if _dungeons is not None:
    ITEMS.update(raise_landmarks(_story_zones, _dungeons))

# The world spine: one main-road campaign quest (the Forgeward Road) that guides a player through
# the zones in level order, giving the sprawling world a through-line (kernel.world.spine). It lives
# in the `quest` log, not the notice board -- the spine the side-content hangs on.
register_spine(_story_zones)

# Living rumours: give each town resident gossip that NAMES the zone's dungeon and the relic it
# guards (kernel.world.rumors), so plaza becomes a signpost toward content, not just flavour. The
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
