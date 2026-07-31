"""CARD: bestiary -- a procedural creature factory: classes of beasts x modifiers -> varied life.

The world-generation lever (compare spiral/wildlands for rooms, affixes for loot, quest.bounties for
side-quests) pointed at CREATURES. A wilderness of 50,000 rooms cannot draw its life from a few
hardcoded foes without every stretch feeling the same, so this composes each beast from a small,
inspectable schema:

    body-CLASS (canid, felid, reptile, ...) x biome ADJECTIVE x SIZE (by level) x elemental affinity

The space (10 classes x 8 biomes x several kin-nouns x several adjectives x size tiers)
yields thousands of distinct, coherent creatures -- "a dire ash-hound", "an elder rime-wight", "a
meadow razorback" -- each level-scaled through the same reward curve as hand-authored foes. No
randomness: every choice is by index, so the same room always grows the same creature.

`make_beast(biome, level, idx, room)` returns an Npc, ready to merge like any seed foe. Pure, so it
is testable without a boot, and it is what parts.world.wildlands hangs in each generated room.
"""

from __future__ import annotations

from parts.world.seed import Npc

# Body-plans. `kin` are interchangeable nouns; `hp`/`atk` scale the level base; `undead`
# and `elemental` carry their own element; everyone else takes their biome's (a fire-touched wolf
# in the flats strikes FIR -- the land marks its life). Variety comes from combination.
_CLASSES: dict[str, dict[str, object]] = {
    "canid": {"kin": ("wolf", "hound", "jackal"), "hp": 1.0, "atk": 1.05, "el": None},
    "felid": {"kin": ("lynx", "panther", "sabrecat"), "hp": 0.9, "atk": 1.2, "el": None},
    "ursine": {"kin": ("bear", "brute", "maul"), "hp": 1.4, "atk": 1.1, "el": None},
    "boar": {"kin": ("boar", "tusker", "razorback"), "hp": 1.2, "atk": 1.05, "el": None},
    "reptile": {"kin": ("adder", "basilisk", "serpent"), "hp": 0.9, "atk": 1.0, "el": "PSN"},
    "avian": {"kin": ("hawk", "shrike", "roc"), "hp": 0.7, "atk": 1.15, "el": None},
    "insectoid": {"kin": ("beetle", "scarab", "mantis"), "hp": 0.85, "atk": 1.0, "el": "PSN"},
    "elemental": {"kin": ("wisp", "elemental", "revenant"), "hp": 1.0, "atk": 1.1, "el": None},
    "undead": {"kin": ("husk", "wight", "wraith"), "hp": 1.1, "atk": 1.0, "el": "DRK"},
    "colossus": {"kin": ("hulk", "golem", "colossus"), "hp": 1.9, "atk": 1.25, "el": None},
}

# Monster materials (Crafting slice 1c): the raw crafting material a body-class drops on its loot
# table, so felling the wilds' life feeds the tannery, not just the coin purse. Furred and feathered
# beasts give a hide; scaled and shelled ones give chitin. The unbodied (elemental/undead/colossus)
# yield no such material -- there is no pelt to take. Leatherworking refines these into gear.
_CLASS_MATERIAL: dict[str, str] = {
    "canid": "raw_hide",
    "felid": "raw_hide",
    "ursine": "raw_hide",
    "boar": "raw_hide",
    "avian": "raw_hide",
    "reptile": "chitin_scale",
    "insectoid": "chitin_scale",
}


def material_for_class(cls_name: str) -> str | None:
    """The raw monster material a body-class drops (raw_hide / chitin_scale), or None for a class
    with no pelt or shell to take (elemental, undead, colossus)."""
    return _CLASS_MATERIAL.get(cls_name)


# Each biome: which classes live there, its ambient element, and adjectives that mark its creatures.
_BIOME_LIFE: dict[str, dict[str, object]] = {
    "temperate-meadow": {
        "classes": ("canid", "boar", "avian", "reptile"),
        "el": "WND",
        "adj": (
            "meadow",
            "field",
            "green",
            "russet",
            "hedgerow",
            "clover",
            "thistle",
            "briar",
            "upland",
            "downland",
            "gorse",
            "heath",
        ),
    },
    "wild-forest": {
        "classes": ("canid", "felid", "boar", "insectoid"),
        "el": "WND",
        "adj": (
            "wood",
            "bramble",
            "shadow",
            "moss",
            "thorn",
            "fern",
            "birch",
            "hollow",
            "timber",
            "root",
            "gloam",
            "dusk",
        ),
    },
    "highland-moor": {
        "classes": ("canid", "avian", "ursine", "undead"),
        "el": "LGT",
        "adj": (
            "moor",
            "crag",
            "cairn",
            "windward",
            "peat",
            "tor",
            "fell",
            "heather",
            "scree",
            "mist",
            "granite",
            "brae",
        ),
    },
    "coastal-strand": {
        "classes": ("reptile", "avian", "insectoid", "undead"),
        "el": "WTR",
        "adj": (
            "strand",
            "tide",
            "brine",
            "shingle",
            "wrack",
            "surf",
            "foam",
            "reef",
            "salt",
            "storm",
            "cliff",
            "spray",
        ),
    },
    "glacier-waste": {
        "classes": ("canid", "elemental", "ursine", "undead"),
        "el": "ICE",
        "adj": (
            "rime",
            "glacier",
            "frost",
            "hoar",
            "floe",
            "ice",
            "snow",
            "sleet",
            "glaze",
            "drift",
            "pale",
            "boreal",
        ),
    },
    "volcanic-flats": {
        "classes": ("elemental", "reptile", "colossus", "insectoid"),
        "el": "FIR",
        "adj": (
            "ash",
            "cinder",
            "slag",
            "ember",
            "obsidian",
            "basalt",
            "magma",
            "sulphur",
            "char",
            "scoria",
            "pyre",
            "forge",
        ),
    },
    "living-jungle": {
        "classes": ("felid", "reptile", "insectoid", "boar"),
        "el": "PSN",
        "adj": (
            "mire",
            "canopy",
            "green",
            "vine",
            "root",
            "fern",
            "spore",
            "bloom",
            "sap",
            "moss",
            "humid",
            "tangle",
        ),
    },
    "salt-desert": {
        "classes": ("canid", "reptile", "undead", "insectoid"),
        "el": "ERT",
        "adj": (
            "salt",
            "dune",
            "ash",
            "glass",
            "grey",
            "bleach",
            "mirage",
            "bone",
            "scour",
            "crust",
            "waste",
            "sun",
        ),
    },
}

# Size tier by level, with a small stat multiplier and a naming word. The higher the band, the more
# the wilds skew large and dread; an index tie-breaker keeps a band from being one size only.
_SIZES = (
    ("lesser ", 0.75),  # 0
    ("", 1.0),  # 1 (the plain form)
    ("dire ", 1.35),  # 2
    ("great ", 1.6),  # 3
    ("elder ", 1.9),  # 4
    ("dread ", 2.2),  # 5
)


def _pick(seq: tuple, idx: int):
    return seq[idx % len(seq)]


def _size_tier(level: int, idx: int) -> int:
    """A size index 0..5 that skews larger with level, varied by idx so a band mixes sizes."""
    base = min(level // 45, 4)  # 0 at low levels ... 4 by ~L180
    wobble = (idx % 3) - 1  # -1, 0, +1
    return max(0, min(5, base + 1 + wobble))


def classes_for_biome(biome: str) -> tuple[str, ...]:
    """The creature body-classes (canid, felid, ...) that live in a biome. Falls back to the
    temperate meadow's set for an unknown biome, never empty."""
    life = _BIOME_LIFE.get(biome, _BIOME_LIFE["temperate-meadow"])
    classes: tuple = life["classes"]  # type: ignore[assignment]
    return tuple(str(c) for c in classes)


def cullable_types(biome: str) -> tuple[str, ...]:
    """Every creature TYPE a cull can name in a biome: each body-class AND each of its kin (canid,
    wolf, hound, jackal, ...). All are keywords the creatures carry, so a cull on any counts.
    Deduped (a class named like a kin, e.g. 'boar', appears once). This multiplies the cull board
    from a handful of classes to a real spread of distinct targets."""
    types: list[str] = []
    for cls in classes_for_biome(biome):
        types.append(cls)
        kin: tuple = _CLASSES[cls]["kin"]  # type: ignore[assignment]
        types.extend(str(k) for k in kin)
    return tuple(dict.fromkeys(types))


def make_beast(biome: str, level: int, idx: int, room: str) -> Npc:
    """Compose one creature for a room: a biome-appropriate body-class, marked by a biome adjective,
    at a level-driven size, level-scaled and typed. Deterministic by (biome, level, idx)."""
    life = _BIOME_LIFE.get(biome, _BIOME_LIFE["temperate-meadow"])
    classes: tuple = life["classes"]  # type: ignore[assignment]
    adjs: tuple = life["adj"]  # type: ignore[assignment]
    biome_el: str = life["el"]  # type: ignore[assignment]

    # Two per-room phases (char-sums of the room label) decorrelate the COSMETIC axes -- which kin
    # of the class, and which biome adjective -- across regions. Without them every region restarts
    # its index at 0, so same-index rooms in the same biome minted the identical creature and a few
    # names swamped the wilds. The two phases must be INDEPENDENT: a single shared phase links adj
    # (mod 12) and kin (mod 3), and since 3 divides 12 only a third of the pairs can appear. A plain
    # char-sum drives adj; a position-weighted one drives kin, so they decorrelate. The class stays
    # idx-driven (it fixes the element, the stats, the cull ecology), but every kin of every class
    # still appears across a zone, so no cull target vanishes -- only its room shifts.
    adj_phase = sum(ord(c) for c in room)
    kin_phase = sum((i + 1) * ord(c) for i, c in enumerate(room))
    cls_name = _pick(classes, idx)
    cls = _CLASSES[cls_name]
    kin = _pick(cls["kin"], idx // len(classes) + kin_phase)  # type: ignore[arg-type]
    adj = _pick(adjs, idx // 2 + adj_phase)
    size_word, size_mult = _SIZES[_size_tier(level, idx)]

    element = str(cls["el"] or biome_el)  # class element if set, else the biome's
    noun = f"{adj}-{kin}"
    first_word = size_word or noun  # the word right after the article decides a/an
    article = "an" if first_word[0].lower() in "aeiou" else "a"
    display = f"{article} {size_word}{noun}"

    hp = int((18 + level * 4) * float(cls["hp"]) * size_mult)  # type: ignore[arg-type]
    atk = int((5 + level // 2) * float(cls["atk"]))  # type: ignore[arg-type]
    tier = "elite" if idx % 11 == 10 else "normal"
    if tier == "elite":
        hp = int(hp * 1.6)
        atk = int(atk * 1.25)
    return Npc(
        name=display,
        keywords=[w for w in (adj, kin, cls_name) if w],
        location=room,
        dialogue=[f"{display.capitalize()} {_telegraph(cls_name, idx)}."],
        next_line=0,
        hp=hp,
        hp_now=hp,
        xp=0,
        atk=atk,
        aggressive=(idx % 3 == 0),
        level=level,
        tier=tier,
        attack_element=element,
        loot=_ambient_loot(cls_name, biome, tier),
        ambient=True,  # mass wilderness life: no per-foe bounty (see register_bounties)
    )


def _ambient_loot(cls_name: str, biome: str, tier: str = "normal") -> dict[str, int]:
    """A common creature's weighted loot: ember-shards, its class's monster material (hide/chitin,
    if any), the biome's signature SPOIL (the same herb its nodes yield and its town vendor buys, so
    a kill feeds the local crafting economy), and a chance of nothing. An ELITE is worth the harder
    fight: it never drops nothing and its materials weigh heavier (parts.shelf.weighted_table).

    The biome spoil is resolved through wildlands.biome_spoil (the single source of truth for a
    biome's herb); the import is local to avoid a cycle (wildlands imports this module)."""
    from parts.world.wildlands import biome_spoil

    loot = {"ember_shard": 3, "nothing": 2}
    material = _CLASS_MATERIAL.get(cls_name)
    if material:
        loot[material] = 2
    spoil = biome_spoil(biome)
    if spoil and spoil != "ember_shard":
        loot[spoil] = 2
    if tier == "elite":
        loot.pop("nothing", None)  # an elite always yields something for the harder fight
        for drop in list(loot):
            if drop != "ember_shard":
                loot[drop] += 2  # and its materials come dearer
    return loot


# A named guardian's proper name (a fore-name + a biome-marked epithet), deterministic by index. The
# wilds' ambient life is nameless; a NOTABLE is an individual with a title, a hunt target the bounty
# board names and the player seeks out.
_NAME_HEAD = (
    "Grath",
    "Vor",
    "Thane",
    "Mor",
    "Skarn",
    "Ur",
    "Bala",
    "Kael",
    "Draum",
    "Vex",
    "Hroth",
)
_NAME_TAIL = ("ok", "ar", "une", "ix", "oth", "ka", "en", "ur", "aya", "orn")
_EPITHETS = (
    "Warden",
    "Maw",
    "Sovereign",
    "Stalker",
    "Bane",
    "Matron",
    "Herald",
    "Tyrant",
    "Scourge",
)


def _forge_name(idx: int) -> str:
    """A stable proper name from the syllable pools, e.g. 'Grathok', 'Vorune'."""
    head = _NAME_HEAD[idx % len(_NAME_HEAD)]
    tail = _NAME_TAIL[(idx // len(_NAME_HEAD)) % len(_NAME_TAIL)]
    return f"{head}{tail}"


def make_notable(biome: str, level: int, idx: int, room: str, seq: int) -> Npc:
    """A NAMED guardian: a bestiary creature ennobled into a titled individual (elite, or every
    sixth a boss), non-ambient so it mints a hunt bounty (parts.world.quest.register_bounties),
    stronger and better-paying than the ambient life around it. Deterministic by (biome, level,
    idx, seq)."""
    beast = make_beast(biome, level, idx, room)
    life = _BIOME_LIFE.get(biome, _BIOME_LIFE["temperate-meadow"])
    adjs: tuple = life["adj"]  # type: ignore[assignment]
    mark = str(_pick(adjs, idx // 2))  # the biome word its title carries
    name = _forge_name(idx + seq * 5)  # seq varies the fore-name so a region's guardians all differ
    role = _EPITHETS[(idx + seq) % len(_EPITHETS)]
    display = f"{name} the {mark.capitalize()} {role}"

    is_boss = seq % 6 == 5  # roughly one in six guardians is a boss-tier payout (10x reward curve)
    hp = int(beast["hp"] * (2.4 if is_boss else 1.5))
    beast["name"] = display
    beast["keywords"] = list(dict.fromkeys([name.lower(), role.lower(), *beast["keywords"]]))
    beast["hp"] = hp
    beast["hp_now"] = hp
    beast["atk"] = int(beast["atk"] * (1.4 if is_boss else 1.2))
    beast["tier"] = "boss" if is_boss else "elite"
    beast["aggressive"] = False  # a hunt TARGET the player seeks, not a roadside ambush
    beast["dialogue"] = [f"{display} {_telegraph(display, idx)}."]
    # A richer haul than ambient life: more ember, and a heavier chance of its monster material.
    beast["loot"] = {"ember_shard": 5, "nothing": 1}
    material = material_for_class(beast["keywords"][-1])
    if material:
        beast["loot"][material] = 3
    beast.pop("ambient", None)  # NOT ambient: the bounty board names it, the hunt is on
    return beast


# The generic fallback: creature-agnostic tells for a class without its own pool (all ten have one
# below, so this is a safety net, never the main path).
_TELEGRAPHS = (
    "watches from cover, unblinking",
    "rises to meet you",
    "bars the way, bristling",
    "circles, testing your nerve",
    "lifts its head at your scent",
    "breaks from the brush, already moving",
)

# CLASS-AWARE combat tells: the line a player reads at the start of every fight, keyed to the
# creature's body-class so a wolf circles, a wraith drifts, and a colossus grinds -- combat reads
# in-character instead of cycling six generic sentences worldwide. Seven per class; the beast's name
# already varies widely, so name x tell gives a large, flavour-correct space. Extend a pool freely;
# the test twin pins that every class has one.
_CLASS_TELEGRAPHS: dict[str, tuple[str, ...]] = {
    "canid": (
        "circles low, hackles up and teeth bared",
        "paces the trail, watching for your throat",
        "drops its head and growls from deep in the chest",
        "fans wide as if it hunts with a pack long dead",
        "bares its teeth and will not be stared down",
        "slinks closer on silent pads, testing you",
        "throws back its head and howls, and the sound is answered",
    ),
    "felid": (
        "flattens to the ground, all coiled patience",
        "watches from the shadow with lamp-bright eyes",
        "pads a slow circle and never once looks away",
        "lashes its tail and gathers itself to spring",
        "melts half into cover, only its stare left",
        "shows its fangs in something too cold for a snarl",
        "moves without a sound, and is suddenly nearer",
    ),
    "ursine": (
        "rears up huge and bellows a warning",
        "drops to all fours and shakes the ground coming on",
        "swings its great head, small eyes fixing on you",
        "roars until the very air seems to shake",
        "lumbers forward, in no hurry and utterly certain",
        "rakes the earth with claws like plough-blades",
        "stands its ground and dares you to come closer",
    ),
    "boar": (
        "lowers its tusks and paws the trampled ground",
        "snorts and squares up, small-eyed and furious",
        "charges a step and pulls up, testing your nerve",
        "grinds its tusks and will not give the path",
        "wheels to keep its tusks between you and it",
        "breaks into a bristling, head-down charge",
        "champs and slavers, working itself to a fury",
    ),
    "reptile": (
        "coils tight and tastes the air with a flickering tongue",
        "rears its head and holds, still as cut stone",
        "hisses low and fixes you with a lidless stare",
        "draws back to strike, its jaws unhinging",
        "pours itself into a coil across the way",
        "sways, slow and hypnotic, and does not blink",
        "opens its mouth on a bright threat of venom",
    ),
    "avian": (
        "mantles its wings and shrieks a challenge",
        "drops from the height in a stoop of talons",
        "rakes the air and circles for an opening",
        "screams once, high and cold, and folds to dive",
        "spreads vast wings that blot out the light",
        "cocks its head, marking you with a killer's eye",
        "beats up into the wind to gain the killing height",
    ),
    "insectoid": (
        "clashes its mandibles and rears on spined legs",
        "chitters a dry warning through a hundred mouthparts",
        "raises barbed forelimbs and holds, waiting",
        "scuttles a half-circle on far too many legs",
        "flexes its carapace and clicks, and clicks, and clicks",
        "unfolds sawing limbs from beneath its shell",
        "swings its horned head, feelers reading your fear",
    ),
    "elemental": (
        "gathers itself brighter, humming with charge",
        "draws the loose light and cold in toward its core",
        "flickers, reforms a pace nearer, and steadies",
        "pulses with a glow that carries no warmth",
        "coalesces out of the air where nothing stood",
        "hums up the scale toward a note that hurts",
        "sheds sparks that die before they touch the ground",
    ),
    "undead": (
        "drifts nearer, cold pouring off it in a wave",
        "turns a ruined face toward you and does not stop",
        "raises a withered hand and beckons you closer",
        "moans low, a dead language moving under the sound",
        "wears a grief older than the ground it rose from",
        "flickers between one step and the next, gaining",
        "fixes you with eyes that hold no light at all",
    ),
    "colossus": (
        "grinds forward, stone-jawed and terribly slow",
        "rises with a shriek of settling rock and metal",
        "plants a foot that cracks the ground beneath it",
        "swings a fist the size of a millstone to bear",
        "looms up until it blots the sky, and steps",
        "hauls its vast bulk around to face you square",
        "shudders to life, dust sheeting off ancient shoulders",
    ),
}


def _telegraph(cls_name: str, idx: int) -> str:
    """The creature's opening combat tell, drawn from its CLASS pool so the fight reads in
    character. An unknown class falls back to the generic tells. Deterministic by (class, idx)."""
    pool = _CLASS_TELEGRAPHS.get(cls_name, _TELEGRAPHS)
    return pool[(idx + len(cls_name)) % len(pool)]
