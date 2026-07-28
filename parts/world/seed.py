"""CARD: seed -- load and validate world component packs from YAML.

The world is files. Every loader is also a GATE: a pack that fails
validation never reaches the engine.

Identity rules (all component types):
- LABEL: the YAML key. lowercase_snake_case, unique, permanent.
  Machines link by label: exits, saves, scripts, code.
- NAME: human display text. Free to change anytime.

Shared machinery (all component types):
- label gates: bad format gets a suggested fix; duplicates are
  refused (plain YAML would silently overwrite).
- the template merge chain, rightmost wins:
    engine defaults -> file 'template:' block -> the entry's own fields

Location rule: operators write plain room labels in YAML
(location: library). The engine tags item locations internally
(room:library) because items can also live on a player.
"""

import os
import re
from pathlib import Path
from typing import Any, NotRequired, TypedDict

import yaml

from parts.shelf.conditions import ConditionError, validate
from parts.shelf.reward_curve import LEVEL_MAX, LEVEL_MIN, TIER_MULTIPLIERS
from parts.world.score_sheet_model import RESIST_ORDER  # the canonical element/status codes

# A seed IS a game. The engine loads one seed pack at startup; swap the seed and
# codeforge boots a different game (fantasy `first-forge`, `spiral-ascent`, ...).
# Selection is by the FORGE_SEED env var, read once at import -- you choose which
# program the proving ground runs when it powers on, not while it's running.
# Default: the repo's seeds/ dir. CODEFORGE_SEEDS_ROOT overrides it for installed /
# containerized deploys where the package lives apart from the seed files.
_default_seeds_root = (
    Path(__file__).resolve().parent.parent.parent / "seeds"
)  # parts/world/ -> repo root
SEEDS_ROOT = Path(os.environ.get("CODEFORGE_SEEDS_ROOT", str(_default_seeds_root)))
DEFAULT_SEED = "first-forge"
SEED_NAME = os.environ.get("FORGE_SEED", DEFAULT_SEED)
SEED_DIR = SEEDS_ROOT / SEED_NAME


def available_seeds() -> list[str]:
    """Every installed game: seed dirs that carry a rooms.yaml, alphabetical."""
    if not SEEDS_ROOT.is_dir():
        return []
    return sorted(p.name for p in SEEDS_ROOT.iterdir() if (p / "rooms.yaml").is_file())


def load_splash() -> str:
    """The world's title screen: seeds/<world>/splash.txt (world data, like every seed file).

    Read by every driver that opens a world - the TCP gateway, the web gateway, and the solo
    terminal loop - so the world's own face greets the player, not a generic banner."""
    path = SEED_DIR / "splash.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").rstrip("\n")
    return "Welcome, traveler."


LABEL_RE = re.compile(r"^[a-z][a-z0-9_]*$")
# The sentinel `location` for a drop-only prototype: a template never placed in the world, only
# spawned by clone() (loot, timed spawns). Reserved -- a room may not be labelled this.
UNPLACED = "nowhere"
DEFAULT_ROOM_DESC = "There is nothing remarkable here yet."
DEFAULT_DIALOGUE = ['"..."']
# The six canonical attributes (JRPG character system): the loader fills any a job omits.
# `speed` replaces the old `agility`; `wisdom` and `luck` are new. Balance per job is set in
# the seed data, not here -- these defaults only guarantee every job carries all six.
DEFAULT_JOB_STATS = {
    "strength": 8,
    "speed": 8,
    "magic": 8,
    "stamina": 8,
    "wisdom": 8,
    "luck": 8,
}

# The valid resistance levels a job may declare for an element/status. Undeclared reads Normal.
RESIST_LEVELS = ("Weak", "Normal", "Resist", "Immune", "Absorb")


class Room(TypedDict):
    """The shape every room must have."""

    name: str
    desc: str
    exits: dict[str, str]
    # Optional: a live capability this room surfaces on `look` (e.g. "arc" -> the ARC verdict).
    # The world stays data; the engine renders a declared capability, never a hard-coded room.
    dynamic: NotRequired[str]
    # Optional: a GATHER node -- the item prototype a Forger harvests here with `gather`
    # (a crafting material). The node renews after a short cooldown (parts.world.gather). Absent = a
    # room with nothing to gather.
    node: NotRequired[str]


class Item(TypedDict):
    """The shape every item must have.

    `slot` and `mods` are the OPTIONAL equipment fields: a bare item leaves them empty; an
    equippable one names its slot (weapon/body/head/arm/accessory_1/accessory_2) and the flat
    modifiers it grants (target stat -> amount, e.g. {ATK: 6}). The loader fills empty defaults."""

    name: str
    keywords: list[str]
    location: str  # "room:<label>" or "player"
    slot: str  # equipment slot, or "" for a non-equippable item
    mods: dict[str, int]  # flat stat modifiers this item grants when equipped
    # The seed label this item is an INSTANCE of. A seed label is a prototype (a template);
    # runtime items are instances cloned from it (parts.world.items.clone). Seed items are their
    # own prototype. Optional so existing Item literals stay valid; readers use prototype_of().
    prototype: NotRequired[str]
    # Opt-in: this item REPOPULATES on an area reset. If a `resettable` item is absent from its
    # home room when its area comes due (parts.world.zones), a fresh instance spawns there. Default
    # off, so quest items and keys never respawn (no duplicated ember, no second key).
    resettable: NotRequired[bool]
    # A CONSUMABLE's one-shot effect: a map of resource -> restore amount, e.g. {hp: 30} or
    # {hp: 20, mp: 10}. `quaff <item>` spends the item and restores those pools. Optional -- a bare
    # item is not consumable. Only `hp`/`mp` are honoured; a positive int each. Validated at load.
    consume: NotRequired[dict[str, int]]
    # The rarity tier a levelled drop rolled (parts.shelf.affixes): common/uncommon/rare/epic/
    # legendary. Set when combat rolls affixes onto an instance; absent (read as "common") on a
    # base seed item. A client colours the loadout by it; readers use `.get("rarity", "common")`.
    rarity: NotRequired[str]
    # Readable lore: the text `read <item>` shows. A lore book, a record, an inscription -- readable
    # environmental storytelling you can carry. Optional -- a bare item has nothing written on it.
    lore: NotRequired[str]
    # A WANDERING pickup (dynamic spawn): the candidate rooms this item may appear in. On an area
    # reset, if no instance is loose anywhere in the pool, one spawns at a pick_room-chosen site, so
    # the pickup is not always in the same spot (parts.world.zones._spawn_wanderers). Requires
    # location: nowhere -- a wanderer is not placed, it appears. Absent = an ordinary fixed item.
    spawn_pool: NotRequired[list[str]]
    # Rarity for a wandering spawn: appear on only 1-in-N eligible resets. Absent/1 = every eligible
    # reset. Combined with spawn_pool this gives a rare pickup that also moves. Positive int.
    spawn_chance: NotRequired[int]
    # Seasonal gate for a wandering spawn: the seasons (spring/summer/autumn/winter) this pickup may
    # appear in. Absent = every season. Read against the world's climate at reset time
    # (parts.world.zones._spawn_wanderers), so a spring bloom or winter relic only shows in season.
    seasons: NotRequired[list[str]]


class Npc(TypedDict):
    """The shape every NPC must have."""

    name: str
    keywords: list[str]
    location: str  # room label
    dialogue: list[str]
    next_line: int  # runtime state, always starts at 0
    hp: int  # max hit points; 0 means peaceful, not attackable
    hp_now: int  # runtime state, starts at hp
    xp: int  # XP awarded when defeated
    atk: int  # counter-attack damage; 0 (default) means passive, never strikes back
    aggressive: NotRequired[bool]  # True = strikes first on the world beat; default False
    # A LETHAL foe (a boss) is NOT covered by the training-ground failsafe: fall to it and you are
    # sent back to your start room at full health while it recovers, not revived in place. Default
    # False, so every training-ground foe stays gentle. A lethal foe must be combatable (hp > 0).
    lethal: NotRequired[bool]
    # Optional: a level (1-300) and tier (normal/elite/boss) that scale the kill reward through the
    # challenge curve (parts.shelf.reward_curve): fighting up pays more, grays pay nothing. A foe
    # WITHOUT a level keeps its flat `xp` award (the tutorial default). Validated at load.
    level: NotRequired[int]
    tier: NotRequired[str]
    # Runtime state: a burn damage-over-time applied by a `brand` ability -- {damage, ticks}. It
    # saps `damage` HP on each world beat until `ticks` runs out (never below 1: you land the
    # finishing blow). Cleared when the foe reassembles. Never seeded; combat sets and clears it.
    burn: NotRequired[dict[str, int]]
    # Runtime state: beats a foe is DAZED, applied by a `daze` ability -- it skips that many of its
    # world-beat strikes (crowd control on an aggressive foe), decremented each beat by menace.
    # Cleared when the foe reassembles. Never seeded; combat sets and clears it.
    dazed: NotRequired[int]
    # Runtime state: the number of its next blows a foe is WEAKENED for, applied by a `weaken`
    # ability -- each softens (halves, floored 1) and decrements one. Cleared when the foe
    # reassembles. Never seeded; combat sets and clears it.
    weakened: NotRequired[int]
    # Runtime state: True once a BOSS has crossed its enrage threshold (parts.world.boss_phases), so
    # the enrage announces once. Self-clears when the boss recovers above the line. Never seeded.
    enraged: NotRequired[bool]
    # Optional: an ELEMENT its blows carry (a RESIST code -- FIR/ICE/LGT/...). When set, the
    # player's job resistance to that element scales the incoming blow (Weak amplifies, Resist
    # halves, Immune nullifies, Absorb heals). Absent = an untyped (physical) blow no resistance
    # touches. This makes the score sheet's resistance grid matter. Validated against RESIST_ORDER.
    attack_element: NotRequired[str]
    # Optional: this foe's OWN resistance grid (code -> level), the mirror of a job's. A player's
    # elemental ability is scaled by it -- freeze the fire creature, don't burn it. Absent = a foe
    # that resists nothing (every hit lands full). Validated vs RESIST_ORDER and RESIST_LEVELS.
    resistances: NotRequired[dict[str, str]]
    # Optional: an AFFLICTION this foe's landed blow may lay on the player (afflictions.py):
    # {status, chance?, damage?, ticks?, beats?}. `status` 'daze' stuns for `beats`; any other name
    # is a damage-over-time of that name (`damage` per beat for `ticks`). `chance` is 1-in-N (def.
    # 1 = always). The substrate a telegraphed boss special needs. Validated at load.
    inflicts: NotRequired[dict[str, object]]
    # Optional (boss-tier): a TELEGRAPHED SPECIAL (parts.world.boss_specials). {telegraph, mult?,
    # cadence?} -- once enraged, the boss winds up (announcing `telegraph`, no blow that beat) then
    # unleashes a `mult`x blow with a guaranteed affliction, at most 1-in-`cadence` of its beats.
    # `charging` is the runtime wind-up flag (never seeded). Validated at load.
    special: NotRequired[dict[str, object]]
    charging: NotRequired[bool]
    # Item prototype labels this NPC drops when defeated: a fresh instance of each is spawned into
    # the room (parts.world.items.clone). Optional; a bare NPC drops nothing. Loot is real object
    # instancing -- the drop is a new instance, so it never collides with the seed original.
    drops: NotRequired[list[str]]
    # A WEIGHTED loot table rolled once on defeat: {item_prototype -> weight}, plus the reserved
    # key `nothing` for a no-drop weight. One outcome is picked proportional to weight and spawned.
    # `drops` (above) is guaranteed; `loot` is the chance roll. Optional.
    loot: NotRequired[dict[str, int]]
    # AMBIENT wildlife: a mass-generated wilderness creature (parts.world.bestiary), not a notable
    # foe. Excluded from hunt-contract bounties (a world of a million ambient hares must not mint a
    # million bounty quests -- that is both absurd content and the boot-time hot spot at scale).
    # Default absent (read as False), so every hand-authored and Spiral foe keeps its bounty.
    ambient: NotRequired[bool]
    # A SHOP this NPC keeps (a merchant). `sells` maps an item prototype to its coin price (buy one
    # and a fresh instance is cloned into your hands); `buys` maps a prototype to the coins it pays
    # for one. Both optional within the shop. Prices are positive ints; prototypes are cross-checked
    # against the seed's items at boot (inspect_world_links). Optional -- a bare NPC keeps no shop.
    shop: NotRequired[dict[str, dict[str, int]]]
    # TOPICS a player can ask this NPC about: a keyword -> the response line(s). `ask <npc> about
    # <topic>` looks one up; a bare `ask <npc>` lists them. This turns a cycling dialogue list into
    # a real conversation. Keys are lowercase keywords; each maps to a non-empty list of strings.
    topics: NotRequired[dict[str, list[str]]]


class Door(TypedDict):
    """The shape every door must have: a lockable barrier on one room's exit."""

    name: str
    keywords: list[str]
    blocks: tuple[str, str]  # (room_label, direction) -- the exit this door guards
    locked: bool
    key_id: str  # the item label that unlocks it, or "" for a door opened by other means
    # Optional: a self-closing "portcullis" -- after a player UNLOCKS it, the world beat relocks
    # it this many beats later (0/absent = stays open once unlocked). Quest-opened doors never
    # set this, so a reforged bridge stays reforged.
    recloses_after: NotRequired[int]
    # Optional: a safe condition (parts.shelf.conditions) gating the unlock, evaluated against the
    # actor's state (level, rank). Validated at load; a door with a requires the actor doesn't meet
    # stays barred even with the key. Absent = no extra gate.
    requires: NotRequired[str]


class Job(TypedDict):
    """The shape every job (class/calling) must have.

    The first three fields are the original calling. The rest are the JRPG job loadout: they
    are OPTIONAL in the data (a simple calling omits them) but the loader always fills them
    with empty defaults, so every Job carries the full shape. Ability fields hold ability
    labels (names), not behavior -- combat wiring is a later batch.
    """

    name: str
    description: str
    stats: dict[str, int]
    role_tags: list[str]  # role identity, e.g. ["support", "control", "technical"]
    abilities: list[str]  # active skill labels
    automatic_attack: str  # the auto-attack label
    counter: str  # reaction ability label
    movement: str  # positioning/mobility ability label
    inherent: str  # passive trait label
    signature: str  # defining job ability label
    resistances: dict[str, str]  # element/status code -> level (Normal/Weak/Resist/Immune/Absorb)
    power_cells: int  # size of the job's custom resource pool (0 = none, runs on MP)
    power_regen: int  # power cells regained per combat tick
    milestone_perks: list[dict]  # ordered passive perks unlocked at each TP milestone


class Ability(TypedDict):
    """A usable combat ability: what it does, what it scales on, and which jobs may wield it.

    An ability turns a fight from one repeated `attack` into a job's own moveset. `strike` deals
    damage scaled by an attribute; `heal` restores the wielder's HP. `jobs` names the callings that
    may use it, so the job->ability link lives in the data, not hardcoded. Validated at load.
    """

    name: str  # display name, e.g. "Power Strike"
    # kinds: "strike" (damage) | "heal" (self) | "brand" (burn DoT) | "daze" (skip strikes) |
    # "weaken" (soften its blows)
    kind: str
    power: int  # flat base magnitude before the stat scale (for `daze`/`weaken`, a number of beats)
    scales: str  # the attribute it scales on (strength/magic/...), or "" for flat
    mp_cost: int  # MP spent to use it
    jobs: list[str]  # job labels that may use this ability
    # Optional: the ELEMENT this move deals (a RESIST code -- FIR/ICE/...). When set, the target's
    # resistance to it scales the damage (Weak amplifies, Resist halves, Immune nullifies).
    # Absent = an untyped (physical) hit no resistance touches. Validated against RESIST_ORDER.
    element: NotRequired[str]
    # Optional: the COOLDOWN in combat beats. After a successful channel the move is locked out for
    # this many beats; a landed strike advances the combat clock and thaws it (parts.world.combat_
    # clock). Absent or 0 = no cooldown (spam-limited only by MP). This is the cadence knob that
    # turns "spam the strongest button" into a rotation. Validated as a non-negative int.
    cooldown: NotRequired[int]


class Recipe(TypedDict):
    """A crafting recipe: consume `inputs` (material prototype -> count) to make one `makes` item.

    Crafting turns gathered materials into goods at the forge (the `craft` verb), so the maker Jobs
    and the drop/salvage economy have a use. The world is data: recipes are YAML, validated at load.
    """

    name: str  # display name of what it forges, e.g. "a healing draught"
    makes: str  # the output item prototype label (cloned into the crafter's hands)
    inputs: dict[str, int]  # material prototype label -> quantity consumed from the inventory
    # Optional acquisition gate (slice 1d): a recipe you must EARN before you can forge it. Keys:
    # `profession` (a trade id) + `level` (the trade level it demands), and/or `order` (a sworn
    # Order id). Absent = an open recipe anyone can forge. Craftability derives from the player's
    # professions + Order, no stored "known" flag (derive-don't-store). Validated at load.
    requires: NotRequired[dict[str, object]]


class Profession(TypedDict):
    """A maker's TRADE: a data-driven skill track leveled by DOING (parts.world.professions).

    `kind` is 'gather' or 'craft'. A gather trade lists the material prototype labels it `works`; a
    craft trade lists the recipe labels it `makes`. Skill is earned by gathering/crafting what the
    trade governs; persists per character. The world is data: trades are YAML, validated at boot.
    """

    name: str  # display name, e.g. "Smithing"
    kind: str  # 'gather' | 'craft'
    works: list[str]  # gather trade: material prototype labels (empty for a craft trade)
    makes: list[str]  # craft trade: recipe labels (empty for a gather trade)


class GearSet(TypedDict):
    """A gear SET: wear every one of its `pieces` at once and earn a flat `bonus` on top of the
    pieces' own mods, so collecting a whole regional set beats three unrelated pieces. The world is
    data: sets are YAML, validated at load; the bonus math lives in parts.world.gearsets.
    """

    name: str  # display name of the set, e.g. "the Stormward set"
    pieces: list[str]  # the item prototype labels that must ALL be worn for the bonus
    bonus: dict[str, int]  # flat stat -> amount granted when the set is complete


class QuestStep(TypedDict):
    """One move in a quest: from `state`, event `event` advances to `to`; `effect` is optional.

    World-event triggers let an arc advance from a real action instead of only the `quest <event>`
    verb (which always stays a fallback, so a trigger can never dead-end the arc):
      `on_defeat` -- an NPC label whose defeat in combat fires this step;
      `on_take`   -- an item label whose pickup fires it;
      `on_enter`  -- a room label whose entry fires it;
      `on_cull`   -- a creature TYPE (a keyword like 'canid'/'wolf') whose defeat fires it, so a
                     'cull N of a kind' quest can chain N identical steps, one per kill;
      `on_forage` -- a (zone-scoped) material whose gather fires it, so a 'forage N' quest chains N
                     identical steps, one per harvest.
    """

    state: str
    event: str
    to: str
    effect: NotRequired[str]
    on_defeat: NotRequired[str]
    on_take: NotRequired[str]
    on_enter: NotRequired[str]
    on_cull: NotRequired[str]
    on_forage: NotRequired[str]


class QuestSpec(TypedDict):
    """A region's story arc, as data: a workflow the player walks with the `quest` verb.

    The engine already drives quests as workflows; this lets a seed SHIP its own arc instead of
    hardcoding one in Python (the world is data). Optional per seed -- `load_quest` returns None
    when a seed ships no quest.yaml, and the game falls back to its built-in default.
    """

    id: str
    name: str
    start: str
    reward_xp: int
    steps: list[QuestStep]
    terminal: list[str]
    labels: dict[str, str]


# Zone reset modes: how eager an area is to refill on the world beat. `never` groups rooms
# only (no reset); `empty_only` refills when no player occupies it; `always` refills on cadence.
RESET_MODES = ("never", "empty_only", "always")


class Zone(TypedDict):
    """An AREA: a named group of rooms with a reset policy.

    Grouping over the flat room graph (regions/areas), a mechanism common to the MUD
    tradition (best documented in the Diku/Circle/tbaMUD family, LGPL). The reset POLICY is
    declared here as data; the beat-driven scheduler that reads it lives in `parts/world/zones.py`.
    Labels, not vnums: a zone names its member rooms by their existing room labels.
    """

    name: str  # display name of the area
    rooms: list[str]  # member room labels
    reset_mode: str  # one of RESET_MODES
    beats_between: int  # world beats between reset opportunities (> 0)
    # Layer-2 geographic metadata (all OPTIONAL, backward-compatible): a zone that omits them loads
    # exactly as before. When present they give an area its place in the world -- its parent Reach,
    # its recommended level band, and its primary biome -- so tooling (scripts/world_audit.py) can
    # report region and Level 1-300 coverage. Data, not behavior: the reset scheduler ignores them.
    region: NotRequired[str]  # the parent Reach / continent (e.g. "Emberreach", "The Cinderdeep")
    level_min: NotRequired[int]  # recommended minimum level (>= 1)
    level_max: NotRequired[int]  # recommended maximum level (>= level_min, <= 300)
    biome: NotRequired[str]  # primary biome (e.g. "temperate-coast", "glacier", "volcanic")


class SeedError(Exception):
    """Raised when a seed file fails validation. Names the exact problem."""


# Parse seeds with libyaml's CSafeLoader (~13x faster than the pure-Python SafeLoader) on the
# cold-start path, falling back to SafeLoader where libyaml is absent. The C composer preserves
# duplicate key pairs in the composed node, so the unique-key gate below still fires (proven and
# pinned by test_duplicate_label_is_rejected + test_seed_loader_prefers_libyaml). EXP-004.
try:
    from yaml import CSafeLoader as _SeedYamlBase
except ImportError:  # pragma: no cover - libyaml is present on our hosts and in CI
    from yaml import SafeLoader as _SeedYamlBase  # type: ignore[assignment]


class _UniqueKeyLoader(_SeedYamlBase):
    """A YAML loader that refuses duplicate keys instead of silently
    overwriting them."""


def _construct_unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in mapping:
            raise SeedError(
                f"Duplicate label '{key}' in seed file. "
                "Every label must be unique -- rename one of them."
            )
        mapping[key] = loader.construct_object(value_node, deep=True)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _check_label(label: str, what: str) -> None:
    if not isinstance(label, str) or not LABEL_RE.match(label):
        suggestion = re.sub(r"[^a-z0-9_]+", "_", str(label).lower()).strip("_") or "my_label"
        raise SeedError(
            f"{what} label '{label}' is invalid. Labels must be lowercase_snake_case "
            f"(letters, digits, underscores; starts with a letter). Try: '{suggestion}'."
        )


def _phrase(label: str) -> str:
    return label.replace("_", " ")


def _auto_keywords(label: str) -> list[str]:
    """copper_key -> ['copper key', 'copper', 'key']"""
    words = label.split("_")
    keywords = [_phrase(label)] if len(words) > 1 else []
    keywords.extend(words)
    return keywords


def _article(noun: str) -> str:
    return "an" if noun[:1] in "aeiou" else "a"


def _open_seed_bin(path: Path, what: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Shared front door: read YAML, gate labels, pop the template block.

    Returns (entries, file_template)."""
    if not path.exists():
        raise SeedError(f"Seed file not found: {path}")
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(data, dict) or not data:
        raise SeedError(f"Seed file is empty or not a mapping: {path}")
    file_template = data.pop("template", None) or {}
    if not isinstance(file_template, dict):
        raise SeedError("'template:' must be a mapping of default fields.")
    entries: dict[str, dict[str, Any]] = {}
    for label, raw in data.items():
        _check_label(label, what)
        if raw is None:
            raw = {}  # a bare label is valid: all defaults
        if not isinstance(raw, dict):
            raise SeedError(f"{what} '{label}' is not a mapping.")
        entries[label] = raw
    return entries, file_template


def _inspect_required_types(
    label: str, merged: dict[str, Any], spec: tuple[tuple[str, type], ...]
) -> None:
    for field, kind in spec:
        if not isinstance(merged[field], kind):
            raise SeedError(f"'{label}' field '{field}' must be {kind.__name__}.")


def load_rooms(path: Path) -> dict[str, Room]:
    """Read rooms.yaml, validate it, return the room graph."""
    entries, file_template = _open_seed_bin(path, "Room")
    rooms: dict[str, Room] = {}
    for label, raw in entries.items():
        merged: dict[str, Any] = {
            "name": _phrase(label).title(),
            "desc": DEFAULT_ROOM_DESC,
            "exits": {},
            **file_template,
            **raw,
        }
        _inspect_required_types(label, merged, (("name", str), ("desc", str), ("exits", dict)))
        room = Room(name=merged["name"], desc=merged["desc"], exits=merged["exits"])
        if merged.get("dynamic"):
            room["dynamic"] = str(merged["dynamic"])
        rooms[label] = room
    for label, room in rooms.items():
        for direction, destination in room["exits"].items():
            if destination not in rooms:
                raise SeedError(
                    f"Room '{label}' has exit '{direction}' -> '{destination}', "
                    "which does not exist in this seed."
                )
    return rooms


def load_items(path: Path) -> dict[str, Item]:
    """Read items.yaml, validate it, return items with tagged locations."""
    entries, file_template = _open_seed_bin(path, "Item")
    items: dict[str, Item] = {}
    for label, raw in entries.items():
        noun = _phrase(label)
        merged: dict[str, Any] = {
            "name": f"{_article(noun)} {noun}",
            "keywords": _auto_keywords(label),
            "slot": "",
            "mods": {},
            "resettable": False,
            **file_template,
            **raw,
        }
        if "location" not in merged:
            raise SeedError(f"Item '{label}' is missing required field 'location' (a room label).")
        _inspect_required_types(
            label,
            merged,
            (("name", str), ("keywords", list), ("location", str), ("slot", str), ("mods", dict)),
        )
        for target, amount in merged["mods"].items():
            if not isinstance(amount, int) or isinstance(amount, bool):
                raise SeedError(f"Item '{label}': mod '{target}' must be an integer")
        loc = merged["location"]
        # `nowhere` is a drop-only PROTOTYPE: a template that is never placed in a room (so it
        # never renders or can be taken from the floor), existing only to be spawned by clone()
        # -- e.g. loot a foe drops on defeat. This is the Diku/LP "object prototype" idea, made
        # native to instancing. `player` and room labels place a live instance as before.
        tagged = loc if loc in ("player", UNPLACED) else f"room:{loc}"
        if not isinstance(merged["resettable"], bool):
            raise SeedError(f"Item '{label}': 'resettable' must be true or false.")
        consume = merged.get("consume")
        if consume is not None and (
            not isinstance(consume, dict)
            or not all(
                pool in ("hp", "mp")
                and isinstance(amount, int)
                and not isinstance(amount, bool)
                and amount > 0
                for pool, amount in consume.items()
            )
        ):
            raise SeedError(
                f"Item '{label}': 'consume' must map hp/mp to a positive integer restore."
            )
        lore = merged.get("lore")
        if lore is not None and (not isinstance(lore, str) or not lore.strip()):
            raise SeedError(f"Item '{label}': 'lore' must be non-empty readable text.")
        spawn_pool = merged.get("spawn_pool")
        if spawn_pool is not None:
            if (
                not isinstance(spawn_pool, list)
                or not spawn_pool
                or not all(isinstance(r, str) and r for r in spawn_pool)
            ):
                raise SeedError(
                    f"Item '{label}': 'spawn_pool' must be a non-empty list of room labels."
                )
            if loc != UNPLACED:
                raise SeedError(
                    f"Item '{label}': a wandering 'spawn_pool' item must have location: {UNPLACED} "
                    "(it appears in the world, it is not placed in one room)."
                )
        spawn_chance = merged.get("spawn_chance")
        if spawn_chance is not None and (
            not isinstance(spawn_chance, int) or isinstance(spawn_chance, bool) or spawn_chance < 1
        ):
            raise SeedError(
                f"Item '{label}': 'spawn_chance' must be a positive integer (1 = every reset)."
            )
        if spawn_chance is not None and spawn_pool is None:
            raise SeedError(f"Item '{label}': 'spawn_chance' only applies to a 'spawn_pool' item.")
        seasons = merged.get("seasons")
        if seasons is not None:
            from parts.world.climate import SEASONS

            if (
                not isinstance(seasons, list)
                or not seasons
                or not all(s in SEASONS for s in seasons)
            ):
                raise SeedError(
                    f"Item '{label}': 'seasons' must be a non-empty list drawn from {SEASONS}."
                )
            if spawn_pool is None:
                raise SeedError(f"Item '{label}': 'seasons' only applies to a 'spawn_pool' item.")
        item = Item(
            name=merged["name"],
            keywords=merged["keywords"],
            location=tagged,
            slot=merged["slot"],
            mods=dict(merged["mods"]),
            prototype=label,  # a seed-placed item is its own prototype
        )
        if merged["resettable"]:
            item["resettable"] = True  # opt-in: repopulates on an area reset
        if consume:
            item["consume"] = dict(consume)
        if lore:
            item["lore"] = str(lore)  # readable text: `read <item>` shows it
        if spawn_pool:
            item["spawn_pool"] = [
                str(r) for r in spawn_pool
            ]  # a wandering pickup's candidate rooms
        if spawn_chance:
            item["spawn_chance"] = int(spawn_chance)  # rarity for the wanderer
        if seasons:
            item["seasons"] = [str(s) for s in seasons]  # the seasons the wanderer appears in
        items[label] = item
    return items


def load_npcs(path: Path) -> dict[str, Npc]:
    """Read npcs.yaml, validate it, return NPCs. next_line is runtime state."""
    entries, file_template = _open_seed_bin(path, "NPC")
    npcs: dict[str, Npc] = {}
    for label, raw in entries.items():
        merged: dict[str, Any] = {
            "name": f"the {_phrase(label)}",
            "keywords": _auto_keywords(label),
            "dialogue": DEFAULT_DIALOGUE,
            "hp": 0,
            "xp": 0,
            "atk": 0,
            "aggressive": False,
            "lethal": False,
            "drops": [],
            "loot": {},
            **file_template,
            **raw,
        }
        if "location" not in merged:
            raise SeedError(f"NPC '{label}' is missing required field 'location' (a room label).")
        _inspect_required_types(
            label,
            merged,
            (
                ("name", str),
                ("keywords", list),
                ("location", str),
                ("dialogue", list),
                ("hp", int),
                ("xp", int),
                ("atk", int),
                ("aggressive", bool),
                ("lethal", bool),
            ),
        )
        # A lethal foe must be combatable: an hp-0 poser can never fell anyone, so 'lethal' on it
        # is a contradiction -- refuse loud rather than ship a boss that can't be a boss.
        if merged["lethal"] and merged["hp"] <= 0:
            raise SeedError(
                f"NPC '{label}' is lethal but has hp {merged['hp']}; a lethal foe must be "
                "combatable (hp > 0)."
            )
        if merged["atk"] < 0:
            raise SeedError(
                f"NPC '{label}' has a negative atk ({merged['atk']}); "
                "counter-attack damage cannot be negative."
            )
        # An aggressive NPC opens the fight on the world beat; a poser that cannot land a
        # blow (atk 0) or cannot be fought back (hp 0) is a contradiction -- refuse loud.
        if merged["aggressive"]:
            if merged["atk"] <= 0:
                raise SeedError(
                    f"NPC '{label}' is aggressive but has atk {merged['atk']}; "
                    "an aggressive NPC needs atk > 0 to strike first."
                )
            if merged["hp"] <= 0:
                raise SeedError(
                    f"NPC '{label}' is aggressive but has hp {merged['hp']}; "
                    "an aggressive NPC must be combatable (hp > 0)."
                )
        # xp is awarded to XP/JP/TP on defeat; a negative value would DRAIN the victor. hp<0 would
        # read as an unfightable corpse. Refuse both loud and early, as we do for atk.
        for field in ("xp", "hp"):
            if merged[field] < 0:
                raise SeedError(
                    f"NPC '{label}' has a negative {field} ({merged[field]}); cannot be negative."
                )
        drops = merged["drops"]
        if not isinstance(drops, list) or not all(isinstance(d, str) for d in drops):
            raise SeedError(
                f"NPC '{label}': 'drops' must be a list of item prototype labels (strings)."
            )
        loot = merged["loot"]
        if not isinstance(loot, dict) or not all(
            isinstance(k, str) and isinstance(w, int) and not isinstance(w, bool) and w > 0
            for k, w in loot.items()
        ):
            raise SeedError(
                f"NPC '{label}': 'loot' must be a mapping of item prototype (or 'nothing') "
                "to a positive integer weight."
            )
        # Optional challenge rating: a 'level' (1-300) and 'tier' feed the reward curve so a kill
        # pays by the gap between fighter and foe. Both are opt-in -- a levelless foe keeps its flat
        # xp -- but a tier without a level is a contradiction (nothing to scale), so refuse it loud.
        level = merged.get("level")
        if level is not None and (
            not isinstance(level, int)
            or isinstance(level, bool)
            or not LEVEL_MIN <= level <= LEVEL_MAX
        ):
            raise SeedError(
                f"NPC '{label}': 'level' must be an integer {LEVEL_MIN}-{LEVEL_MAX}, got {level!r}."
            )
        tier = merged.get("tier")
        if tier is not None and tier not in TIER_MULTIPLIERS:
            raise SeedError(
                f"NPC '{label}': 'tier' must be one of {sorted(TIER_MULTIPLIERS)}, got {tier!r}."
            )
        if tier is not None and level is None:
            raise SeedError(
                f"NPC '{label}': 'tier' {tier!r} is set but 'level' is not; a tier only scales a "
                "levelled foe. Give the NPC a level or drop the tier."
            )
        # Optional conversation topics: a keyword -> non-empty list of response lines.
        topics = merged.get("topics")
        if topics is not None and (
            not isinstance(topics, dict)
            or not all(
                isinstance(key, str)
                and isinstance(lines, list)
                and lines
                and all(isinstance(line, str) for line in lines)
                for key, lines in topics.items()
            )
        ):
            raise SeedError(
                f"NPC '{label}': 'topics' must map a keyword to a non-empty list of reply strings."
            )
        # Optional attack element: a typed blow whose damage the player's job resistance scales.
        # Must be one of the canonical resistance codes, so a foe can never carry an element the
        # score sheet has no row for -- refuse an unknown one loud rather than ship a dead type.
        element = merged.get("attack_element")
        if element is not None and element not in RESIST_ORDER:
            raise SeedError(
                f"NPC '{label}': 'attack_element' must be one of {list(RESIST_ORDER)}, "
                f"got {element!r}."
            )
        # Optional resistance grid (the mirror of a job's): scales a player's elemental ability.
        # Codes must be canonical and levels valid, so a foe never carries a resistance the system
        # can't read -- refuse a bad code or level loud rather than ship a dead defense.
        resistances = merged.get("resistances")
        if resistances is not None:
            if not isinstance(resistances, dict):
                raise SeedError(
                    f"NPC '{label}': 'resistances' must map an element code to a level."
                )
            for code, resist_level in resistances.items():
                if code not in RESIST_ORDER:
                    raise SeedError(
                        f"NPC '{label}': resistance code {code!r} must be one of "
                        f"{list(RESIST_ORDER)}."
                    )
                if resist_level not in RESIST_LEVELS:
                    raise SeedError(
                        f"NPC '{label}': resistance {code!r} must be one of {RESIST_LEVELS}, "
                        f"got {resist_level!r}."
                    )
        inflicts = merged.get("inflicts")
        if inflicts is not None:
            if not isinstance(inflicts, dict) or set(inflicts) - {
                "status",
                "chance",
                "damage",
                "ticks",
                "beats",
            }:
                raise SeedError(
                    f"NPC '{label}': 'inflicts' allows only status/chance/damage/ticks/beats keys."
                )
            status = inflicts.get("status")
            if not isinstance(status, str) or not status:
                raise SeedError(
                    f"NPC '{label}': 'inflicts.status' must name an affliction ('poison', 'daze')."
                )
            for key in ("chance", "damage", "ticks", "beats"):
                value = inflicts.get(key)
                if value is not None and (
                    not isinstance(value, int) or isinstance(value, bool) or value < 1
                ):
                    raise SeedError(f"NPC '{label}': 'inflicts.{key}' must be a positive integer.")
        special = merged.get("special")
        if special is not None:
            if not isinstance(special, dict) or set(special) - {"telegraph", "mult", "cadence"}:
                raise SeedError(
                    f"NPC '{label}': 'special' allows only telegraph/mult/cadence keys."
                )
            tele = special.get("telegraph")
            if tele is not None and (not isinstance(tele, str) or not tele.strip()):
                raise SeedError(f"NPC '{label}': 'special.telegraph' must be non-empty text.")
            for key in ("mult", "cadence"):
                value = special.get(key)
                if value is not None and (
                    not isinstance(value, int) or isinstance(value, bool) or value < 1
                ):
                    raise SeedError(f"NPC '{label}': 'special.{key}' must be a positive integer.")
        # Optional shop: a merchant's `sells`/`buys` price tables. Prices are positive ints; the
        # prototypes are cross-checked against the seed's items at boot (inspect_world_links).
        shop = merged.get("shop")
        if shop is not None:
            if not isinstance(shop, dict) or set(shop) - {"sells", "buys"}:
                raise SeedError(
                    f"NPC '{label}': 'shop' must be a mapping with only 'sells' and/or 'buys'."
                )
            for side in ("sells", "buys"):
                table = shop.get(side, {})
                if not isinstance(table, dict) or not all(
                    isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) and v > 0
                    for k, v in table.items()
                ):
                    raise SeedError(
                        f"NPC '{label}': shop '{side}' must map an item prototype to a positive "
                        "integer price."
                    )
        npc = Npc(
            name=merged["name"],
            keywords=merged["keywords"],
            location=merged["location"],
            dialogue=merged["dialogue"],
            next_line=0,
            hp=merged["hp"],
            hp_now=merged["hp"],
            xp=merged["xp"],
            atk=merged["atk"],
            aggressive=merged["aggressive"],
        )
        if merged["lethal"]:
            npc["lethal"] = True
        if level is not None:
            npc["level"] = level
            npc["tier"] = tier if tier is not None else "normal"
        if drops:
            npc["drops"] = list(drops)
        if loot:
            npc["loot"] = dict(loot)
        if shop:
            npc["shop"] = {side: dict(table) for side, table in shop.items()}
        if topics:
            npc["topics"] = {key: list(lines) for key, lines in topics.items()}
        if element is not None:
            npc["attack_element"] = element
        if resistances:
            npc["resistances"] = dict(resistances)
        if inflicts:
            npc["inflicts"] = dict(inflicts)
        if special:
            npc["special"] = dict(special)
        npcs[label] = npc
    return npcs


def inspect_world_links(
    rooms: dict[str, Room], items: dict[str, Item], npcs: dict[str, Npc]
) -> None:
    """The cross-component gate: everything placed somewhere must be
    placed in a room that exists. Runs at boot, before any player."""
    for label, item in items.items():
        loc = item["location"]
        if loc not in ("player", UNPLACED) and loc.removeprefix("room:") not in rooms:
            raise SeedError(
                f"Item '{label}' is placed in room '{loc.removeprefix('room:')}', "
                "which does not exist."
            )
        for site in item.get("spawn_pool", []):  # a wanderer's candidate rooms must all be real
            if site not in rooms:
                raise SeedError(
                    f"Item '{label}' spawn_pool names room '{site}', which does not exist."
                )
    for label, npc in npcs.items():
        if npc["location"] not in rooms:
            raise SeedError(
                f"NPC '{label}' is placed in room '{npc['location']}', which does not exist."
            )
        for drop in npc.get("drops", []):  # loot must name a real item prototype (caught at boot)
            if drop not in items:
                raise SeedError(f"NPC '{label}' drops '{drop}', which is not an item in this seed.")
        for side in ("sells", "buys"):  # a shop's wares must name real item prototypes
            for proto in npc.get("shop", {}).get(side, {}):
                if proto not in items:
                    raise SeedError(
                        f"NPC '{label}' shop {side} names '{proto}', which is not an item "
                        "in this seed."
                    )
        for outcome in npc.get("loot", {}):  # weighted loot: every outcome but `nothing` is real
            if outcome != "nothing" and outcome not in items:
                raise SeedError(
                    f"NPC '{label}' loot names '{outcome}', which is not an item in this seed "
                    "(use 'nothing' for a no-drop weight)."
                )


def load_jobs(path: Path) -> dict[str, Job]:
    """Load and gate the job pack: every job gets name, description, stats."""
    entries, template = _open_seed_bin(path, "job")
    jobs: dict[str, Job] = {}
    for label, fields in entries.items():
        _check_label(label, "job")
        merged: dict[str, Any] = {
            "name": _phrase(label).title(),
            "description": "",
            "stats": dict(DEFAULT_JOB_STATS),
            "role_tags": [],
            "abilities": [],
            "automatic_attack": "",
            "counter": "",
            "movement": "",
            "inherent": "",
            "signature": "",
            "resistances": {},
            "power_cells": 0,
            "power_regen": 0,
            "milestone_perks": [],
        }
        merged.update(template)
        merged.update(fields)
        _inspect_required_types(
            label,
            merged,
            (
                ("name", str),
                ("description", str),
                ("stats", dict),
                ("role_tags", list),
                ("abilities", list),
                ("automatic_attack", str),
                ("counter", str),
                ("movement", str),
                ("inherent", str),
                ("signature", str),
                ("resistances", dict),
                ("power_cells", int),
                ("power_regen", int),
                ("milestone_perks", list),
            ),
        )
        for perk in merged["milestone_perks"]:
            if not (
                isinstance(perk, dict)
                and isinstance(perk.get("name"), str)
                and isinstance(perk.get("target"), str)
                and isinstance(perk.get("amount"), int)
                and not isinstance(perk.get("amount"), bool)
            ):
                raise SeedError(
                    f"job '{label}': each milestone perk needs name(str), target(str), amount(int)"
                )
        stats = dict(DEFAULT_JOB_STATS) | dict(merged["stats"])
        for stat_name, value in stats.items():
            if not isinstance(value, int) or isinstance(value, bool):
                raise SeedError(f"job '{label}': stat '{stat_name}' must be an integer")
        for list_field in ("role_tags", "abilities"):
            if not all(isinstance(entry, str) for entry in merged[list_field]):
                raise SeedError(f"job '{label}': every {list_field} entry must be a string")
        for code, level in merged["resistances"].items():
            if level not in RESIST_LEVELS:
                raise SeedError(
                    f"job '{label}': resistance '{code}' must be one of {RESIST_LEVELS}"
                )
        jobs[label] = Job(
            name=merged["name"],
            description=merged["description"],
            stats=stats,
            role_tags=list(merged["role_tags"]),
            abilities=list(merged["abilities"]),
            automatic_attack=merged["automatic_attack"],
            counter=merged["counter"],
            movement=merged["movement"],
            inherent=merged["inherent"],
            signature=merged["signature"],
            resistances=dict(merged["resistances"]),
            power_cells=merged["power_cells"],
            power_regen=merged["power_regen"],
            milestone_perks=[dict(p) for p in merged["milestone_perks"]],
        )
    return jobs


def load_quest(path: Path) -> QuestSpec | None:
    """Load a seed's optional story arc (a workflow, as data). Returns None if the seed ships no
    quest file; fails loud (SeedError) on a malformed one -- a broken arc must not boot silently."""
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SeedError(f"quest file must be a mapping: {path}")
    for key in ("id", "start", "steps"):
        if key not in data:
            raise SeedError(f"{path}: quest needs '{key}'")
    steps = data["steps"]
    if not isinstance(steps, list) or not steps:
        raise SeedError(f"{path}: quest 'steps' must be a non-empty list")
    clean_steps: list[QuestStep] = []
    for raw in steps:
        if not isinstance(raw, dict) or not all(k in raw for k in ("state", "event", "to")):
            raise SeedError(f"{path}: each quest step needs 'state', 'event', and 'to'")
        step: QuestStep = {
            "state": str(raw["state"]),
            "event": str(raw["event"]),
            "to": str(raw["to"]),
        }
        if raw.get("effect"):
            step["effect"] = str(raw["effect"])
        for trigger in ("on_defeat", "on_take", "on_enter", "on_cull", "on_forage"):
            if raw.get(trigger):
                step[trigger] = str(raw[trigger])
        clean_steps.append(step)
    reward = data.get("reward_xp", 50)
    if not isinstance(reward, int) or isinstance(reward, bool) or reward < 0:
        raise SeedError(f"{path}: 'reward_xp' must be a non-negative integer")
    terminal = data.get("terminal", [])
    labels = data.get("labels", {})
    if not isinstance(terminal, list) or not isinstance(labels, dict):
        raise SeedError(f"{path}: 'terminal' must be a list and 'labels' a mapping")
    return QuestSpec(
        id=str(data["id"]),
        name=str(data.get("name", _phrase(str(data["id"])).title())),
        start=str(data["start"]),
        reward_xp=reward,
        steps=clean_steps,
        terminal=[str(t) for t in terminal],
        labels={str(k): str(v) for k, v in labels.items()},
    )


def load_doors(path: Path) -> dict[str, Door]:
    """Load a seed's optional lockable barriers. {} if the seed ships none; fails loud on a bad one.
    A door with an empty key_id is opened by other means (e.g. a quest effect), never a key."""
    if not path.exists():
        return {}
    entries, template = _open_seed_bin(path, "door")
    doors: dict[str, Door] = {}
    for label, fields in entries.items():
        merged: dict[str, Any] = {
            "name": _phrase(label).title(),
            "keywords": _auto_keywords(label),
            "blocks": None,
            "locked": True,
            "key_id": "",
            "recloses_after": 0,
        }
        merged.update(template)
        merged.update(fields)
        blocks = merged["blocks"]
        if not (
            isinstance(blocks, list)
            and len(blocks) == 2
            and all(isinstance(part, str) for part in blocks)
        ):
            raise SeedError(f"door '{label}': 'blocks' must be [room_label, direction]")
        _inspect_required_types(
            label,
            {**merged, "blocks": tuple(blocks)},
            (("name", str), ("keywords", list), ("locked", bool), ("key_id", str)),
        )
        recloses = merged["recloses_after"]
        if not isinstance(recloses, int) or isinstance(recloses, bool) or recloses < 0:
            raise SeedError(
                f"door '{label}': 'recloses_after' must be a non-negative integer "
                f"(beats before a self-closing door relocks), got {recloses!r}."
            )
        requires = merged.get("requires")
        if requires is not None:
            if not isinstance(requires, str):
                raise SeedError(
                    f"door '{label}': 'requires' must be a condition string, got {requires!r}."
                )
            try:
                validate(requires)  # a load-time gate: reject a malformed/unsafe condition now
            except ConditionError as exc:
                raise SeedError(f"door '{label}': invalid 'requires' condition: {exc}") from exc
        door = Door(
            name=merged["name"],
            keywords=list(merged["keywords"]),
            blocks=(str(blocks[0]), str(blocks[1])),
            locked=bool(merged["locked"]),
            key_id=str(merged["key_id"]),
        )
        if recloses:
            door["recloses_after"] = recloses
        if requires is not None:
            door["requires"] = requires
        doors[label] = door
    return doors


def load_abilities(path: Path) -> dict[str, Ability]:
    """Load a seed's optional combat abilities. {} if the seed ships none; fails loud on a bad one.

    Each ability is a usable move: `kind` strike/heal, `power` its base magnitude, `scales` the
    attribute it grows on (one of the six, or "" for flat), `mp_cost` the MP it spends, and `jobs`
    the callings that may wield it. Structure and every attribute name are checked at load."""
    if not path.exists():
        return {}
    entries, template = _open_seed_bin(path, "ability")
    abilities: dict[str, Ability] = {}
    attrs = set(DEFAULT_JOB_STATS)
    for label, fields in entries.items():
        merged: dict[str, Any] = {
            "name": _phrase(label).title(),
            "kind": "strike",
            "power": 0,
            "scales": "",
            "mp_cost": 0,
            "cooldown": 0,
            "jobs": [],
        }
        merged.update(template)
        merged.update(fields)
        _inspect_required_types(
            label,
            merged,
            (
                ("name", str),
                ("kind", str),
                ("power", int),
                ("scales", str),
                ("mp_cost", int),
                ("cooldown", int),
                ("jobs", list),
            ),
        )
        if merged["kind"] not in ("strike", "heal", "brand", "daze", "weaken"):
            raise SeedError(
                f"ability '{label}': 'kind' must be 'strike', 'heal', 'brand', 'daze', or "
                f"'weaken', got {merged['kind']!r}."
            )
        for num_field in ("power", "mp_cost", "cooldown"):
            value = merged[num_field]
            if isinstance(value, bool) or value < 0:
                raise SeedError(
                    f"ability '{label}': '{num_field}' must be a non-negative int, got {value!r}."
                )
        scales = merged["scales"]
        if scales and scales not in attrs:
            raise SeedError(
                f"ability '{label}': 'scales' must be an attribute or empty, got {scales!r}."
            )
        # Optional element: a typed hit whose damage the target's resistance scales. Must be a
        # canonical resistance code so a move can never deal a type no foe grid could answer.
        element = merged.get("element")
        if element is not None and element not in RESIST_ORDER:
            raise SeedError(
                f"ability '{label}': 'element' must be a RESIST code {list(RESIST_ORDER)}, "
                f"got {element!r}."
            )
        ability = Ability(
            name=str(merged["name"]),
            kind=str(merged["kind"]),
            power=int(merged["power"]),
            scales=str(scales),
            mp_cost=int(merged["mp_cost"]),
            jobs=[str(j) for j in merged["jobs"]],
        )
        if element is not None:
            ability["element"] = str(element)
        if merged["cooldown"]:  # only a real cooldown is stamped; a bare ability stays uncapped
            ability["cooldown"] = int(merged["cooldown"])
        abilities[label] = ability
    return abilities


def load_recipes(path: Path) -> dict[str, Recipe]:
    """Load a seed's optional crafting recipes. {} if the seed ships none; fails loud on a bad one.

    Each recipe names what it `makes` (an output item prototype) and the `inputs` it consumes
    (material prototype -> a positive count). The prototypes are cross-checked against the seed's
    items at boot (like a shop's wares), so a recipe can never make or need an item that isn't real.
    """
    if not path.exists():
        return {}
    entries, template = _open_seed_bin(path, "recipe")
    recipes: dict[str, Recipe] = {}
    for label, fields in entries.items():
        merged: dict[str, Any] = {"name": _phrase(label).title(), "makes": "", "inputs": {}}
        merged.update(template)
        merged.update(fields)
        _inspect_required_types(label, merged, (("name", str), ("makes", str), ("inputs", dict)))
        if not merged["makes"]:
            raise SeedError(f"recipe '{label}': 'makes' must name the output item prototype.")
        inputs = merged["inputs"]
        if not inputs or not all(
            isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) and v > 0
            for k, v in inputs.items()
        ):
            raise SeedError(
                f"recipe '{label}': 'inputs' must map a material prototype to a positive count "
                "(at least one input)."
            )
        recipe = Recipe(
            name=str(merged["name"]),
            makes=str(merged["makes"]),
            inputs={str(k): int(v) for k, v in inputs.items()},
        )
        requires = _inspect_recipe_gate(label, merged.get("requires"))
        if requires:
            recipe["requires"] = requires
        recipes[label] = recipe
    return recipes


def _inspect_recipe_gate(label: str, requires: object) -> dict[str, object]:
    """Validate a recipe's optional acquisition gate (slice 1d). Returns the cleaned dict, or {} if
    absent. `profession` (str) demands a `level` (positive int); `order` (str) is standalone. Fails
    loud on any other key or a malformed value, so a typo'd gate never silently opens a recipe."""
    if requires is None:
        return {}
    if not isinstance(requires, dict) or set(requires) - {"profession", "level", "order"}:
        raise SeedError(
            f"recipe '{label}': 'requires' allows only 'profession'/'level'/'order' keys."
        )
    gate: dict[str, object] = {}
    if "profession" in requires or "level" in requires:
        prof, level = requires.get("profession"), requires.get("level")
        if not isinstance(prof, str) or not prof:
            raise SeedError(f"recipe '{label}': 'requires.profession' must name a trade.")
        if not isinstance(level, int) or isinstance(level, bool) or level < 1:
            raise SeedError(f"recipe '{label}': 'requires.level' must be a positive integer.")
        gate["profession"], gate["level"] = prof, level
    order = requires.get("order")
    if order is not None:
        if not isinstance(order, str) or not order:
            raise SeedError(f"recipe '{label}': 'requires.order' must name an Order.")
        gate["order"] = order
    return gate


def load_professions(path: Path) -> dict[str, Profession]:
    """Load a seed's optional maker TRADES. {} if the seed ships none; fails loud on a bad one.

    Each trade names its `kind` ('gather' or 'craft') and what it governs: a gather trade lists the
    material prototypes it `works`; a craft trade lists the recipe labels it `makes`. The references
    are cross-checked against the seed's items and recipes by the professions conformance test, so a
    trade can never govern a material or recipe that isn't real.
    """
    if not path.exists():
        return {}
    entries, template = _open_seed_bin(path, "profession")
    professions: dict[str, Profession] = {}
    for label, fields in entries.items():
        merged: dict[str, Any] = {
            "name": _phrase(label).title(),
            "kind": "",
            "works": [],
            "makes": [],
        }
        merged.update(template)
        merged.update(fields)
        _inspect_required_types(
            label,
            merged,
            (("name", str), ("kind", str), ("works", list), ("makes", list)),
        )
        kind = merged["kind"]
        if kind not in ("gather", "craft"):
            raise SeedError(
                f"profession '{label}': 'kind' must be 'gather' or 'craft', got {kind!r}."
            )
        key = "works" if kind == "gather" else "makes"
        governed = merged[key]
        if not governed or not all(isinstance(x, str) and x for x in governed):
            raise SeedError(
                f"profession '{label}': a {kind} trade needs a non-empty '{key}' list of labels."
            )
        professions[label] = Profession(
            name=str(merged["name"]),
            kind=str(kind),
            works=[str(x) for x in merged["works"]],
            makes=[str(x) for x in merged["makes"]],
        )
    return professions


def load_sets(path: Path) -> dict[str, "GearSet"]:
    """Load a seed's optional gear SETS. {} if the seed ships none; fails loud on a bad one.

    Each set lists its `pieces` (at least two item prototype labels) and the flat `bonus` (stat ->
    a positive amount) earned when all pieces are worn together. Shape is validated here; that the
    pieces and stats are real is cross-checked against the seed's items at boot (like a recipe).
    """
    if not path.exists():
        return {}
    entries, template = _open_seed_bin(path, "set")
    sets: dict[str, GearSet] = {}
    for label, fields in entries.items():
        merged: dict[str, Any] = {"name": _phrase(label).title(), "pieces": [], "bonus": {}}
        merged.update(template)
        merged.update(fields)
        _inspect_required_types(label, merged, (("name", str), ("pieces", list), ("bonus", dict)))
        pieces = merged["pieces"]
        if len(pieces) < 2 or not all(isinstance(p, str) for p in pieces):
            raise SeedError(f"set '{label}': 'pieces' must list at least two item prototypes.")
        bonus = merged["bonus"]
        if not bonus or not all(
            isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) and v > 0
            for k, v in bonus.items()
        ):
            raise SeedError(f"set '{label}': 'bonus' must map a stat to a positive amount.")
        sets[label] = GearSet(
            name=str(merged["name"]),
            pieces=[str(p) for p in pieces],
            bonus={str(k): int(v) for k, v in bonus.items()},
        )
    return sets


def load_zones(path: Path, known_rooms: set[str]) -> dict[str, Zone]:
    """Load a seed's optional AREAS: named groups of rooms with a reset policy.

    {} if the seed ships no zones.yaml; fails loud on a bad one. Every member room must exist
    in this seed, no room may belong to two zones, `reset_mode` must be a known mode, and
    `beats_between` must be a positive integer. `known_rooms` is the loaded room-label set, so
    a zone can never name a room that isn't there (the cross-component gate, as for items/npcs).
    """
    if not path.exists():
        return {}
    entries, template = _open_seed_bin(path, "zone")
    zones: dict[str, Zone] = {}
    claimed: dict[str, str] = {}  # room label -> the zone that already claims it
    for label, fields in entries.items():
        merged: dict[str, Any] = {
            "name": _phrase(label).title(),
            "rooms": [],
            "reset_mode": "never",
            "beats_between": 10,
        }
        merged.update(template)
        merged.update(fields)
        _inspect_required_types(
            label,
            merged,
            (("name", str), ("rooms", list), ("reset_mode", str), ("beats_between", int)),
        )
        if isinstance(merged["beats_between"], bool) or merged["beats_between"] <= 0:
            raise SeedError(
                f"zone '{label}': 'beats_between' must be a positive integer, "
                f"got {merged['beats_between']!r}."
            )
        if merged["reset_mode"] not in RESET_MODES:
            raise SeedError(
                f"zone '{label}': 'reset_mode' must be one of {RESET_MODES}, "
                f"got {merged['reset_mode']!r}."
            )
        if not merged["rooms"]:
            raise SeedError(f"zone '{label}': must name at least one member room.")
        members: list[str] = []
        for room in merged["rooms"]:
            if not isinstance(room, str):
                raise SeedError(f"zone '{label}': room labels must be strings, got {room!r}.")
            if room not in known_rooms:
                raise SeedError(
                    f"zone '{label}' names room '{room}', which does not exist in this seed."
                )
            if room in claimed:
                raise SeedError(
                    f"zone '{label}' claims room '{room}', already claimed by "
                    f"zone '{claimed[room]}'. A room belongs to at most one zone."
                )
            claimed[room] = label
            members.append(room)
        zone = Zone(
            name=str(merged["name"]),
            rooms=members,
            reset_mode=str(merged["reset_mode"]),
            beats_between=int(merged["beats_between"]),
        )
        _attach_zone_metadata(label, merged, zone)
        zones[label] = zone
    return zones


def _attach_zone_metadata(label: str, merged: dict[str, Any], zone: Zone) -> None:
    """Fold in the optional Layer-2 geographic metadata (region / level band / biome), validating
    each field only if the zone declares it. Absent fields stay absent -- a zone without metadata
    is untouched, so the change is backward-compatible. A malformed field fails loud, as every gate.
    """
    region = merged.get("region")
    if region is not None:
        if not isinstance(region, str) or not region.strip():
            raise SeedError(f"zone '{label}': 'region' must be a non-empty string.")
        zone["region"] = region
    lo = merged.get("level_min")
    hi = merged.get("level_max")
    for name, value in (("level_min", lo), ("level_max", hi)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            raise SeedError(f"zone '{label}': '{name}' must be an integer.")
    if lo is not None:
        if lo < 1 or lo > 300:
            raise SeedError(f"zone '{label}': 'level_min' must be within 1-300, got {lo}.")
        zone["level_min"] = lo
    if hi is not None:
        if hi < 1 or hi > 300:
            raise SeedError(f"zone '{label}': 'level_max' must be within 1-300, got {hi}.")
        zone["level_max"] = hi
    if lo is not None and hi is not None and hi < lo:
        raise SeedError(f"zone '{label}': 'level_max' ({hi}) must be >= 'level_min' ({lo}).")
    biome = merged.get("biome")
    if biome is not None:
        if not isinstance(biome, str) or not biome.strip():
            raise SeedError(f"zone '{label}': 'biome' must be a non-empty string.")
        zone["biome"] = biome
