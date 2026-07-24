"""CARD: spiral -- procedurally extend the Great Spiral toward the summit (the 1-255 climb).

The world bible frames the Spiral as an endless ascent of Coils, each with a Gate-boss climbing in
level (s.24). Hand-authoring 25 more YAML Coils to reach the level ceiling would be repetitive
filler; instead this is a DETERMINISTIC generator: given a seed's `spiral.yaml` config, it produces
seed-SHAPED Coils (rooms + a foe + a lethal Gate-boss each) that climb from a base level to the
summit. The output is ordinary Room/Npc data, run through the same loader gates -- the world stays
data, the generator is only its factory. No randomness (determinism keeps the world reproducible).

`generate_spiral(config, existing_rooms)` returns (rooms, npcs, attach_up) to merge into the world:
each Coil is an ascent room (a husk foe) and a landing room (the Gate-boss), chained up from the
seed's `attach` room to the summit, where the final Gate-boss stands at the top_level cap.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from parts.shelf.reward_curve import LEVEL_MAX
from parts.world.seed import Npc, Room, SeedError

_ORDINALS = {4: "Fourth", 5: "Fifth", 6: "Sixth", 7: "Seventh", 8: "Eighth", 9: "Ninth"}


def _ordinal(n: int) -> str:
    """A display ordinal for a Coil number (Fourth, Fifth, ... then plain '12th' past the named)."""
    if n in _ORDINALS:
        return _ORDINALS[n]
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def load_spiral_config(path: Path) -> dict[str, Any] | None:
    """Read a seed's optional spiral.yaml. Returns None when the seed ships none (no extension);
    fails loud (SeedError) on a malformed one -- required int fields, a sane climb, a real cap."""
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise SeedError("spiral.yaml must be a mapping of config keys.")
    required = ("attach", "first_coil", "base_level", "levels_per_coil", "top_level")
    missing = [k for k in required if k not in raw]
    if missing:
        raise SeedError(f"spiral.yaml is missing required key(s): {', '.join(missing)}.")
    if not isinstance(raw["attach"], str):
        raise SeedError("spiral.yaml 'attach' must be a room label (string).")
    for key in ("first_coil", "base_level", "levels_per_coil", "top_level"):
        value = raw[key]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise SeedError(f"spiral.yaml '{key}' must be a positive integer, got {value!r}.")
    if raw["levels_per_coil"] < 1:
        raise SeedError("spiral.yaml 'levels_per_coil' must be >= 1 (the climb must ascend).")
    if not raw["base_level"] <= raw["top_level"] <= LEVEL_MAX:
        raise SeedError(
            f"spiral.yaml needs base_level <= top_level <= {LEVEL_MAX} "
            f"(got base {raw['base_level']}, top {raw['top_level']})."
        )
    return raw


def _boss_level(config: dict[str, Any], n: int) -> int:
    """The Gate-boss level for Coil `n`, climbing from base and capped at the summit."""
    raw = config["base_level"] + (n - config["first_coil"]) * config["levels_per_coil"]
    return min(config["top_level"], raw)


def _coil_numbers(config: dict[str, Any]) -> list[int]:
    """The Coil numbers to generate: from first_coil up to (and including) the summit Coil -- the
    first whose Gate-boss reaches top_level. A hard cap of 500 Coils backstops a bad config."""
    numbers: list[int] = []
    n = config["first_coil"]
    while n < config["first_coil"] + 500:
        numbers.append(n)
        if _boss_level(config, n) >= config["top_level"]:
            break
        n += 1
    return numbers


def _foe(label: str, name: str, room: str, level: int, *, boss: bool) -> Npc:
    """A generated Spiral foe: a husk (normal) or a lethal Gate-boss, with level/tier-scaled reward
    and hp/atk tuned to its level. Bosses drop a Coil keystone (an existing accessory prototype)."""
    hp = (90 if boss else 50) + level * (5 if boss else 3)
    atk = (14 if boss else 8) + level // 2
    npc = Npc(
        name=name,
        keywords=label.split("_"),
        location=room,
        dialogue=[f"{name} rises from the forge-storm of the high Spiral."],
        next_line=0,
        hp=hp,
        hp_now=hp,
        xp=0,
        atk=atk,
        aggressive=True,
        level=level,
        tier="boss" if boss else "normal",
    )
    if boss:
        npc["lethal"] = True
        npc["drops"] = ["coil_keystone"]
    return npc


def generate_spiral(
    config: dict[str, Any], existing_rooms: dict[str, Room]
) -> tuple[dict[str, Room], dict[str, Npc], str]:
    """Generate the procedural Spiral above the seed's Coils. Returns (rooms, npcs, first_room):
    a chain of Coils climbing from `attach` to the summit, and the room `attach.up` should point to.

    Fails loud if `attach` is not a real room -- a generator that hangs its stair on nothing is a
    seed bug, not a silent no-op."""
    attach = config["attach"]
    if attach not in existing_rooms:
        raise SeedError(f"spiral.yaml 'attach' names room '{attach}', which is not in this seed.")
    rooms: dict[str, Room] = {}
    npcs: dict[str, Npc] = {}
    numbers = _coil_numbers(config)
    for index, n in enumerate(numbers):
        boss_level = _boss_level(config, n)
        summit = boss_level >= config["top_level"]
        ascent_id, landing_id = f"coil_{n}_ascent", f"coil_{n}_landing"
        below = attach if index == 0 else f"coil_{numbers[index - 1]}_landing"
        above = "" if summit else f"coil_{numbers[index + 1]}_ascent"

        ord_name = _ordinal(n)
        rooms[ascent_id] = Room(
            name=f"The {ord_name} Coil Ascent",
            desc=(
                f"The {ord_name} turn of the Great Spiral climbs higher into the forge-storm, the "
                "old Coilwork singing with charge. Husks of fallen climbers walk the steps. The "
                "stair goes on, up, toward the landing above."
            ),
            exits={"down": below, "up": landing_id},
        )
        if summit:
            landing_desc = (
                "The summit of the Great Spiral: a vast forged crown above the world, where the "
                "Forge at the Spiral's heart burns close. The Spiral Sovereign keeps the last "
                "stair -- the final Gate-boss of the whole ascent. Beyond it, the Forge itself."
            )
        else:
            landing_desc = (
                f"The {ord_name} Coil's landing, ringed in cold ascent-lamps above a fall with no "
                "bottom. Its Gate-boss keeps the stair; best it, and the Spiral climbs on above."
            )
        landing_exits = {"down": ascent_id}
        if above:
            landing_exits["up"] = above
        rooms[landing_id] = Room(
            name=("The Spiral Summit" if summit else f"The {ord_name} Coil Landing"),
            desc=landing_desc,
            exits=landing_exits,
        )

        husk_id = f"spiral_husk_{n}"
        npcs[husk_id] = _foe(
            husk_id,
            f"a Coil husk of the {ord_name} turn",
            ascent_id,
            max(1, boss_level - 4),
            boss=False,
        )
        boss_id = f"spiral_gate_{n}"
        boss_name = "the Spiral Sovereign" if summit else f"the {ord_name} Coil Gate-boss"
        npcs[boss_id] = _foe(boss_id, boss_name, landing_id, boss_level, boss=True)

    first_room = f"coil_{numbers[0]}_ascent" if numbers else attach
    return rooms, npcs, first_room
