"""CARD: delve -- expand the map's dungeon mouths into multi-room delves with a boss ladder.

The map marks its dungeons, but each shipped as a single room with one guardian at the mouth -- a
door, not a dungeon. This is the world-generation lever (rooms via wildlands, creatures via
bestiary, gear via armory) pointed at DUNGEONS: it reads a compact manifest (dungeons.yaml, one row
per mouth: name, zone, level, biome) and sinks a DESCENT below each mouth -- a chain of chambers,
each with a foe that grows deadlier as you descend, ending in a deep BOSS out-levelling the mouth's
own guardian and drops real gear. So a dungeon becomes a delve: a boss ladder from the door to the
depths, with a payoff at the bottom.

The descent's trash foes are ambient (a fight, no bounty flood); the deep boss is a named notable
(a hunt bounty + armory gear, wired in world assembly). Pure and deterministic like the other
generators -- the same dungeon always sinks the same delve -- merged through the same loader gates
as authored rooms. `generate_delves` returns rooms/npcs; `wire_delve_mouths` opens each mouth
`down` into its descent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from kernel.world.bestiary import make_beast, make_notable
from kernel.world.seed import BlueprintError, Npc, Room

_DEPTH = 4  # chambers in a delve's descent below the mouth
_BOSS_BUMP = 5  # the deep boss out-levels the dungeon's mouth guardian by this many levels

# A descent should READ like one: a chamber names how deep it sits, so the threshold and the boss's
# lair do not read alike. Four stages (a short title + a lead), mapped across `_DEPTH` by fraction,
# so the count is robust if the depth changes; the last chamber always lands on the lair.
_CHAMBER_STAGES = (
    (
        "the threshold",
        "The descent into {name} begins here, where the last of the daylight fails. {note} {mood}",
    ),
    (
        "the mid-depths",
        "Deeper beneath {name}, the passage narrows and the air turns stale and close. "  # noqa: ISC004
        "{note} {mood}",
    ),
    (
        "the deep",
        "Far under {name} now, the weight of all that stone overhead is a thing you can feel. "  # noqa: ISC004
        "{note} {mood}",
    ),
    (
        "the lair",
        "The way opens into a great vault at the root of {name}, where the deep thing makes its "  # noqa: ISC004
        "lair. {note} {mood}",
    ),
)

# The stone and air a delve INHERITS from the Reach it sinks below, so a dungeon under the ice reads
# unlike one under the jungle. Keyed by the same biome names as the bestiary; unknown -> plain note.
_BIOME_DELVE_NOTE: dict[str, str] = {
    "temperate-meadow": "Old field-stone and the roots of the world above lace the walls.",
    "wild-forest": "Pale roots thread the ceiling and the walls breathe a green, living damp.",
    "highland-moor": "The walls are raw granite, and cold peat-water seeps between the courses.",
    "coastal-strand": "Brine crusts the stone and, far off, the walls answer the pull of the tide.",
    "glacier-waste": "The passage is sheathed in black ice that groans and ticks as you pass.",
    "volcanic-flats": "The rock sweats a dry heat and glows a dull red in the deepest seams.",
    "living-jungle": "Living vine has breached the old stone, and pale things grow in the dark.",
    "salt-desert": "Drifted salt and dry bone floor the passage, and the air is a desiccated hush.",
}
_DEFAULT_DELVE_NOTE = "The walls are old, worked stone, and the dark between them is very old."

_MOODS = (
    "Cold air breathes up from below.",
    "The dark thickens; your lamp gutters.",
    "Old bones crunch underfoot.",
    "A wet dripping echoes from deeper still.",
    "The stone itself seems to hold its breath.",
)


def load_dungeons(path: Path) -> list[dict[str, Any]] | None:
    """Read a seed's optional dungeons.yaml (room-id -> {name, zone, level, biome}). Returns None
    when the seed ships none. Fails loud on a malformed row (missing field, bad level)."""
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise BlueprintError("dungeons.yaml must be a mapping of room-id to dungeon config.")  # noqa: TRY003
    configs: list[dict[str, Any]] = []
    for room, cfg in raw.items():
        if not isinstance(cfg, dict):
            raise BlueprintError(f"dungeon {room!r} must be a mapping of config keys.")  # noqa: TRY003
        merged = {**cfg, "room": room}
        for key in ("name", "zone", "level", "biome"):
            if key not in merged:
                raise BlueprintError(f"dungeon {room!r} is missing required key {key!r}.")  # noqa: TRY003
        level = merged["level"]
        if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 300:  # noqa: PLR2004
            raise BlueprintError(f"dungeon {room!r}: 'level' must be an int 1..300, got {level!r}.")  # noqa: TRY003
        configs.append(merged)
    return configs


def boss_chamber(mouth: str) -> str:
    """The label of a dungeon's deepest chamber -- where its deep boss waits (and where the delve's
    lore inscription is carved). Public so other generators can name it without knowing `_DEPTH`."""
    return f"{mouth}_delve_{_DEPTH}"


_VAULT_OFF = 2  # the mid chamber a treasure vault forks from (a trash chamber, never the lair)
_VAULT_DESC = (
    "A side-passage opens off the descent into {name} onto a low treasure-vault: old strongboxes "
    "and the dust-furred hoard of whatever the deep buried here. {note} Something has kept this "
    "hoard a long age, and it has noticed you."
)


def _vault_room(name: str, biome: str) -> Room:
    """A treasure-vault pocket branching off the descent: a real fork, so a delve is a choice (take
    the detour for the hoard, or press straight for the boss) and not a single corridor."""
    note = _BIOME_DELVE_NOTE.get(biome, _DEFAULT_DELVE_NOTE)
    desc = _VAULT_DESC.format(name=name, note=note)
    return Room(name=f"{name}, the treasure-vault", desc=desc, exits={})


def _chamber(name: str, idx: int, biome: str) -> Room:
    """One chamber of a delve, read as a stage of a DESCENT: the deeper it sits the graver the lead
    (threshold -> mid-depths -> deep -> lair), carrying the biome's inherited stone-and-air note and
    a per-depth mood. The stage is by fraction of `_DEPTH`, so the bottom is always the lair."""
    stage_word, lead = _CHAMBER_STAGES[(idx - 1) * len(_CHAMBER_STAGES) // _DEPTH]
    note = _BIOME_DELVE_NOTE.get(biome, _DEFAULT_DELVE_NOTE)
    mood = _MOODS[idx % len(_MOODS)]
    desc = lead.format(name=name, note=note, mood=mood)
    return Room(name=f"{name}, {stage_word}", desc=desc, exits={})


def generate_delves(
    configs: list[dict[str, Any]],
) -> tuple[dict[str, Room], dict[str, Npc]]:
    """Sink a descent below every dungeon mouth: `_DEPTH` chambers, each with a foe that deepens in
    level, ending in a named deep boss (non-ambient -> a bounty; armed with gear in world assembly).
    Returns (rooms, npcs) to merge; `wire_delve_mouths` opens each mouth into its first chamber."""
    rooms: dict[str, Room] = {}
    npcs: dict[str, Npc] = {}
    for cfg in configs:
        mouth, name = cfg["room"], str(cfg["name"])
        biome, base = str(cfg["biome"]), int(cfg["level"])
        prev = mouth
        for i in range(1, _DEPTH + 1):
            label = f"{mouth}_delve_{i}"
            room = _chamber(name, i, biome)
            room["exits"]["up"] = prev  # back toward the mouth
            if i < _DEPTH:
                room["exits"]["down"] = f"{mouth}_delve_{i + 1}"
                # a trash foe, deadlier the deeper you go (ambient: a fight, but no bounty)
                npcs[f"{label}_foe"] = make_beast(biome, base + i, i, label)
            else:
                # the deep boss: a named notable, boss-tier and lethal, out-levelling the mouth
                boss = make_notable(biome, base + _BOSS_BUMP, i, label, 5)
                boss["tier"] = "boss"
                boss["lethal"] = True
                boss["aggressive"] = False  # a hunt at the bottom, not an ambush at the door
                npcs[f"{mouth}_deep_boss"] = boss
            rooms[label] = room
            prev = label
            # A treasure vault forks off one mid chamber: an OPTIONAL pocket with a named guardian
            # (an ambush, unlike the patient deep boss), so clearing a delve to the last strongbox
            # is a choice with a reward. Guarded below the deep boss's level, so it stays the lord.
            if i == _VAULT_OFF and _DEPTH > _VAULT_OFF + 1:
                vault_label = f"{mouth}_delve_vault"
                room["exits"]["vault"] = vault_label
                vault = _vault_room(name, biome)
                vault["exits"]["out"] = label
                rooms[vault_label] = vault
                guard = make_notable(biome, base + _VAULT_OFF + 1, i, vault_label, 6)
                guard["aggressive"] = True  # it sits the hoard and will not let you at it
                npcs[f"{mouth}_vault_guard"] = guard
    return rooms, npcs


def wire_delve_mouths(world: dict[str, Room], configs: list[dict[str, Any]]) -> None:
    """Open each dungeon mouth `down` into its descent's first chamber, in place. The mouth room is
    the authored place room; its guardian stays at the door, the delve sinks below."""
    for cfg in configs:
        mouth = cfg["room"]
        if mouth in world:  # a seed may omit a dungeon's mouth room; skip rather than fail the boot
            world[mouth]["exits"].setdefault("down", f"{mouth}_delve_1")
