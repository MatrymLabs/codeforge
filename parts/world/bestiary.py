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

# Each biome: which classes live there, its ambient element, and adjectives that mark its creatures.
_BIOME_LIFE: dict[str, dict[str, object]] = {
    "temperate-meadow": {
        "classes": ("canid", "boar", "avian", "reptile"),
        "el": "WND",
        "adj": ("meadow", "field", "green", "russet", "hedgerow"),
    },
    "wild-forest": {
        "classes": ("canid", "felid", "boar", "insectoid"),
        "el": "WND",
        "adj": ("wood", "bramble", "shadow", "moss", "thorn"),
    },
    "highland-moor": {
        "classes": ("canid", "avian", "ursine", "undead"),
        "el": "LGT",
        "adj": ("moor", "crag", "cairn", "windward", "peat"),
    },
    "coastal-strand": {
        "classes": ("reptile", "avian", "insectoid", "undead"),
        "el": "WTR",
        "adj": ("strand", "tide", "brine", "shingle", "wrack"),
    },
    "glacier-waste": {
        "classes": ("canid", "elemental", "ursine", "undead"),
        "el": "ICE",
        "adj": ("rime", "glacier", "frost", "hoar", "floe"),
    },
    "volcanic-flats": {
        "classes": ("elemental", "reptile", "colossus", "insectoid"),
        "el": "FIR",
        "adj": ("ash", "cinder", "slag", "ember", "obsidian"),
    },
    "living-jungle": {
        "classes": ("felid", "reptile", "insectoid", "boar"),
        "el": "PSN",
        "adj": ("mire", "canopy", "green", "vine", "root"),
    },
    "salt-desert": {
        "classes": ("canid", "reptile", "undead", "insectoid"),
        "el": "ERT",
        "adj": ("salt", "dune", "ash", "glass", "grey"),
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


def make_beast(biome: str, level: int, idx: int, room: str) -> Npc:
    """Compose one creature for a room: a biome-appropriate body-class, marked by a biome adjective,
    at a level-driven size, level-scaled and typed. Deterministic by (biome, level, idx)."""
    life = _BIOME_LIFE.get(biome, _BIOME_LIFE["temperate-meadow"])
    classes: tuple = life["classes"]  # type: ignore[assignment]
    adjs: tuple = life["adj"]  # type: ignore[assignment]
    biome_el: str = life["el"]  # type: ignore[assignment]

    cls_name = _pick(classes, idx)
    cls = _CLASSES[cls_name]
    kin = _pick(cls["kin"], idx // len(classes))  # type: ignore[arg-type]
    adj = _pick(adjs, idx // 2)
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
        loot={"ember_shard": 3, "nothing": 2},
        ambient=True,  # mass wilderness life: no per-foe bounty (see register_bounties)
    )


_TELEGRAPHS = (
    "watches from cover, unblinking",
    "rises to meet you",
    "bars the way, bristling",
    "circles, testing your nerve",
    "lifts its head at your scent",
    "breaks from the brush, already moving",
)


def _telegraph(cls_name: str, idx: int) -> str:
    return _TELEGRAPHS[(idx + len(cls_name)) % len(_TELEGRAPHS)]
