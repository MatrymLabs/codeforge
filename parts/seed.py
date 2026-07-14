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

# A seed IS a game. The engine loads one seed pack at startup; swap the seed and
# codeforge boots a different game (fantasy `first-forge`, `spiral-ascent`, ...).
# Selection is by the FORGE_SEED env var, read once at import -- you choose which
# program the proving ground runs when it powers on, not while it's running.
# Default: the repo's seeds/ dir. CODEFORGE_SEEDS_ROOT overrides it for installed /
# containerized deploys where the package lives apart from the seed files.
_default_seeds_root = Path(__file__).resolve().parent.parent / "seeds"
SEEDS_ROOT = Path(os.environ.get("CODEFORGE_SEEDS_ROOT", str(_default_seeds_root)))
DEFAULT_SEED = "first-forge"
SEED_NAME = os.environ.get("FORGE_SEED", DEFAULT_SEED)
SEED_DIR = SEEDS_ROOT / SEED_NAME


def available_seeds() -> list[str]:
    """Every installed game: seed dirs that carry a rooms.yaml, alphabetical."""
    if not SEEDS_ROOT.is_dir():
        return []
    return sorted(p.name for p in SEEDS_ROOT.iterdir() if (p / "rooms.yaml").is_file())


LABEL_RE = re.compile(r"^[a-z][a-z0-9_]*$")
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


class Door(TypedDict):
    """The shape every door must have: a lockable barrier on one room's exit."""

    name: str
    keywords: list[str]
    blocks: tuple[str, str]  # (room_label, direction) -- the exit this door guards
    locked: bool
    key_id: str  # the item label that unlocks it, or "" for a door opened by other means


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


class QuestStep(TypedDict):
    """One move in a quest: from `state`, event `event` advances to `to`; `effect` is optional.

    World-event triggers let an arc advance from a real action instead of only the `quest <event>`
    verb (which always stays a fallback, so a trigger can never dead-end the arc):
      `on_defeat` -- an NPC label whose defeat in combat fires this step;
      `on_take`   -- an item label whose pickup fires it;
      `on_enter`  -- a room label whose entry fires it.
    """

    state: str
    event: str
    to: str
    effect: NotRequired[str]
    on_defeat: NotRequired[str]
    on_take: NotRequired[str]
    on_enter: NotRequired[str]


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
        tagged = loc if loc == "player" else f"room:{loc}"
        items[label] = Item(
            name=merged["name"],
            keywords=merged["keywords"],
            location=tagged,
            slot=merged["slot"],
            mods=dict(merged["mods"]),
        )
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
            ),
        )
        if merged["atk"] < 0:
            raise SeedError(
                f"NPC '{label}' has a negative atk ({merged['atk']}); "
                "counter-attack damage cannot be negative."
            )
        npcs[label] = Npc(
            name=merged["name"],
            keywords=merged["keywords"],
            location=merged["location"],
            dialogue=merged["dialogue"],
            next_line=0,
            hp=merged["hp"],
            hp_now=merged["hp"],
            xp=merged["xp"],
            atk=merged["atk"],
        )
    return npcs


def inspect_world_links(
    rooms: dict[str, Room], items: dict[str, Item], npcs: dict[str, Npc]
) -> None:
    """The cross-component gate: everything placed somewhere must be
    placed in a room that exists. Runs at boot, before any player."""
    for label, item in items.items():
        loc = item["location"]
        if loc != "player" and loc.removeprefix("room:") not in rooms:
            raise SeedError(
                f"Item '{label}' is placed in room '{loc.removeprefix('room:')}', "
                "which does not exist."
            )
    for label, npc in npcs.items():
        if npc["location"] not in rooms:
            raise SeedError(
                f"NPC '{label}' is placed in room '{npc['location']}', which does not exist."
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
        for trigger in ("on_defeat", "on_take", "on_enter"):
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
        doors[label] = Door(
            name=merged["name"],
            keywords=list(merged["keywords"]),
            blocks=(str(blocks[0]), str(blocks[1])),
            locked=bool(merged["locked"]),
            key_id=str(merged["key_id"]),
        )
    return doors
