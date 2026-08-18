"""CARD: wildlands -- procedurally grow coherent wilderness regions to world-generation scale.

Hand-authoring tens of thousands of wilderness rooms would be repetitive filler; this is a
DETERMINISTIC generator (a sibling of kernel.world.spiral) that expands a compact region config
(seeds/<world>/wildlands.yaml) into a connected, biome-varied trail-network of rooms. Every
generated room carries one ambient creature (so no room ships empty) and belongs to a named area
with region / level-band / biome metadata. The output is ordinary Room / Npc / Zone data, run
through the SAME loader gates as hand-authored content -- the world stays data, the generator is
only its factory.

No randomness: every choice is by index, so the whole expansion is reproducible from the compact
config (regenerate the identical world from any commit). Layouts are branching trails with glade
pockets and loop-backs -- NOT a flat square grid -- and descriptions are composed by structured
variation (biome vocabulary x terrain feature x directional context), not random adjective swaps,
so adjacent rooms feel related and distant regions feel different at scale.

`generate_wildlands(configs, existing_rooms)` returns (rooms, npcs) to merge into the world; each
config's `attach` room grows one exit onto the region's trail-head. `wildlands_zones(configs)`
returns the matching metadata areas. Both are pure, so the expansion is testable without a boot.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from kernel.world.bestiary import make_beast, make_notable
from kernel.world.seed import BlueprintError, Npc, Room, Zone

# CODEFORGE_WILD_SCALE multiplies every region's trail_length at load, so ONE seed scales from a
# laptop/demo world to an MMO world without re-authoring the config. Default 1 (the seed's shipped
# size, safe for CI and the free-tier demo); set it higher on capable hardware -- aethryn reaches
# ~1,000,000 rooms at scale 19 (~1.9 GB / ~22 s boot). Populate density is separate (guardians are
# capped per region), so scaling adds land, not bounty-board flood.
_WILD_SCALE_ENV = "CODEFORGE_WILD_SCALE"

# The compass a trail can run and its reverse, so every generated exit is reciprocal.
_OPPOSITE = {
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
# Branches leave the trail on alternating flanks, so a region reads as a wide land, not a corridor.
_FLANKS = ("east", "west", "northeast", "northwest", "southeast", "southwest")

# The most named guardians one region may seed, however large. Each mints a hunt bounty, so this
# bounds the board (and boot cost) even if a zone's trail runs to thousands of rooms.
_NOTABLE_CAP = 16

# Gather nodes: roughly one room in `_GATHER_EVERY` carries a harvestable material (kernel.world.
# gather), so a forager always has somewhere to work. Ore biomes occasionally yield a drowned INGOT
# (the rarer crafting input); everywhere else yields the common EMBER-SHARD. Both feed real recipes.
_GATHER_EVERY = 5
_ORE_BIOMES = frozenset({"volcanic-flats", "glacier-waste", "highland-moor", "salt-desert"})


# A biome-specific HERB every region yields, on top of the common ember-shard (and the ore-biome
# ingot). Each herb is a seed item (aethryn/items.yaml) that feeds a real recipe (recipes.yaml), so
# a gather node can clone it like ember_shard and the forage board + crafting bench gain variety.
_BIOME_HERB: dict[str, str] = {
    "temperate-meadow": "meadowfoil",
    "wild-forest": "fernshade",
    "highland-moor": "moorbell",
    "coastal-strand": "saltkelp",
    "glacier-waste": "frostmoss",
    "volcanic-flats": "cinderroot",
    "living-jungle": "vinesilk",
    "salt-desert": "dustbloom",
}


def _gather_node(biome: str, idx: int) -> str | None:
    """The material a room offers to gather, or None (most rooms). Deterministic by index. A node
    yields the ore-biome ingot, then the biome's herb, else the common ember-shard."""
    if idx % _GATHER_EVERY != 0:
        return None
    if biome in _ORE_BIOMES and idx % (_GATHER_EVERY * 3) == 0:
        return "hollow_ingot"
    herb = _BIOME_HERB.get(biome)
    if herb and idx % (_GATHER_EVERY * 2) == 0:
        return herb
    # Ore biomes also quarry RAW ORE (the smithing refinement chain's raw tier), on the half of
    # their common nodes ember-shard does not claim -- so ore, ingot, herb and shard all coexist.
    if biome in _ORE_BIOMES and idx % (_GATHER_EVERY * 6) == _GATHER_EVERY * 5:
        return "raw_ore"
    return "ember_shard"


def gatherable_materials(biome: str) -> tuple[str, ...]:
    """The material prototypes a biome's gather nodes can yield -- the forageable inputs a region
    offers (kernel.world.forage builds contracts from these). Mirrors `_gather_node`'s choices: the
    common ember-shard, the ore-biome ingot and raw ore, and the biome's own herb."""
    mats = ["ember_shard"]
    if biome in _ORE_BIOMES:
        mats.extend(("hollow_ingot", "raw_ore"))
    herb = _BIOME_HERB.get(biome)
    if herb:
        mats.append(herb)
    return tuple(mats)


def biome_spoil(biome: str) -> str | None:
    """The biome's signature material -- the herb its gather nodes yield, its forage board asks for,
    and (via the ambient loot table) its wildlife drops. One source of truth for all three, so a
    meadow kill gives the same meadowfoil a forager cuts and the Greenhold trader buys. None for an
    unknown biome."""
    return _BIOME_HERB.get(biome)


# Per-biome ROOM vocabulary: a lead sentence, terrain FEATURES (composed by index so adjacent rooms
# differ but relate), and LANDMARKS (a branch-end payoff). The ambient CREATURES come from the
# procedural bestiary (kernel.world.bestiary), keyed by the same biome name -- kept separate so life
# and land each vary on their own axis. The lead x feature x landmark x direction space is large
# enough to avoid near-identical rooms.
_BIOMES: dict[str, dict[str, Any]] = {
    "temperate-meadow": {
        "lead": "Open meadowland rolls under a wide, kind sky",
        "features": [
            "long grass hisses in the wind and ember-poppies nod along the path",
            "a shallow brook cuts the turf, cold and clear over cinder-gravel",
            "a lone forge-oak stands sentinel, its bark warm to the touch",
            "wildflower banks give onto a stretch of sun-baked cart-ruts",
            "a drystone wall, older than the Rekindling, divides two green folds",
            "skylarks climb over a hollow where the grass grows tall and secret",
            "a hedgerow thick with berries walls the trail on the windward side",
            "the ground dips to a boggy seep bright with marsh-marigold",
        ],
        "landmarks": [
            "a mossy standing-stone leans here, a wayfarer's mark from the old kingdom",
            "a ring of ember-mushrooms glows faint in a grass hollow",
            "a broken plough rusts where a farm once was, the field gone to meadow",
        ],
        "atmospheres": [
            "the air is sweet with crushed grass and the drone of bees",
            "a warm wind combs the grass into long silver waves",
            "somewhere unseen a lark climbs and will not stop singing",
            "the sun lies heavy and gold and the whole field seems to breathe",
            "cloud-shadows drift across the green like slow grazing beasts",
            "the far hedges shimmer in the heat and a dog barks once, a mile off",
            "dusk comes soft here, and the first ember-moths wake in the dew",
            "rain has just passed, and the turf steams and smells of iron and clover",
            "the quiet runs deep enough to hear your own blood, and nothing means you harm",
        ],
    },
    "wild-forest": {
        "lead": "The wood closes overhead into a green, breathing dusk",
        "features": [
            "roots knuckle across the deer-path and wild ember pools in the hollows",
            "a fallen giant of a tree bridges a gully thick with fern",
            "birch-light dapples a clearing loud with unseen wings",
            "the trail threads between trunks too wide to reach around",
            "a stream chuckles unseen below a bank of hart's-tongue",
            "bramble arches close, and the air goes still and watchful",
            "a stand of ember-pine drops warm needles underfoot",
            "toadstools ring a stump where the wood grows quiet and old",
        ],
        "landmarks": [
            "a hunter's blind rots in the crook of an old oak, long abandoned",
            "a spring wells up cold and clear beneath a mossed rock-face",
            "a shrine-post to the wood-warden leans, its offerings gone to seed",
        ],
        "atmospheres": [
            "the air hangs green and close, and every sound comes back changed",
            "light falls in coins through the canopy and moves when you do",
            "something large shifts its weight far off, and then holds very still",
            "the wood smells of wet bark, cold sap, and older, darker growth",
            "birdsong stops as you pass and starts again once you are gone",
            "a warm wind moves the high branches though the floor stays dead calm",
            "the dusk here never fully lifts, and the shadows keep their own counsel",
            "resin and rot mingle sweet and sharp, and the ferns drip in the hush",
            "you have the sense of being counted, and not by anything kind",
        ],
    },
    "highland-moor": {
        "lead": "Bare high moor rolls away under a scoured grey sky",
        "features": [
            "heather and gorse clutch the thin soil over grey Forge-stone",
            "the wind never stops, and the path is marked by cairns alone",
            "a peat-cut gapes black and wet beside the trail",
            "a tarn lies steel-still in a fold of the hill, reflecting nothing",
            "old charge hums faint from a buried Forgework under the turf",
            "a tumble of frost-split boulders makes a maze of the way",
            "sheep-tracks web the slope where no shepherd has walked in an age",
            "the moor gives onto a scarp with the whole country laid out below",
        ],
        "landmarks": [
            "a ring of standing stones keeps its silence on the hill's crown",
            "a ruined bothy offers cold shelter, its hearth long dead",
            "a boundary-cairn of the old marches stands taller than a man",
        ],
        "atmospheres": [
            "the wind never falls, and it carries the smell of peat and cold stone",
            "cloud tears low over the tops and the light changes minute to minute",
            "a curlew cries somewhere out in the grey and nothing answers",
            "the cold gets into the bones out here, patient and unhurried",
            "mist rolls up out of the hollows and swallows the cairns one by one",
            "the silence is huge, broken only by the wind worrying the heather",
            "rain comes sideways and stinging, then clears to a hard clean light",
            "the ground gives spongy underfoot and the air tastes of iron and rain",
            "you feel very small here, and very watched, though nothing shows itself",
        ],
    },
    "coastal-strand": {
        "lead": "The trail runs the strand where the Cooling-Sea meets the land",
        "features": [
            "grey shingle grinds underfoot and salt-wind carries the gulls' cry",
            "tide-pools mirror the sky between fingers of black rock",
            "marram grass binds the dunes above a long pale beach",
            "a wrack-line of drowned Forgework and kelp marks the last high tide",
            "a freshwater stream fans out across the sand to the sea",
            "sea-caves gape in the low cliff, breathing cold at the ebb",
            "a spit of shingle runs out to a rock the tide cuts off",
            "salt-marsh gives onto mudflats bright with wading birds",
        ],
        "landmarks": [
            "a beacon-cairn stands on the point, its old fire-basket rusted through",
            "a fisher's upturned hull rots above the tideline, a shelter of sorts",
            "a shrine to the drowned keeps a guttering lamp against the sea",
        ],
        "atmospheres": [
            "the air is thick with salt and the endless grinding of the surf",
            "gulls wheel and complain overhead and the wind never lets up",
            "the tide is turning, and the whole shore mutters and shifts with it",
            "spray hangs in the cold air and beads on everything the wind touches",
            "far out, a bell-buoy tolls slow over the grey heave of the sea",
            "the light off the water is hard and bright and edged with cold",
            "kelp and brine and old tar hang heavy, and something drowned besides",
            "fog rolls in off the Cooling-Sea and the land ends ten paces off",
            "the sea says the same thing over and over, and it is not comforting",
        ],
    },
    "glacier-waste": {
        "lead": "A white waste of old ice stretches flat and blinding",
        "features": [
            "the wind scours loose snow in hissing ribbons over blue ice",
            "a pressure-ridge heaves the floe into a wall of frozen slabs",
            "a frozen well drops black and bottomless beside the trail",
            "rime-crystal grows in the cold seams, sharp as struck glass",
            "an Emberwright work stands half-swallowed and perfect under the ice",
            "the floe cracks and settles somewhere far off, a sound like a bell",
            "a field of ice-spires throws long blue shadows across the snow",
            "the white gives onto a frozen shore where the sea itself is stopped",
        ],
        "landmarks": [
            "a cairn of frost-marks keeps a dead beacon on the highest ridge",
            "a Silent Anvil shrine-post forbids the touching of what the ice keeps",
            "a warm-camp's dead fire-ring marks where salvagers wintered and left",
        ],
        "atmospheres": [
            "the cold is a physical weight, and the air burns going down",
            "the light off the ice is blinding and casts no honest shadow",
            "the silence is total, until the floe groans somewhere beneath you",
            "wind-driven crystal stings the skin and glitters in the flat glare",
            "the horizon and the sky are the same white, with no line between",
            "your breath freezes hard and the world holds utterly still",
            "far off the ice cracks like a shot and the echo runs for a mile",
            "the cold smells of nothing at all, which is its own kind of warning",
            "nothing lives here that should, and you feel the ice waiting you out",
        ],
    },
    "volcanic-flats": {
        "lead": "Black obsidian flats crack with the glow of the fire below",
        "features": [
            "a slow river of Forgelight-lit lava steams across the shelf",
            "cinder-fall drifts from the sky and crunches underfoot",
            "an ash-dune shifts against a wall of cooled black glass",
            "a working vent breathes heat and sulphur from the world's floor",
            "emberglass sets bright in the cracks where the fire last ran",
            "a cooling shelf rings hollow, the crust thin over the heat",
            "obsidian spires throw knife-edged shade across the glowing ground",
            "the flats give onto a caldera-rim above a lightning-lit pit",
        ],
        "landmarks": [
            "a Kollkin pilgrim-cairn marks a way to the raw Ember below",
            "a slagged ruin of a Forger who reached too hot stands half-melted",
            "a Vent-Forge waymark points the safe line across the burning ground",
        ],
        "atmospheres": [
            "the heat comes up through the soles and the air stinks of sulphur",
            "the ground ticks and creaks as the cooling crust settles over the fire",
            "a red glow pulses from every crack, keeping time with something deep",
            "ash sifts down out of a brown sky and grits between the teeth",
            "the air is too hot to breathe deep and tastes of iron and burning",
            "far off a vent lets go with a roar and a fountain of embers",
            "the light is the colour of a forge at work, and never fully dark",
            "heat-haze bends the black spires until they seem to walk",
            "the whole plain feels one breath from waking, and it knows you are here",
        ],
    },
    "living-jungle": {
        "lead": "The living wild presses in, green and warm and awake",
        "features": [
            "ember-blooms light the understory and the air thickens to breathing",
            "roots choose their own courses across a game-trail of black mud",
            "a strangler-vine has closed its slow fist around a fallen trunk",
            "a river runs uphill where the old Forgework holds a forgotten slope",
            "canopy-mist beads on broad leaves and drips a warm, steady rain",
            "a swarm of ember-moths lifts from a bank of luminous fungus",
            "the trail fords a warm black pool loud with unseen frogs",
            "the green gives onto a grove that watches you pass, and remembers",
        ],
        "landmarks": [
            "a Deeprooted witness-stone grows in the living bark of a wayside tree",
            "a poacher's ruin lies where someone tried to harvest the wild and was eaten",
            "a hidden grove-shrine breathes a green quiet older than the Reaches",
        ],
        "atmospheres": [
            "the air is a warm wet weight, loud with insects and unseen throats",
            "everything drips, and the green light comes from the leaves themselves",
            "something calls, is answered, and the whole canopy falls abruptly silent",
            "the smell is sweet rot and ember-bloom and a green so thick it cloys",
            "the heat presses down and the growth seems to lean in to watch",
            "a warm rain starts without warning and stops the same way",
            "the wild here feels awake in a way that has nothing to do with beasts",
            "luminous spores drift on the heavy air and light the black beneath the leaves",
            "you are certain, without proof, that the grove remembers your face",
        ],
    },
    "salt-desert": {
        "lead": "A bleached salt-waste glares white under an enormous sky",
        "features": [
            "cold grey cinder drifts in dunes over a crust of dead salt",
            "the salt-flat crazes over the ghost of a drowned canal",
            "a glass crater marks where the Unforging struck and left black glass",
            "salvage-poles lean along the only walkable line across the waste",
            "the wind erases the trail behind you and offers no landmark ahead",
            "a dry sea-basin glares to its far rim, white and utterly still",
            "wind-carved mesas of grey rock throw the day's only shade",
            "the waste gives onto the Ashline, where the made world simply stops",
        ],
        "landmarks": [
            "an Ashborn waymoot keeps a water-cache by unbreakable road-code",
            "a salvage-clan marker leans over a dig gone down into the salt",
            "the last Ashborn stone stands before the un-ness, hung with tokens",
        ],
        "atmospheres": [
            "the heat is a hammer and the light off the salt is merciless",
            "the wind carries fine grey grit and the taste of old ash",
            "the silence is enormous, and the sky goes on past all reason",
            "heat-devils spin up off the flat and walk the shimmering distance",
            "nothing moves but the mirage, and the mirage moves wrong",
            "the cold comes fast when the sun drops, and the salt ticks as it cools",
            "the air is bone-dry and every breath pulls the water from you",
            "far off the un-ness hums at the edge of hearing, or seems to",
            "the waste offers no landmark and no mercy, and does not notice you at all",
        ],
    },
}


def _biome(name: str) -> dict[str, Any]:
    if name not in _BIOMES:
        raise BlueprintError(
            f"wildlands biome {name!r} is unknown. Known biomes: {sorted(_BIOMES)}."
        )
    return _BIOMES[name]


def _wild_scale() -> float:
    """The world-scale multiplier from CODEFORGE_WILD_SCALE (default 1). Fails loud on a bad value;
    must be >= 1 (a seed's shipped size is its floor -- scaling only ever grows the world)."""
    raw = os.getenv(_WILD_SCALE_ENV, "1")
    try:
        scale = float(raw)
    except ValueError:
        raise BlueprintError(f"{_WILD_SCALE_ENV} must be a number, got {raw!r}.") from None
    if scale < 1:
        raise BlueprintError(
            f"{_WILD_SCALE_ENV} must be >= 1 (scaling only grows the world), got {raw!r}."
        )
    return scale


def load_wildlands_config(path: Path) -> list[dict[str, Any]] | None:
    """Read a seed's optional wildlands.yaml (a mapping of region-id -> config). Returns None when
    the seed ships none. Fails loud on a malformed region: required fields, a real biome,
    a sane level band (1..300, min<=max), positive sizes, and a known trail direction.

    Every region's trail_length is multiplied by CODEFORGE_WILD_SCALE (default 1), so the same seed
    scales from a demo world to an MMO world by env alone (see `_wild_scale`)."""
    if not path.exists():
        return None
    scale = _wild_scale()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise BlueprintError("wildlands.yaml must be a mapping of region-id to config.")
    configs: list[dict[str, Any]] = []
    for rid, cfg in raw.items():
        if not isinstance(cfg, dict):
            raise BlueprintError(f"wildlands region {rid!r} must be a mapping of config keys.")
        # notable_every: a NAMED guardian foe every N generated rooms (a hunt target that mints a
        # bounty), 0 = none. Default on, so every wildlands zone carries MMO-density hunt content.
        merged = {"branch_every": 3, "branch_length": 3, "notable_every": 220, **cfg, "id": rid}
        required = (
            "name",
            "region",
            "biome",
            "attach",
            "attach_dir",
            "level_min",
            "level_max",
            "trail_length",
        )
        missing = [k for k in required if k not in merged]
        if missing:
            raise BlueprintError(f"wildlands region {rid!r} missing key(s): {', '.join(missing)}.")
        _biome(merged["biome"])  # validate the biome exists
        if merged["attach_dir"] not in _OPPOSITE:
            raise BlueprintError(
                f"wildlands region {rid!r}: attach_dir {merged['attach_dir']!r} is not a direction."
            )
        for key in ("level_min", "level_max", "trail_length", "branch_every", "branch_length"):
            value = merged[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise BlueprintError(
                    f"wildlands region {rid!r}: {key!r} must be a positive integer, got {value!r}."
                )
        if not merged["level_min"] <= merged["level_max"] <= 300:  # noqa: PLR2004
            raise BlueprintError(
                f"wildlands region {rid!r}: need level_min <= level_max <= 300 "
                f"(got {merged['level_min']}-{merged['level_max']})."
            )
        ne = merged["notable_every"]
        if not isinstance(ne, int) or isinstance(ne, bool) or ne < 0:
            raise BlueprintError(
                f"wildlands region {rid!r}: 'notable_every' must be a non-negative int (0 = off), "
                f"got {ne!r}."
            )
        # Scale the region AFTER validating its authored size, so a bad base fails clearly and the
        # env only ever multiplies a known-good value (floored at 1 room).
        merged["trail_length"] = max(1, round(merged["trail_length"] * scale))
        configs.append(merged)
    return configs


def _band_level(cfg: dict[str, Any], step: int, span: int) -> int:
    """A level in the region's band, deepening from min to max as `step` runs 0..span, so the
    wilderness gets a little harder the further from the attach point (a real gradient)."""
    lo, hi = cfg["level_min"], cfg["level_max"]
    if span <= 1:
        return lo
    return lo + (hi - lo) * min(step, span - 1) // (span - 1)


def _ambient(cfg: dict[str, Any], room: str, idx: int, level: int) -> tuple[str, Npc]:
    """One ambient creature for a generated room, from the procedural BESTIARY (classes of beasts
    x biome x size x element -- thousands of distinct, level-scaled foes) so no room ships empty and
    the wilds never feel like the same handful of animals. Deterministic by index."""
    label = f"{cfg['id']}_beast_{idx}"
    return label, make_beast(cfg["biome"], level, idx, room)


def _describe(
    cfg: dict[str, Any], idx: int, back_dir: str, on_dir: str | None, landmark: str | None
) -> str:
    """Compose a room description by structured variation: the biome lead, an indexed terrain
    feature, an indexed atmosphere (a second, independent axis of sound/light/weather/mood), a
    directional cue back and onward, and (at a branch-end) a landmark. Feature and atmosphere are
    each indexed by the SAME room index but at co-prime pool sizes (8 features x 9 atmospheres), so
    by the Chinese remainder theorem the (feature, atmosphere) pair cycles over all 72 combinations
    before repeating -- 9x the old variety from one extra pool, with no random state. A per-region
    phase offset (a deterministic char-sum of the region id, immune to PYTHONHASHSEED) rotates the
    starting point, so two regions of the SAME biome do not read identically at the same index --
    without it, every region restarted at index 0 and collapsed onto the same handful of rooms.
    Adjacent rooms differ on both axes; distant biomes read wholly different."""
    biome = _biome(cfg["biome"])
    phase = sum(ord(c) for c in str(cfg["id"]))  # per-region offset; distinct regions decorrelate
    feature = biome["features"][(idx + phase) % len(biome["features"])]
    atmosphere = biome["atmospheres"][(idx + phase) % len(biome["atmospheres"])]
    lines = [f"{biome['lead']}: {feature}; {atmosphere}."]
    if landmark:
        lines.append(f"{landmark[0].upper()}{landmark[1:]}.")
    cue = f"The way runs back {back_dir}"
    if on_dir:
        cue += f", and on {on_dir}"
    lines.append(cue + ".")
    return " ".join(lines)


def _region(cfg: dict[str, Any], claimed: set[str]) -> tuple[dict[str, Room], dict[str, Npc]]:
    """Grow one region: a main trail off the attach room, with periodic flank-branches ending in a
    landmark, and every generated room carrying one ambient creature. Returns (rooms, npcs)."""
    rid = cfg["id"]
    on = cfg["attach_dir"]
    back = _OPPOSITE[on]
    L = cfg["trail_length"]  # noqa: N806
    every = cfg["branch_every"]
    blen = cfg["branch_length"]
    rooms: dict[str, Room] = {}
    npcs: dict[str, Npc] = {}
    idx = 0  # a global index across the region, driving level gradient + description variation
    seq = 0  # count of named guardians placed so far, for their titles and the boss cadence

    # Total trail-equivalent span for the level gradient (trail + its branches).
    span = L + (L // every) * blen
    # A named guardian every `notable_every` rooms, bounded so a huge region cannot flood the bounty
    # board (each guardian mints a hunt contract). 0/absent = off (ambient-only). The loader turns
    # it on by default, so a hand-built config (a test) stays quiet unless it opts in.
    notable_every = cfg.get("notable_every", 0)
    max_notables = min(L // notable_every, _NOTABLE_CAP) if notable_every else 0

    def add(label: str, name: str, desc: str, exits: dict[str, str]) -> None:
        nonlocal idx, seq
        if label in claimed or label in rooms:
            raise BlueprintError(f"wildlands region {rid!r} would collide on room label {label!r}.")
        room = Room(name=name, desc=desc, exits=exits)
        material = _gather_node(cfg["biome"], idx)  # some rooms carry a harvestable node
        if material:
            room["node"] = material
        rooms[label] = room
        level = _band_level(cfg, idx, span)
        if notable_every and idx and idx % notable_every == 0 and seq < max_notables:
            npcs[f"{rid}_lord_{seq}"] = make_notable(cfg["biome"], level, idx, label, seq)
            seq += 1
        else:
            beast_label, beast = _ambient(cfg, label, idx, level)
            npcs[beast_label] = beast
        idx += 1

    trail = [f"{rid}_t{i}" for i in range(1, L + 1)]
    for i, room in enumerate(trail):
        exits: dict[str, str] = {}
        exits[back] = cfg["attach"] if i == 0 else trail[i - 1]
        if i + 1 < L:
            exits[on] = trail[i + 1]
        # A flank branch every `every` rooms (not on the last trail room), alternating sides. The
        # flank must never reuse the trail's own axis (`on`/`back`) or it would overwrite the spine
        # and orphan the rooms ahead -- so branches leave strictly perpendicular to the trail.
        branch_head: str | None = None
        flank: str | None = None
        flanks = [d for d in _FLANKS if d != on and d != back]  # noqa: PLR1714
        if i > 0 and i % every == 0 and i + 1 < L:
            flank = flanks[(i // every) % len(flanks)]
            branch_head = f"{rid}_b{i}_1"
            exits[flank] = branch_head
        name = f"{cfg['name']} - {_place_word(cfg, i)}"
        add(room, name, _describe(cfg, i, back, on if i + 1 < L else None, None), exits)
        if branch_head and flank is not None:
            _branch(cfg, i, flank, room, blen, claimed, rooms, npcs, add)
    return rooms, npcs


def _branch(  # noqa: PLR0917
    cfg: dict[str, Any],
    trail_i: int,
    flank: str,
    trunk: str,
    blen: int,
    claimed: set[str],  # noqa: ARG001
    rooms: dict[str, Room],
    npcs: dict[str, Npc],  # noqa: ARG001
    add: Any,
) -> None:
    """A short side-trail off the main way, ending in a landmark pocket -- so the region reads as a
    wide land with places to find, not a corridor. Runs on `flank`, reverses to the trunk."""
    rid = cfg["id"]
    back = _OPPOSITE[flank]
    chain = [f"{rid}_b{trail_i}_{j}" for j in range(1, blen + 1)]
    for j, room in enumerate(chain):
        exits: dict[str, str] = {}
        exits[back] = trunk if j == 0 else chain[j - 1]
        last = j + 1 == blen
        if not last:
            exits[flank] = chain[j + 1]
        landmark = None
        if last:
            biome = _biome(cfg["biome"])
            landmark = biome["landmarks"][(trail_i + j) % len(biome["landmarks"])]
        name = f"{cfg['name']} - {_place_word(cfg, trail_i * 7 + j + 3)}"
        add(
            room,
            name,
            _describe(cfg, trail_i * 3 + j + 1, back, flank if not last else None, landmark),
            exits,
        )
        # A single WAYSHRINE per region, set at its first branch's landmark pocket: a rare rest boon
        # a traveller can `pray` at (kernel.world.shrine), not a heal on each corner. Deterministic.
        if last and trail_i == cfg["branch_every"]:
            rooms[room]["shrine"] = "wayshrine"


_PLACE_WORDS = (
    "the Trail",
    "the Wayside",
    "the Hollow",
    "the Rise",
    "the Ford",
    "the Bend",
    "the Reach",
    "the Glade",
    "the Cut",
    "the Fold",
    "the Verge",
    "the Draw",
    "the Shelf",
    "the Narrows",
    "the Bluff",
    "the Waste",
    "the Spur",
    "the Marches",
)


def _place_word(cfg: dict[str, Any], idx: int) -> str:  # noqa: ARG001
    """A varied local place-name so a generated room reads as a place, not `room 214`."""
    return _PLACE_WORDS[idx % len(_PLACE_WORDS)]


# The order the auto-picker tries directions when a region CHAINS onto an already-generated room and
# its configured attach_dir is taken. Cardinals first (cleanest), then diagonals, then vertical.
_DIR_PREFERENCE = (
    "north",
    "south",
    "east",
    "west",
    "northeast",
    "northwest",
    "southeast",
    "southwest",
    "up",
    "down",
)


def generate_wildlands(
    configs: list[dict[str, Any]], existing_rooms: set[str]
) -> tuple[dict[str, Room], dict[str, Npc]]:
    """Expand every region config into rooms + ambient npcs. A region may `attach` to a SEED room OR
    to a room an earlier region generated (chaining lets a few seed anchors grow a vast connected
    sprawl). When chaining onto a generated room whose configured attach_dir is taken, a free
    direction is auto-picked and the config's attach_dir is updated so the trail-head's reciprocal
    exit stays consistent. All labels are checked against the world and each other, so a bad config
    fails loud rather than orphaning or colliding. Deterministic given the config order."""
    all_rooms: dict[str, Room] = {}
    all_npcs: dict[str, Npc] = {}
    claimed = set(existing_rooms)
    for cfg in configs:
        attach = cfg["attach"]
        if attach not in claimed:
            raise BlueprintError(
                f"wildlands region {cfg['id']!r} attaches to {attach!r}, not a real room "
                "(a seed room, or one an earlier region generated)."
            )
        # Chaining onto a generated room: pick a direction that is actually free on it, so the exit
        # can be wired without clobbering its spine. Seed attach rooms trust the config's dir.
        if attach in all_rooms:
            taken = set(all_rooms[attach]["exits"])
            wanted = [cfg["attach_dir"]] + [d for d in _DIR_PREFERENCE if d != cfg["attach_dir"]]
            free = next((d for d in wanted if d not in taken), None)
            if free is None:
                raise BlueprintError(
                    f"wildlands region {cfg['id']!r} cannot attach to {attach!r}: no free dir."
                )
            cfg["attach_dir"] = free
        rooms, npcs = _region(cfg, claimed)
        # Wire a generated attach room's exit here and now (we hold its dict); seed attach rooms are
        # wired later against the merged world by wire_attach_exits.
        if attach in all_rooms:
            all_rooms[attach]["exits"][cfg["attach_dir"]] = f"{cfg['id']}_t1"
        all_rooms.update(rooms)
        all_npcs.update(npcs)
        claimed.update(rooms)
    return all_rooms, all_npcs


def wire_attach_exits(world: dict[str, Room], configs: list[dict[str, Any]]) -> None:
    """Grow the one exit on each SEED attach room that leads onto its region's trail-head (chained
    regions already wired their generated attach rooms in generate_wildlands). Done on the merged
    world so a hand-authored attach room gains its `attach_dir` exit into the generated land."""
    for cfg in configs:
        head = f"{cfg['id']}_t1"
        if head in world:
            world[cfg["attach"]]["exits"].setdefault(cfg["attach_dir"], head)


def wildlands_zones(configs: list[dict[str, Any]]) -> dict[str, Zone]:
    """One metadata AREA per generated region, carrying its region / level-band / biome, so every
    generated room belongs to geography (the audit reports it, like the hand-authored zones)."""
    zones: dict[str, Zone] = {}
    for cfg in configs:
        L = cfg["trail_length"]  # noqa: N806
        every, blen = cfg["branch_every"], cfg["branch_length"]
        members = [f"{cfg['id']}_t{i}" for i in range(1, L + 1)]
        for i in range(1, L):
            if i > 0 and i % every == 0 and i + 1 < L:
                members += [f"{cfg['id']}_b{i}_{j}" for j in range(1, blen + 1)]
        zones[f"wildlands_{cfg['id']}"] = Zone(
            name=cfg["name"],
            rooms=members,
            reset_mode="empty_only",
            beats_between=12,
            region=cfg["region"],
            level_min=cfg["level_min"],
            level_max=cfg["level_max"],
            biome=cfg["biome"],
        )
    return zones
