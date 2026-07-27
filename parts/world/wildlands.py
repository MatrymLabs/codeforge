"""CARD: wildlands -- procedurally grow coherent wilderness regions to world-generation scale.

Hand-authoring tens of thousands of wilderness rooms would be repetitive filler; this is a
DETERMINISTIC generator (a sibling of parts.world.spiral) that expands a compact region config
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

from pathlib import Path
from typing import Any

import yaml

from parts.world.seed import Npc, Room, SeedError, Zone

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

# Per-biome vocabulary. Each biome gives: a lead sentence, terrain FEATURES (composed by index so
# adjacent rooms differ but relate), LANDMARKS (a branch-end payoff), and CREATURES (ambient life,
# name + attack element) drawn to level-band the region. Kept compact but varied: the combinatorial
# space of lead x feature x landmark x direction is large enough to avoid near-identical rooms.
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
        "creatures": [
            ("a meadow-hare", "WND"),
            ("a grass-adder", "PSN"),
            ("a forge-lark", "WND"),
            ("a horned meadow-ram", "ERT"),
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
        "creatures": [
            ("a reach-wolf", "WND"),
            ("a thornback boar", "ERT"),
            ("a wood-lynx", "WND"),
            ("a bramble-spider", "PSN"),
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
        "creatures": [
            ("a moor-wolf", "WND"),
            ("a hill-husk", "LGT"),
            ("a crag-eagle", "WND"),
            ("a peat-lurker", "ERT"),
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
        "creatures": [
            ("a shore-crab", "WTR"),
            ("a strand-wight", "WTR"),
            ("a gull-of-the-wrack", "WND"),
            ("a tide-adder", "PSN"),
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
        "creatures": [
            ("a rime-wolf", "ICE"),
            ("an ice-wight", "ICE"),
            ("a glass-hound", "ICE"),
            ("a frost-drake whelp", "ICE"),
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
        "creatures": [
            ("an ember-lynx", "FIR"),
            ("a slag-hulk", "FIR"),
            ("a cinder-drake whelp", "FIR"),
            ("a magma-kin", "FIR"),
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
        "creatures": [
            ("a canopy-stalker", "PSN"),
            ("a mire-serpent", "PSN"),
            ("a swarm-kin", "PSN"),
            ("a root-boar", "ERT"),
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
        "creatures": [
            ("an ash-jackal", "ERT"),
            ("a salt-wraith", "WTR"),
            ("a glass-lurker", "DRK"),
            ("a dune-scuttler", "ERT"),
        ],
    },
}


def _biome(name: str) -> dict[str, Any]:
    if name not in _BIOMES:
        raise SeedError(f"wildlands biome {name!r} is unknown. Known biomes: {sorted(_BIOMES)}.")
    return _BIOMES[name]


def load_wildlands_config(path: Path) -> list[dict[str, Any]] | None:
    """Read a seed's optional wildlands.yaml (a mapping of region-id -> config). Returns None when
    the seed ships none. Fails loud on a malformed region: required fields, a real biome,
    a sane level band (1..300, min<=max), positive sizes, and a known trail direction."""
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise SeedError("wildlands.yaml must be a mapping of region-id to config.")
    configs: list[dict[str, Any]] = []
    for rid, cfg in raw.items():
        if not isinstance(cfg, dict):
            raise SeedError(f"wildlands region {rid!r} must be a mapping of config keys.")
        merged = {"branch_every": 3, "branch_length": 3, **cfg, "id": rid}
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
            raise SeedError(f"wildlands region {rid!r} missing key(s): {', '.join(missing)}.")
        _biome(merged["biome"])  # validate the biome exists
        if merged["attach_dir"] not in _OPPOSITE:
            raise SeedError(
                f"wildlands region {rid!r}: attach_dir {merged['attach_dir']!r} is not a direction."
            )
        for key in ("level_min", "level_max", "trail_length", "branch_every", "branch_length"):
            value = merged[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise SeedError(
                    f"wildlands region {rid!r}: {key!r} must be a positive integer, got {value!r}."
                )
        if not merged["level_min"] <= merged["level_max"] <= 300:
            raise SeedError(
                f"wildlands region {rid!r}: need level_min <= level_max <= 300 "
                f"(got {merged['level_min']}-{merged['level_max']})."
            )
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
    """One ambient creature for a generated room -- biome wildlife, level-banded -- so no room ships
    empty (the no-empty-room law). Passive-but-present by default; deterministic by index."""
    biome = _biome(cfg["biome"])
    name, element = biome["creatures"][idx % len(biome["creatures"])]
    label = f"{cfg['id']}_beast_{idx}"
    hp = 20 + level * 4
    npc = Npc(
        name=name,
        keywords=[w for w in name.replace("-", " ").split() if w not in ("a", "an", "of", "the")],
        location=room,
        dialogue=[f"{name.capitalize()} watches from the {cfg['biome'].split('-')[-1]}."],
        next_line=0,
        hp=hp,
        hp_now=hp,
        xp=0,
        atk=6 + level // 2,
        aggressive=(idx % 3 == 0),  # some stretches hunt; most just live there
        level=level,
        tier="normal",
        attack_element=element,
        loot={"ember_shard": 3, "nothing": 2},
    )
    return label, npc


def _describe(
    cfg: dict[str, Any], idx: int, back_dir: str, on_dir: str | None, landmark: str | None
) -> str:
    """Compose a room description by structured variation: the biome lead, an indexed feature,
    a directional cue back and onward, and (at a branch-end) a landmark. Adjacent rooms differ by
    index but share the biome voice; distant biomes read wholly different."""
    biome = _biome(cfg["biome"])
    feature = biome["features"][idx % len(biome["features"])]
    lines = [f"{biome['lead']}: {feature}."]
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
    L = cfg["trail_length"]
    every = cfg["branch_every"]
    blen = cfg["branch_length"]
    rooms: dict[str, Room] = {}
    npcs: dict[str, Npc] = {}
    idx = 0  # a global index across the region, driving level gradient + description variation

    # Total trail-equivalent span for the level gradient (trail + its branches).
    span = L + (L // every) * blen

    def add(label: str, name: str, desc: str, exits: dict[str, str]) -> None:
        nonlocal idx
        if label in claimed or label in rooms:
            raise SeedError(f"wildlands region {rid!r} would collide on room label {label!r}.")
        rooms[label] = Room(name=name, desc=desc, exits=exits)
        beast_label, beast = _ambient(cfg, label, idx, _band_level(cfg, idx, span))
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
        flanks = [d for d in _FLANKS if d != on and d != back]
        if i > 0 and i % every == 0 and i + 1 < L:
            flank = flanks[(i // every) % len(flanks)]
            branch_head = f"{rid}_b{i}_1"
            exits[flank] = branch_head
        name = f"{cfg['name']} - {_place_word(cfg, i)}"
        add(room, name, _describe(cfg, i, back, on if i + 1 < L else None, None), exits)
        if branch_head:
            _branch(cfg, i, flank, room, blen, claimed, rooms, npcs, add)
    return rooms, npcs


def _branch(
    cfg: dict[str, Any],
    trail_i: int,
    flank: str,
    trunk: str,
    blen: int,
    claimed: set[str],
    rooms: dict[str, Room],
    npcs: dict[str, Npc],
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


def _place_word(cfg: dict[str, Any], idx: int) -> str:
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
            raise SeedError(
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
                raise SeedError(
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
        L = cfg["trail_length"]
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
