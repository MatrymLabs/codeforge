"""CARD: caves -- the deterministic cave forge: one reusable area-family, varied by region.

The prompt's centerpiece: let a developer generate a small area (a cave) WITHOUT touching the
engine, expanding the world locally while never inventing global canon. This forges one cave from
(region, seed): a navigable room graph of 5 to 18 rooms with at least one branch, one loop, a
memorable landmark, an environmental hazard, a local resource, an optional hidden feature, a
micro-story, and an understandable return route. Every cave inherits its region's identity (biome,
subtypes, creature / hazard / resource families, naming grammar) from
seeds/aethryn/cave_families.yaml, so a Veridia cave reads like Veridia and a Voidscar cave reads
wounded, both from the same forge.

Determinism is the contract: the SAME (region, seed) always produces the SAME cave (random.Random
seeded from a stable string, version-2 sha512 seeding, unaffected by PYTHONHASHSEED). Every cave is
stamped canon_status GENERATED_LOCAL and carries a validation report; a non-empty report is a
generator defect, and the test twin pins it empty across regions and seeds. Forbidden global canon
(gods, the pantheon, Netharion's fate) can only surface as a RUMOR that raises a question, never as
an assertion.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import yaml

from kernel.world import canon, generation_contract
from kernel.world.seed import SeedError, _UniqueKeyLoader

_FAMILIES_PATH = canon.AETHRYN_DIR / "cave_families.yaml"

# The chain runs on the four compass directions (a 4-cycle never collides an axis with its reverse);
# branch and loop edges use the perpendicular in/out and up/down pairs, so no room ever grows two
# exits in one direction.
_COMPASS = ("north", "east", "south", "west")
_REVERSE = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "up": "down",
    "down": "up",
    "in": "out",
    "out": "in",
}

# Every region row must carry these families, or a cave could not inherit its region's identity.
_REQUIRED_FIELDS = (
    "biome",
    "subtypes",
    "entrances",
    "creatures",
    "hazards",
    "resources",
    "landmarks",
    "naming",
)


def load_families(path: Path | None = None) -> dict[str, Any]:
    """Read and VALIDATE the regional cave-family table, merging the shared defaults into each row.
    Fails loud (SeedError) if a canon region has no family or a family is missing a required list,
    so a cave can never be forged without its region's identity."""
    where = path if path is not None else _FAMILIES_PATH
    if not where.exists():
        raise SeedError(f"Cave families file not found: {where}")
    data = yaml.load(where.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(data, dict):
        raise SeedError(f"Cave families file is not a mapping: {where}")
    defaults = data.get("defaults", {})
    families: dict[str, Any] = {}
    known_regions = {r["id"] for r in canon.regions()}
    for region_id, row in data.items():
        if region_id == "defaults":
            continue
        if region_id not in known_regions:
            raise SeedError(f"cave family {region_id!r}: not a canon region")
        merged = {**defaults, **row}
        for field in _REQUIRED_FIELDS:
            if not merged.get(field):
                raise SeedError(f"cave family {region_id!r}: missing required field {field!r}")
        families[region_id] = merged
    # Every canon region deserves a cave family, so the generator never strands a region.
    missing = known_regions - set(families)
    if missing:
        raise SeedError(f"cave families: no family for canon region(s) {sorted(missing)}")
    return families


def cave_regions() -> list[str]:
    """The region ids the cave forge can generate for (every canon region)."""
    return sorted(load_families())


def _rng(region_id: str, seed: int) -> random.Random:
    """A reproducible PRNG for this exact (region, seed): sha512-seeded, PYTHONHASHSEED-immune."""
    return random.Random(f"cave:{region_id}:{seed}")  # nosec B311 -- deterministic gen, not crypto


def _connect(a: dict[str, Any], b: dict[str, Any], direction: str) -> None:
    """Grow a reciprocal exit: a --direction--> b and b --reverse--> a."""
    a["exits"][direction] = b["id"]
    b["exits"][_REVERSE[direction]] = a["id"]


def generate_cave(region_id: str, seed: int, *, size: int | None = None) -> dict[str, Any]:
    """Forge one deterministic cave for a canon region. Returns a GeneratedContentRecord-shaped area
    (provenance + room graph + validation report). The same (region_id, seed, size) always returns
    an identical cave. Raises SeedError for an unknown region or an out-of-band size."""
    families = load_families()
    if region_id not in families:
        raise SeedError(f"cannot generate a cave for unknown region {region_id!r}")
    family = families[region_id]
    region = next(r for r in canon.regions() if r["id"] == region_id)
    rng = _rng(region_id, seed)

    lo, hi = family["min_rooms"], family["max_rooms"]
    total = size if size is not None else rng.randint(lo, hi)
    if not lo <= total <= hi:
        raise SeedError(f"cave size {total} outside the {lo}-{hi} band for {region_id!r}")

    naming = family["naming"]
    subtype = rng.choice(family["subtypes"])
    entrance_kind = rng.choice(family["entrances"])

    def _name() -> str:
        return f"The {rng.choice(naming['adjectives'])} {rng.choice(naming['nouns'])}"

    # The chain is total-1 rooms; the branch room is the +1, so the total lands in band.
    chain_len = total - 1
    rooms: list[dict[str, Any]] = []
    for i in range(chain_len):
        rooms.append(
            {
                "id": f"r{i}",
                "display_name": "The Mouth" if i == 0 else _name(),
                "description": "",
                "exits": {},
                "tags": ["cave", family["biome"]],
                "role": "entrance" if i == 0 else "passage",
            }
        )
    for i in range(chain_len - 1):
        _connect(rooms[i], rooms[i + 1], _COMPASS[i % 4])

    # One branch: a dead-end off an interior room via the perpendicular in/out axis.
    branch_parent = rooms[rng.randint(1, chain_len - 1)]
    branch = {
        "id": f"r{chain_len}",
        "display_name": _name(),
        "description": "",
        "tags": ["cave", family["biome"], "branch"],
        "exits": {},
        "role": "branch",
    }
    rooms.append(branch)
    _connect(branch_parent, branch, "in")

    # One loop: a back-passage between two non-adjacent chain rooms (rooms 1 and 3, always present
    # since the smallest cave has a 4-room chain) via the up/down axis, so the map holds a cycle a
    # player can circle rather than a pure tree.
    _connect(rooms[1], rooms[3], "down")

    # Landmark, hazard, resource: seat each on a distinct room so exploration always finds them.
    landmark = rng.choice(family["landmarks"])
    hazard = rng.choice(family["hazards"])
    resource = rng.choice(family["resources"])
    creature = rng.choice(family["creatures"])
    interior = rooms[1:]
    landmark_room = rng.choice(interior)
    landmark_room["role"] = "landmark"
    landmark_room["feature"] = landmark
    hazard_room = rng.choice(interior)
    hazard_room["hazard"] = hazard
    resource_room = rng.choice(interior)
    resource_room["resource"] = resource

    # An optional hidden feature (roughly one cave in three) tucked onto a room to reward searching.
    hidden = None
    if rng.random() < 0.34 and family.get("hidden"):
        hidden = rng.choice(family["hidden"])
        rng.choice(interior)["hidden"] = hidden

    for room in rooms:
        room["description"] = _describe(room, family, subtype, creature)

    micro_story = _micro_story(rng, family, subtype, landmark)
    rumor = _maybe_rumor(rng)
    livelihood = rng.choice(family["livelihoods"])
    tier = generation_contract.canon_tier_for("GENERATED_LOCAL")

    area: dict[str, Any] = {
        "id": f"gen_cave_{region_id}_{seed}",
        "display_name": _name(),
        "canon_status": "GENERATED_LOCAL",
        "canon_tier": tier,
        "source": "caves.generate_cave",
        "version": 1,
        "template": "cave",
        "region_id": region_id,
        "parent_region": region_id,
        "parent_id": None,
        "biome": family["biome"],
        "subtype": subtype,
        "archetype": _archetype(subtype),
        "entrance": entrance_kind,
        "danger_rating": region["threat_min"],
        "level_band": [region["threat_min"], region["threat_max"]],
        "generation_seed": seed,
        "rooms": rooms,
        "return_room": rooms[0]["id"],
        "landmark": landmark,
        "hazard": hazard,
        "resource": resource,
        "hidden": hidden,
        "micro_story": micro_story,
        "rumor": rumor,
        # The generation-contract narrative fields (deterministic, local, never asserting canon).
        "identity": (
            f"A {subtype} that could only be {region['name']}'s: {landmark}, where the old world "
            f"still bleeds through the rock."
        ),
        "historical_layer": rng.choice(generation_contract.historical_layers()),
        "local_livelihood": livelihood,
        "active_conflict": f"a standing quarrel over who may work {resource}",
        "ordinary_experience": (
            f"For most it is plain hard work: {livelihood}, and an eye on {hazard}."
        ),
        "traversal_identity": f"{_traversal(family['biome'])} past {landmark}",
        "larger_world_clue": _world_clue(region["name"], landmark),
        "unresolved_mystery": f"Who sealed the way past {landmark}, and why?",
        "gameplay_hooks": [
            f"explore the {subtype}",
            f"gather {resource}",
            f"drive off the {creature}",
        ],
        "creator_extension_hooks": [
            "extend the cave deeper",
            "link it to a neighbouring region",
            "seat a local faction here",
        ],
        "state_changes": f"Drive off the {creature} and locals can work {resource} again.",
    }
    area["provenance"] = {
        "source": area["source"],
        "generation_seed": seed,
        "parent_region": region_id,
        "template": "cave",
        "canon_tier": tier,
    }
    area["validation"] = _validation_report(area)
    return area


# Which minor-area archetype a cave subtype falls under (for generation_contract.distribution_gaps),
# by keyword in priority order: a scar or old-world reading wins over the natural default.
_SCAR_WORDS = ("lava", "impact", "fissure", "fracture", "slag", "reality", "euclidean", "altered")
_OLD_WORLD_WORDS = (
    "aqueduct",
    "maintenance",
    "service",
    "laborator",
    "factory",
    "underwork",
    "bunker",
    "vault",
    "sublevel",
    "transit",
    "archive",
    "oath",
    "command",
    "foundry",
)
_PRESENT_USE_WORDS = ("cellar", "mine", "cistern", "shelter", "sewer", "catacomb", "tomb", "quarry")


def _archetype(subtype: str) -> str:
    """Classify a cave subtype into a minor-area archetype the generation contract knows."""
    text = subtype.lower()
    if any(w in text for w in _SCAR_WORDS):
        return "scar"
    if any(w in text for w in _OLD_WORLD_WORDS):
        return "old_world"
    if any(w in text for w in _PRESENT_USE_WORDS):
        return "present_use"
    return "natural"


_TRAVERSAL = {
    "coastal": "a wade through drowned corridors",
    "tundra": "a careful climb over blue ice",
    "aerial": "a climb across broken spans",
    "subterranean": "a long descent into the dark",
    "volcanic": "a hot scramble over cooled slag",
    "jungle": "a push through living tunnels",
    "ancient-forest": "a push through living roots",
    "dark-forest": "a wary crawl through black water",
    "desert": "a crawl through shifting sandstone",
    "wounded": "a disorientating passage where the way does not hold still",
}


def _traversal(biome: str) -> str:
    """How a cave of this biome is moved through (its traversal identity)."""
    return _TRAVERSAL.get(biome, "a crawl through close stone")


def _world_clue(region_name: str, landmark: str) -> str:
    """A thread pointing at a larger mystery: if the region holds a Seven Crown, the clue nods to it
    (never asserting), otherwise it points vaguely at the old world."""
    crown = next((c for c in canon.seven_crowns() if c["region"] == region_name), None)
    if crown:
        return f"Marks near {landmark} echo {crown['mythic_title']}, though no one agrees how."
    return f"Old marks near {landmark} point somewhere larger, and no one agrees where."


def _describe(room: dict[str, Any], family: dict[str, Any], subtype: str, creature: str) -> str:
    """Compose a room's prose from its region's material vocabulary (function and material)."""
    if room["role"] == "entrance":
        return (
            f"The {subtype} opens here; daylight thins behind you and "
            f"the {family['biome']} air cools."
        )
    parts = [f"A {subtype} chamber, its walls close and {_texture(room)}."]
    if room.get("feature"):
        parts.append(f"Here stands {room['feature']}.")
    if room.get("hazard"):
        parts.append(f"Beware {room['hazard']}.")
    if room.get("resource"):
        parts.append(f"You could gather {room['resource']} here.")
    if room.get("hidden"):
        parts.append("Something here does not sit right, as if a detail were concealed.")
    parts.append(f"A {creature} has left its sign.")
    return " ".join(parts)


def _texture(room: dict[str, Any]) -> str:
    """A stable texture phrase seeded by the room id, so the same room always reads the same."""
    textures = ("weeping damp", "cool and still", "close and echoing", "streaked with old mineral")
    return textures[sum(ord(c) for c in room["id"]) % len(textures)]


def _micro_story(rng: random.Random, family: dict[str, Any], subtype: str, landmark: str) -> str:
    """One local, material micro-story. Never global canon: a small human trace, honestly local."""
    who = rng.choice(
        ["a scavenger", "a lost surveyor", "a local family", "an old hermit", "a band of miners"]
    )
    fate = rng.choice(
        [
            "never came back out",
            "left in a hurry",
            "walled part of it off",
            "left a warning scratched deep",
        ]
    )
    return (
        f"Locals say {who} once worked this {subtype} for {rng.choice(family['resources'])}, "
        f"drawn by {landmark}, and {fate}. Whatever the truth, the marks are still here."
    )


def _maybe_rumor(rng: random.Random) -> str | None:
    """Roughly one cave in four carries a RUMOR: it RAISES an open canon question, never answers it
    (the generated-lore guardrail; forbidden global canon may only be raised, marked RUMOR)."""
    if rng.random() < 0.25:
        return f"RUMOR: {rng.choice(canon.unresolved_questions())} No one down here can prove it."
    return None


def _validation_report(area: dict[str, Any]) -> list[str]:
    """The generator's own acceptance gate: every forged cave must satisfy the prompt's cave rules.
    Returns violation lines (empty == a valid cave). A non-empty report is a generator defect."""
    rooms = area["rooms"]
    by_id = {r["id"]: r for r in rooms}
    problems: list[str] = []

    if not 5 <= len(rooms) <= 18:
        problems.append(f"room count {len(rooms)} outside the 5-18 band")

    # Every exit must be reciprocal and land on a real room (navigability).
    edges = 0
    for room in rooms:
        for direction, dest in room["exits"].items():
            edges += 1
            if dest not in by_id:
                problems.append(f"room {room['id']} exit {direction} -> unknown room {dest}")
            elif by_id[dest]["exits"].get(_REVERSE[direction]) != room["id"]:
                problems.append(f"room {room['id']} exit {direction} is not reciprocal")
    undirected = edges // 2

    # A tree has rooms-1 edges; a loop needs at least one more.
    if undirected < len(rooms):
        problems.append("no loop: the cave is a pure tree with no cycle")
    if not any("branch" in r.get("tags", []) for r in rooms):
        problems.append("no branch: the cave has no side passage")

    # Connectivity: every room must be reachable from the entrance (a local find-unreachable). Only
    # known rooms are traversed, so a dangling exit (already reported above) cannot crash the walk.
    seen = {area["return_room"]}
    frontier = [area["return_room"]]
    while frontier:
        room = by_id.get(frontier.pop())
        if room is None:
            continue
        for dest in room["exits"].values():
            if dest in by_id and dest not in seen:
                seen.add(dest)
                frontier.append(dest)
    reachable = seen & set(by_id)
    if reachable != set(by_id):
        problems.append(f"unreachable rooms: {sorted(set(by_id) - reachable)}")

    if not any(r.get("feature") for r in rooms):
        problems.append("no landmark feature placed")
    if not any(r.get("hazard") for r in rooms):
        problems.append("no environmental hazard placed")
    if not any(r.get("resource") for r in rooms):
        problems.append("no local resource placed")
    if not area.get("micro_story"):
        problems.append("no micro-story")
    if area.get("canon_status") != "GENERATED_LOCAL":
        problems.append("generated content must be stamped GENERATED_LOCAL")
    # The generation contract: every required narrative field must be present and non-empty.
    for field in generation_contract.missing_fields(area):
        problems.append(f"generation contract: missing field '{field}'")
    return problems
