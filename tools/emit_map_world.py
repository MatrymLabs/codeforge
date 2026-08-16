# ruff: noqa: E501  (data-heavy map emitter: long place descriptions)
#!/usr/bin/env python3
"""Emit the canonical Aethryn seed geography from the world map (Pictures/Map.png).

The map is the blueprint; this encodes it as data and generates the consistent seed files
(rooms/npcs/zones/wildlands) so every named place on the map becomes a connected, validated room
with a resident, its zone carries the map's level band + biome, and the wildlands generator fills
each zone's wilderness. Re-runnable: edit the DATA below and regenerate. The world stays data.

Run from the repo root:  python tools/emit_map_world.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kernel.world.seed import BLUEPRINTS_ROOT

# --- The map, as data --------------------------------------------------------------------------
# Each zone: id, display name, level band, biome (a wildlands biome key), a hub blurb, the wildlands
# fill biome, and its PLACES. A place: id, name, kind (capital/city/town/port/dungeon/landmark),
# and a one-line blurb. INTER-ZONE edges are declared once in LINKS (a -> b, direction, route).
ZONES = [
    (
        "veridia",
        "Veridia",
        1,
        30,
        "temperate-meadow",
        "green starter valleys of rivers and open road, where every journey begins",
        [
            (
                "greenhold",
                "Greenhold",
                "town",
                "a walled market-town of green fields, the first stop of every new traveller",
            ),
            (
                "elderwatch",
                "Elderwatch",
                "town",
                "an old watch-town on the Veridia road, its tower long unmanned",
            ),
            (
                "riverbend",
                "Riverbend",
                "town",
                "a fishing town where the river folds back on itself under willow",
            ),
            (
                "sunmeadow",
                "Sunmeadow",
                "town",
                "a hamlet of hayfields and beehives on the sunniest downs in Veridia",
            ),
            (
                "the_sunken_barrow",
                "The Sunken Barrow",
                "dungeon",
                "a grassed-over barrow at the valley's edge, its fallen stones the mouth of a dark stair down",
            ),
        ],
    ),
    (
        "duskwood_vale",
        "Duskwood Vale",
        20,
        50,
        "wild-forest",
        "a shadowed forest-vale of old growth and older secrets",
        [
            (
                "ravenwatch",
                "Ravenwatch",
                "town",
                "a timber town under the eaves, its roofs black with roosting ravens",
            ),
            (
                "moonshade",
                "Moonshade",
                "town",
                "a moonlit glade-town where the Duskwood folk trade by lantern",
            ),
            (
                "twilight_grove",
                "Twilight Grove",
                "village",
                "a hidden grove-village where the dusk never quite lifts",
            ),
            (
                "the_black_hollow",
                "The Black Hollow",
                "dungeon",
                "a lightless hollow beneath a split oak, mouth of a dungeon of the deep wood",
            ),
        ],
    ),
    (
        "caeloria",
        "Caeloria",
        30,
        60,
        "temperate-meadow",
        "the heartland kingdom of golden plains and the high road",
        [
            (
                "caeloria_city",
                "Caeloria City",
                "capital",
                "the capital of the heartland, its gold-crowned towers ruling the central plains",
            ),
            (
                "brightwater",
                "Brightwater",
                "city",
                "a river-city of mills and bright weirs east of the capital",
            ),
            (
                "silverwatch",
                "Silverwatch",
                "town",
                "a silver-mining town on the plains' southern edge",
            ),
            (
                "westgate",
                "Westgate",
                "town",
                "the western gate-town where Veridia's road meets the heartland",
            ),
            (
                "starfall_temple",
                "Starfall Temple",
                "dungeon",
                "a fallen-star temple on the plains, its crater a dungeon of light and dust",
            ),
        ],
    ),
    (
        "eldryn_forest",
        "Eldryn Forest",
        50,
        80,
        "wild-forest",
        "an ancient forest kingdom grown around a tree older than any crown",
        [
            (
                "eldryn_city",
                "Eldryn City",
                "capital",
                "the forest capital, its halls grown into living trunks the size of towers",
            ),
            (
                "wildgrowth",
                "Wildgrowth",
                "town",
                "a frontier town where the forest is always trying to take the road back",
            ),
            (
                "greenmist",
                "Greenmist",
                "town",
                "a town of the eastern eaves, wrapped in a green mist that never burns off",
            ),
            (
                "the_great_tree",
                "The Great Tree",
                "landmark",
                "the heart of Eldryn Forest, a tree said to be older than the oldest kingdom",
            ),
            (
                "rotwood_deep",
                "Rotwood Deep",
                "dungeon",
                "a root-choked deep beneath the ancient forest, where the wood's old rot has grown teeth",
            ),
        ],
    ),
    (
        "frostspire_peaks",
        "Frostspire Peaks",
        60,
        90,
        "glacier-waste",
        "the frozen north of glacier-crowned peaks and howling passes",
        [
            (
                "frosthold",
                "Frosthold",
                "city",
                "a fortress-city carved into the ice at the roof of the world",
            ),
            (
                "winters_grasp",
                "Winter's Grasp",
                "town",
                "a high town on the glacier's edge, where the cold has a grip and a will",
            ),
            (
                "ironwall_pass",
                "Ironwall Pass",
                "town",
                "the gate-town of the great pass, the only road through the peaks",
            ),
            (
                "glacial_bastion",
                "Glacial Bastion",
                "dungeon",
                "an ice-locked bastion on the northern crags, a dungeon of the frozen dead",
            ),
        ],
    ),
    (
        "zhaar_desert",
        "Zhaar Desert",
        80,
        130,
        "salt-desert",
        "a vast scorched desert of dunes, ruins, and buried fire",
        [
            (
                "sunscar_city",
                "Sunscar City",
                "capital",
                "the desert capital, a sandstone city ringing the only sweet well for a hundred miles",
            ),
            (
                "red_dunes",
                "Red Dune",
                "village",
                "a caravan-outpost among the great red dunes of the deep desert",
            ),
            (
                "sandspire_ruins",
                "Sandspire Ruins",
                "landmark",
                "the half-buried spires of a civilisation the desert swallowed",
            ),
            (
                "the_obsidian_pit",
                "The Obsidian Pit",
                "dungeon",
                "a black glass pit where the desert cracks open onto the fire below",
            ),
            (
                "scorchstone_keep",
                "Scorchstone Keep",
                "dungeon",
                "a heat-blasted keep on a scorchstone mesa, held by things that do not burn",
            ),
        ],
    ),
    (
        "xilnath_jungle",
        "Xil'nath Jungle",
        90,
        150,
        "living-jungle",
        "a vast living jungle that shifts its own canopy and swallows the unwary",
        [
            (
                "zulkarak",
                "Zul'karak",
                "city",
                "a ziggurat-city of a jungle people, half-reclaimed by the green",
            ),
            (
                "mistvale",
                "Mistvale",
                "town",
                "a stilt-town in a jungle vale that is never out of the mist",
            ),
            (
                "shifting_canopy",
                "Shifting Canopy",
                "landmark",
                "a stretch of jungle whose canopy is never the same path twice",
            ),
            (
                "heart_of_xilnath",
                "Heart of Xil'nath",
                "dungeon",
                "the beating green heart of the jungle, a dungeon that is one living thing",
            ),
        ],
    ),
    (
        "thalorin",
        "Thalorin",
        100,
        140,
        "highland-moor",
        "a harsh mountain realm of iron keeps and deep mines",
        [
            (
                "stonefang_keep",
                "Stonefang Keep",
                "city",
                "a fanged mountain keep guarding the Thalorin heights",
            ),
            (
                "boulderfall",
                "Boulderfall",
                "town",
                "a town built in the rubble of an ancient rockslide, and used to it",
            ),
            (
                "khazgor_peaks",
                "Khazgor Peaks",
                "landmark",
                "the iron-grey peaks that give Thalorin its spine",
            ),
            (
                "dreadmaw_hold",
                "Dreadmaw Hold",
                "dungeon",
                "a hold in the northern crags named for what waits in its lowest hall",
            ),
            (
                "irondeep_mines",
                "Irondeep Mines",
                "dungeon",
                "the deepest iron mines in the world, dug too far and abandoned in a hurry",
            ),
        ],
    ),
    (
        "ashen_wastes",
        "Ashen Wastes",
        120,
        170,
        "volcanic-flats",
        "a scorched volcanic waste of lava-fields and standing fire",
        [
            (
                "moltenhold",
                "Moltenhold",
                "capital",
                "the molten capital, an obsidian city over a lake of living fire",
            ),
            (
                "cragfire",
                "Cinderfire",
                "town",
                "a town raised on cooling cinder, its forges never cold and never safe",
            ),
            (
                "ashen_monoliths",
                "Ashen Monoliths",
                "landmark",
                "black monoliths standing in the ash, older than the fire that scoured them",
            ),
            (
                "the_flamewrought_forge",
                "The Flamewrought Forge",
                "dungeon",
                "a forge-dungeon wrought in living flame at the heart of the wastes",
            ),
            (
                "the_scorched_gate",
                "The Scorched Gate",
                "dungeon",
                "a gate of black iron over a stair into the burning deep",
            ),
        ],
    ),
    (
        "korvash_highlands",
        "Korvash Highlands",
        150,
        200,
        "highland-moor",
        "storm-wracked highlands of crag-forts and a crater that should not be",
        [
            (
                "stonehelm",
                "Stonehelm",
                "city",
                "a helm of grey stone crowning the highest holdable crag in Korvash",
            ),
            (
                "highreach",
                "Highreach",
                "town",
                "the highest town a road reaches before the crags give out",
            ),
            (
                "thunderhold",
                "Thunderhold",
                "town",
                "a hold where the storms break first and hardest",
            ),
            (
                "shunderhold",
                "Shunderhold",
                "town",
                "a shattered sister-hold to Thunderhold, half its walls down the mountain",
            ),
            (
                "ancient_overlook",
                "Ancient Overlook",
                "landmark",
                "an overlook of old stone with all the southern world laid out below",
            ),
            (
                "korvash_crater",
                "Korvash Crater",
                "dungeon",
                "a crater the highlands grew around, a dungeon down into the wound",
            ),
        ],
    ),
    (
        "shattered_isles",
        "The Shattered Isles",
        180,
        230,
        "coastal-strand",
        "a broken archipelago of citadels and a maelstrom that eats the sea",
        [
            (
                "stormreach",
                "Stormreach",
                "city",
                "a storm-lashed island city, the last safe harbour of the broken sea",
            ),
            (
                "saltwind_harbor",
                "Saltwind Harbor",
                "port",
                "a wind-scoured harbour where every ship for the isles takes on crew",
            ),
            (
                "blackreef_citadel",
                "Blackreef Citadel",
                "dungeon",
                "a citadel on a black reef, a dungeon the tide half-drowns each night",
            ),
            (
                "the_maelstrom_rise",
                "The Maelstrom Rise",
                "landmark",
                "a violent maelstrom said to fall away to unknown depths",
            ),
        ],
    ),
    (
        "skyward_spires",
        "Skyward Spires",
        200,
        250,
        "highland-moor",
        "floating spires of arcane stone drifting the high eastern air",
        [
            (
                "aurelian_city",
                "Aurelian City",
                "capital",
                "a golden city on the greatest floating spire, capital of the sky",
            ),
            (
                "celestial_observatory",
                "Celestial Observatory",
                "landmark",
                "an observatory on a lone spire, reading a sky no one else can reach",
            ),
            (
                "the_spire_nexus",
                "The Spire Nexus",
                "dungeon",
                "a floating convergence of arcane energies, a dungeon of raw sky-power",
            ),
        ],
    ),
    (
        "the_deepreach",
        "The Deepreach",
        100,
        250,
        "volcanic-flats",
        "a vast underground realm of forge-cities and living crystal beneath the world",
        [
            (
                "deepforge_city",
                "Deepforge City",
                "capital",
                "the great underground forge-capital, lit by the fire it never lets go out",
            ),
            (
                "lumengrotto",
                "Lumengrotto",
                "town",
                "a grotto-town lit by luminous crystal, deep under the western reach",
            ),
            (
                "shadowfissure",
                "Shadowfissure",
                "town",
                "a town clinging to the walls of a fissure that drops past the light",
            ),
            (
                "the_crystal_labyrinth",
                "The Crystal Labyrinth",
                "dungeon",
                "a labyrinth of living crystal that grows new walls behind you",
            ),
        ],
    ),
    (
        "the_voidscar",
        "The Voidscar",
        250,
        300,
        "volcanic-flats",
        "a wound in the world where reality unravels and the oldest evil waits",
        [
            (
                "voidspire",
                "Voidspire",
                "city",
                "a spire of un-stone at the wound's edge, the last hold before the end",
            ),
            (
                "dark_expanse",
                "Dark Expanse",
                "landmark",
                "an expanse of dark where the ground gives out into unravelling",
            ),
            (
                "netharions_throne",
                "Netharion's Throne",
                "dungeon",
                "the seat of the oldest evil beneath the surface, the world's last dungeon",
            ),
            (
                "the_rifted_abyss",
                "The Rifted Abyss",
                "dungeon",
                "a rift into the abyss below the world, where reality comes apart",
            ),
        ],
    ),
]

# Inter-zone edges (from the map's roads, paths, and sea-routes). Each: (from_hub, to_hub, dir, route).
# Direction is the exit key on the from-hub; the reverse is auto-added on the to-hub.
LINKS = [
    ("veridia", "caeloria", "east", "road"),
    ("veridia", "duskwood_vale", "south", "path"),
    ("veridia", "frostspire_peaks", "north", "road"),
    ("caeloria", "eldryn_forest", "south", "road"),
    ("caeloria", "frostspire_peaks", "northeast", "path"),
    ("caeloria", "ashen_wastes", "southeast", "sea"),
    ("duskwood_vale", "eldryn_forest", "southeast", "path"),
    ("duskwood_vale", "zhaar_desert", "south", "path"),
    ("eldryn_forest", "zhaar_desert", "west", "path"),
    ("eldryn_forest", "ashen_wastes", "east", "road"),
    ("eldryn_forest", "korvash_highlands", "southwest", "path"),
    ("zhaar_desert", "korvash_highlands", "southeast", "sea"),
    ("frostspire_peaks", "thalorin", "east", "sea"),
    ("thalorin", "ashen_wastes", "south", "road"),
    ("thalorin", "shattered_isles", "east", "sea"),
    ("ashen_wastes", "xilnath_jungle", "east", "road"),
    ("ashen_wastes", "korvash_highlands", "south", "path"),
    ("xilnath_jungle", "shattered_isles", "north", "sea"),
    ("xilnath_jungle", "skyward_spires", "northeast", "sea"),
    ("korvash_highlands", "the_deepreach", "down", "tunnel"),
    ("korvash_highlands", "the_voidscar", "southeast", "sea"),
    ("shattered_isles", "skyward_spires", "east", "sea"),
    ("skyward_spires", "the_voidscar", "south", "sea"),
    ("the_deepreach", "the_voidscar", "east", "tunnel"),
]

_REV = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "northeast": "southwest",
    "southwest": "northeast",
    "northwest": "southeast",
    "southeast": "northwest",
    "up": "down",
    "down": "up",
}

# The biome each zone's wildlands fill uses (mostly the zone biome; the underground/void go volcanic).
KINDS_WITH_FOE = {"dungeon"}  # dungeons get a guardian foe; other places get a resident NPC

# Zones whose wilderness is an OPEN FIELD (content/blueprints/aethryn/fields.yaml, the World Topology
# Doctrine's trail-to-field zones), NOT a linear trail-chain. Their wildlands trail is skipped here so
# the generator never re-emits a trail that collides with the authored field -- the generator is the
# source of truth (Completion Law: fix the generator, not the output), so the skip lives here.
FIELD_BACKED = {
    "veridia",
    "duskwood_vale",
    "caeloria",
    "eldryn_forest",
    "frostspire_peaks",
    "zhaar_desert",
    "xilnath_jungle",
    "thalorin",
    "ashen_wastes",
    "korvash_highlands",
    "shattered_isles",
    "skyward_spires",
    "the_deepreach",
    "the_voidscar",
}

SP = "  "


def q(s: str) -> str:
    return s.replace('"', "'")


class MapCollision(RuntimeError):
    """Two routes claim one hub's direction, so one route would lose its return path."""


def _wire_hubs(
    links: list[tuple[str, str, str, str]],
    hub: dict[str, str],
    zone_ids: list[str],
) -> dict[str, dict[str, str]]:
    """Bind every inter-zone route to BOTH hubs, refusing any direction claimed twice.

    A plain assignment lets the second writer win. The loser keeps its forward exit and
    silently loses its return, which strands the player who walks through it. Refuse the
    map instead of emitting a world with a trap in it.
    """
    bound: dict[str, dict[str, str]] = {zid: {} for zid in zone_ids}
    claimed_by: dict[tuple[str, str], str] = {}
    collisions: list[str] = []

    for a, b, direction, _route in links:
        route = f"{a} <-> {b} ({direction})"
        for room, heading, target in ((a, direction, b), (b, _REV[direction], a)):
            held = claimed_by.get((room, heading))
            if held is not None and held != route:
                collisions.append(f"  {room} '{heading}' claimed by [{held}] and by [{route}]")
                continue
            claimed_by[(room, heading)] = route
            bound[room][heading] = hub[target]

    if collisions:
        raise MapCollision(
            "inter-zone routes collide; each line is a return path that would vanish:\n"
            + "\n".join(collisions)
        )
    return bound


def emit(out_root: Path | None = None) -> None:
    rooms: list[str] = [
        "# SEED: aethryn -- rooms.yaml  (GENERATED from the world map by tools/emit_map_world.py)",
        "# The canonical map of Aethryn: 14 zones, their settlements, dungeons, and landmarks,",
        "# connected by the map's roads and sea-routes. The FIRST room is the spawn (Veridia).",
        "",
    ]
    npcs: list[str] = [
        "# SEED: aethryn -- npcs.yaml  (GENERATED by tools/emit_map_world.py)",
        "# One resident per settlement/landmark and a guardian per dungeon; the wildlands",
        "# generator + bestiary fill the wilds between them.",
        "",
    ]
    zones_y: list[str] = [
        "# SEED: aethryn -- zones.yaml  (GENERATED by tools/emit_map_world.py)",
        "",
    ]
    wild: list[str] = [
        "# SEED: aethryn -- wildlands.yaml  (GENERATED by tools/emit_map_world.py)",
        "# One wilderness region per zone, filling the land between the map's places at the",
        "# zone's level band and biome (kernel/world/wildlands.py).",
        "",
    ]
    settles: list[str] = [
        "# SEED: aethryn -- settlements.yaml  (GENERATED by tools/emit_map_world.py)",
        "# Every town/landmark on the map (dungeons excluded). The townsfolk generator populates each",
        "# with residents and a merchant at the settlement's level band (kernel/world/townsfolk.py).",
        "",
    ]
    delves: list[str] = [
        "# SEED: aethryn -- dungeons.yaml  (GENERATED by tools/emit_map_world.py)",
        "# Every dungeon mouth on the map. The delve generator expands each into a multi-room descent",
        "# of escalating foes ending in a deep boss, at the dungeon's level band (kernel/world/delve.py).",
        "",
    ]
    ways: list[str] = [
        "# SEED: aethryn -- waystones.yaml  (GENERATED by tools/emit_map_world.py)",
        "# The 14 zone hubs, the nodes of the Waystone travel network. A player at any waystone may",
        "# pay a fee to travel to any other, at the destination's level band (kernel/world/travel.py).",
        "",
    ]

    # index the hub id per zone (the hub room = "<zoneid>" itself, the zone entrance)
    hub = {z[0]: z[0] for z in ZONES}
    # collect inter-zone exits per hub
    hub_exits: dict[str, dict[str, str]] = _wire_hubs(LINKS, hub, [z[0] for z in ZONES])

    for zid, zname, lo, hi, biome, blurb, places in ZONES:
        # --- the zone HUB room (its entrance / crossroads, a Waystone of the travel network) ---
        ways.append(f"{zid}:")
        ways.append(f"{SP}name: {zname}")
        ways.append(f"{SP}level: {lo}")
        ways.append("")
        place_names = ", ".join(p[1] for p in places)
        exits = dict(hub_exits[zid])
        for pid, pname, _kind, _pd in places:
            # a noun exit to each place keyed by a short slug of its name's first MEANINGFUL word
            # (skip leading articles, so "The Sunken Barrow" keys on `sunken`, not the useless `the`)
            words = [w for w in pname.split() if w.lower() not in ("a", "an", "the", "of")]
            key = (words[0] if words else pname.split()[0]).lower().strip("'").replace("'", "")
            if (
                key in exits
                or key in _REV
                or key in ("north", "south", "east", "west", "up", "down")
            ):
                key = pid  # fall back to the full id if the short key collides
            exits[key] = pid
        rooms.append(f"{zid}:")
        rooms.append(f"{SP}name: {zname}")
        rooms.append(f"{SP}desc: |-")
        rooms.append(
            f"{SP}{SP}The {zname} zone (levels {lo}-{hi}): {q(blurb)}. Within its bounds lie "
            f"{q(place_names)}. Roads and routes run on to the neighbouring lands."
        )
        rooms.append(f"{SP}exits:")
        for k, v in exits.items():
            rooms.append(f"{SP}{SP}{k}: {v}")
        rooms.append("")
        # hub resident (a zone warden / guide)
        _npc(
            npcs,
            f"{zid}_warden",
            f"a warden of {zname}",
            zid,
            f'"Welcome to {zname}, traveller. This is a levels {lo}-{hi} land. Mind the road, and the wilds off it."',
        )

        # --- each PLACE room, connected back to the hub ---
        member_rooms = [zid]
        for pid, pname, kind, pd in places:
            rooms.append(f"{pid}:")
            rooms.append(f"{SP}name: {pname}")
            rooms.append(f"{SP}desc: |-")
            rooms.append(
                f"{SP}{SP}{q(pd).capitalize()}. It lies within {zname} (levels {lo}-{hi}); "
                f"the zone road runs back out to the wider land."
            )
            rooms.append(f"{SP}exits:")
            rooms.append(f"{SP}{SP}out: {zid}")
            rooms.append("")
            member_rooms.append(pid)
            if kind in KINDS_WITH_FOE:
                _foe(npcs, f"{pid}_guardian", f"the guardian of {pname}", pid, hi, biome)
                if lo == 1:
                    # The starter zone's dungeon mouth also holds a FAIR, aggressive, winnable,
                    # NON-lethal prey: it strikes first (so the world still exercises proactive
                    # combat) but a fresh hero beats it and levels, and its death routes through the
                    # training-ground failsafe -- the on-ramp teaches combat instead of ending it,
                    # while the capstone guardian above merely bars the way (no longer aggressive).
                    _prey(npcs, f"{pid}_prey", "a barrow-rat", pid, ["rat", "barrow-rat", "vermin"])
                # a dungeon mouth the delve generator expands into a multi-room descent
                delves.append(f"{pid}:")
                delves.append(f"{SP}name: {pname}")
                delves.append(f'{SP}zone: "{zname}"')
                delves.append(f"{SP}level: {hi}")
                delves.append(f"{SP}biome: {biome}")
                delves.append("")
            else:
                _npc(
                    npcs,
                    f"{pid}_folk",
                    _resident(kind, pname),
                    pid,
                    f'"{q(pname)} keeps to itself, traveller, but you are welcome to pass through."',
                )
                # a town/landmark is a settlement the townsfolk generator will populate
                settles.append(f"{pid}:")
                settles.append(f"{SP}name: {pname}")
                settles.append(f'{SP}zone: "{zname}"')
                settles.append(f"{SP}level: {lo}")
                settles.append("")

        # --- the zone metadata area ---
        zones_y.append(f"{zid}_zone:")
        zones_y.append(f"{SP}name: {zname}")
        zones_y.append(f"{SP}rooms: [{', '.join(member_rooms)}]")
        zones_y.append(f"{SP}reset_mode: empty_only")
        zones_y.append(f"{SP}beats_between: 14")
        zones_y.append(f'{SP}region: "{zname}"')
        zones_y.append(f"{SP}level_min: {lo}")
        zones_y.append(f"{SP}level_max: {hi}")
        zones_y.append(f'{SP}biome: "{biome}"')
        zones_y.append("")

        # --- the zone's wilderness fill (wildlands region attached to the hub) ---
        # A field-backed zone grows an OPEN FIELD from fields.yaml instead of a trail, so skip its
        # trail here -- the authored field is its wilderness (kernel.world.fieldzone).
        if zid not in FIELD_BACKED:
            wild.append(f"{zid}_wild:")
            wild.append(f"{SP}name: The {zname} Wilds")
            wild.append(f'{SP}region: "{zname}"')
            wild.append(f"{SP}biome: {biome}")
            wild.append(f"{SP}attach: {zid}")
            wild.append(f"{SP}attach_dir: {_wild_dir(zid, hub_exits, places)}")
            wild.append(f"{SP}level_min: {lo}")
            wild.append(f"{SP}level_max: {hi}")
            wild.append(f"{SP}trail_length: {_fill_trail(zid)}")
            wild.append("")

    root = out_root if out_root is not None else BLUEPRINTS_ROOT / "aethryn"
    root.mkdir(parents=True, exist_ok=True)
    (root / "rooms.yaml").write_text("\n".join(rooms) + "\n")
    (root / "npcs.yaml").write_text("\n".join(npcs) + "\n")
    (root / "zones.yaml").write_text("\n".join(zones_y) + "\n")
    (root / "wildlands.yaml").write_text("\n".join(wild) + "\n")
    (root / "settlements.yaml").write_text("\n".join(settles) + "\n")
    (root / "dungeons.yaml").write_text("\n".join(delves) + "\n")
    (root / "waystones.yaml").write_text("\n".join(ways) + "\n")
    print(
        f"emitted {sum(1 for z in ZONES) + sum(len(z[6]) for z in ZONES)} rooms across {len(ZONES)} zones"
    )


def _resident(kind: str, name: str) -> str:
    role = {
        "capital": "a herald",
        "city": "a city-warden",
        "town": "a townsfolk",
        "village": "a villager",
        "port": "a harbourmaster",
        "landmark": "a keeper",
    }.get(kind, "a local")
    return f"{role} of {name}"


# Per-NPC hand-tuning the emitter reproduces (so a regen is non-destructive). These override or
# augment the generic townsfolk/guardian output for the few NPCs given individual character by hand:
# a lived-in wander on the starter towns, and telegraphed specials, raid-gating, and regional armour
# drops on the bosses that anchor progression. Keeping them here means the map source stays the one
# source of truth: `python tools/emit_map_world.py` rebuilds the world exactly as committed.
_FOLK_WANDER = {"greenhold_folk", "riverbend_folk", "sunmeadow_folk"}
_WANDER_LINE = "wander: true  # ambient: strolls the town on the beat (world life)"

_FOE_TUNING: dict[str, dict[str, Any]] = {
    "the_black_hollow_guardian": {
        "trailing": [
            "inflicts: {status: daze, chance: 3, beats: 1}"
            "  # a dark, reeling blow costs the hero an action",
            'special: {telegraph: "The guardian draws the hollow\'s dark in around its fists", '
            "mult: 2, cadence: 3}",
        ],
    },
    "glacial_bastion_guardian": {
        "name_comment": "  # mid-tier: drops the leg + feet armor for the open world",
        "drops": "[greater_healing_draught, ashlord_greaves, emberstride_boots]",
    },
    "dreadmaw_hold_guardian": {
        "trailing": [
            "special: {kind: mend, telegraph: \"The dreadmaw's torn flesh writhes, "
            'knitting itself whole", heal: 100, cadence: 3}'
            "  # a flesh-maw that regrows: enraged, it knits its wounds -- a DPS race",
        ],
    },
    "heart_of_xilnath_guardian": {
        "trailing": [
            "inflicts: {status: venom, chance: 2, damage: 12, ticks: 4}"
            "  # its bite leaves a venom that saps you",
            'special: {telegraph: "The guardian rears, venom beading along its fangs", '
            "mult: 2, cadence: 3}",
        ],
    },
    "netharions_throne_guardian": {
        "raid": "  # the final weekly raid: Netharion's Throne, the apex of the climb",
        "drops": "[greater_healing_draught, abyssal_legguards, abyssal_sabatons]",
        "trailing": [
            'special: {kind: drain, telegraph: "Netharion bares its fangs and hungers", '
            "mult: 2, cadence: 3}"
            "  # vampiric apex mechanic: its unleash drinks your wound to heal -- mitigate/interrupt",
        ],
    },
    "the_rifted_abyss_guardian": {
        "raid": "  # an apex weekly raid: bring a party and the trinity, not a solo lap",
        "drops": "[greater_healing_draught, abyssal_legguards, abyssal_sabatons]",
    },
}


def _npc(out: list[str], nid: str, name: str, room: str, line: str) -> None:
    out.append(f"{nid}:")
    out.append(f"{SP}name: {name}")
    out.append(
        f"{SP}keywords: [{', '.join(w.strip(chr(39)) for w in name.split() if w not in ('a', 'an', 'of', 'the'))}]"
    )
    out.append(f"{SP}location: {room}")
    out.append(f"{SP}dialogue:")
    out.append(f"{SP}{SP}- {line}")
    if nid in _FOLK_WANDER:
        out.append(f"{SP}{_WANDER_LINE}")
    out.append("")


def _prey(out: list[str], nid: str, name: str, room: str, keywords: list[str]) -> None:
    """A fair, aggressive, WINNABLE, non-lethal starter creature. It strikes first (so the world
    still exercises proactive_combat) but a fresh hero can beat it and level; with no `lethal` flag
    its death routes through the training-ground failsafe, so the on-ramp teaches combat rather than
    ending a level-1 run. Low level + low hp/atk keep it winnable for a brand-new character."""
    out.append(f"{nid}:")
    out.append(f"{SP}name: {name}")
    out.append(f"{SP}keywords: [{', '.join(keywords)}]")
    out.append(f"{SP}location: {room}")
    out.append(f"{SP}dialogue:")
    out.append(f"{SP}{SP}- The {keywords[0]} bares its teeth and darts at your ankles.")
    out.append(f"{SP}aggressive: true")
    out.append(f"{SP}hp: 18")
    out.append(f"{SP}atk: 3")
    out.append(f"{SP}level: 2")
    out.append(f"{SP}tier: normal")
    out.append("")


def _foe(out: list[str], nid: str, name: str, room: str, level: int, biome: str) -> None:
    el = {
        "glacier-waste": "ICE",
        "volcanic-flats": "FIR",
        "living-jungle": "PSN",
        "salt-desert": "ERT",
        "coastal-strand": "WTR",
    }.get(biome, "DRK")
    tuning = _FOE_TUNING.get(nid, {})
    out.append(f"{nid}:")
    out.append(f"{SP}name: {name}{tuning.get('name_comment', '')}")
    out.append(f"{SP}keywords: [guardian, {room.split('_')[0]}]")
    out.append(f"{SP}location: {room}")
    out.append(f"{SP}dialogue:")
    out.append(f"{SP}{SP}- The guardian bars the way into {name.split('of ')[-1]}.")
    out.append(f"{SP}hp: {120 + level * 6}")
    out.append(f"{SP}atk: {12 + level // 2}")
    # A mouth guardian BARS the way (defensive) -- it is not aggressive, so it never passively
    # kills a lower-level hero who wanders to a zone's capstone-dungeon mouth (the on-ramp fix).
    # It still "looks hostile" and fights to the death when struck; entering the delve is a choice.
    out.append(f"{SP}attack_element: {el}")
    out.append(f"{SP}level: {level}")
    out.append(f"{SP}tier: boss")
    if "raid" in tuning:
        out.append(f"{SP}raid: true{tuning['raid']}")
    out.append(f"{SP}lethal: true")
    out.append(f"{SP}drops: {tuning.get('drops', '[greater_healing_draught]')}")
    out.append(f"{SP}loot: {{ember_shard: 5, nothing: 2}}")
    for line in tuning.get("trailing", []):
        out.append(f"{SP}{line}")
    out.append("")


# Wilderness-fill target rooms per zone, sized to the prompt's scaling guidance by region type
# (forest/mountain/desert/underground get the largest fills; the sky and starter get less). The
# wildlands generator turns each target into a connected, biome-varied trail-network; a single
# region's rooms ~= trail_length x 1.75 (branch_every 4, branch_length 3).
_ZONE_FILL = {
    "veridia": 1400,  # starter: walkable, not overwhelming
    "duskwood_vale": 3000,  # forest
    "caeloria": 2400,  # heartland plains
    "eldryn_forest": 4000,  # ancient forest
    "frostspire_peaks": 4000,  # mountain range
    "zhaar_desert": 4000,  # desert
    "xilnath_jungle": 4000,  # jungle
    "thalorin": 4000,  # mountains + mines
    "ashen_wastes": 3000,  # volcanic
    "korvash_highlands": 4000,  # highlands
    "shattered_isles": 3000,  # island chain
    "skyward_spires": 2000,  # floating isles (sparser)
    "the_deepreach": 5000,  # underground kingdom (largest)
    "the_voidscar": 3000,  # endgame
}


def _fill_trail(zid: str) -> int:
    """Trail length for a zone's wilderness fill, from its target room count (min 18)."""
    return max(18, int(_ZONE_FILL.get(zid, 1400) / 1.75))


def _wild_dir(zid: str, hub_exits: dict, places) -> str:
    """Pick a free direction on the hub for the wilderness attach (not used by a link or a place)."""
    used = set(hub_exits[zid])
    for d in (
        "north",
        "south",
        "east",
        "west",
        "up",
        "northeast",
        "northwest",
        "southeast",
        "southwest",
        "down",
    ):
        if d not in used:
            return d
    return "in"


if __name__ == "__main__":
    emit()
