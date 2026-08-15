"""CARD: spiral -- procedurally extend the Forgeward Road outward across the deepening wilds.

The world is one big FLAT land -- no vertical climb. The Forgeward Road runs OUTWARD from the
settled Reaches into the deepening wilds toward the Forge at the world's far heart, each stretch a
higher-level `march`. Hand-authoring hundreds of YAML marches to the ceiling would be repetitive
filler; instead this is a DETERMINISTIC generator: given a seed's `spiral.yaml` config, it produces
seed-SHAPED marches (a road room + a waystation room, each with a foe and a lethal road-warden) that
band from a base level to the ceiling. The output is ordinary Room/Npc data, run through the same
loader gates -- the world stays data, the generator is only its factory. No randomness (determinism
keeps the world reproducible). Internal labels keep the legacy `coil_`/`spiral_` prefixes (they are
frozen identifiers, never shown); the player sees marches and waystations on a flat road, running
`east` (onward, deeper) and `west` (back), never up.

`generate_spiral(config, existing_rooms)` returns (rooms, npcs, first_room) to merge into the world:
each march is a road room (a husk foe) and a waystation room (the warden), chained EAST from the
seed's `attach` room to the far Sovereign at the top_level cap. The caller wires `attach.east`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from kernel.shelf.reward_curve import LEVEL_MAX
from kernel.world.seed import BlueprintError, Npc, Room, Zone

# Stable labels for the far end of the road + its Sovereign, so a capstone quest can name them no
# matter how many marches a config generates. Legacy `spiral_` prefixes are frozen identifiers only.
SUMMIT_ROOM = "the_spiral_summit"
SUMMIT_BOSS = "spiral_sovereign"

_ORDINALS = {4: "Fourth", 5: "Fifth", 6: "Sixth", 7: "Seventh", 8: "Eighth", 9: "Ninth"}

# Each march takes a deterministic elemental theme, cycled by march number, so the road is a varied
# gauntlet instead of one room fifty times. A themed march's foes strike with its element, and its
# road-warden RESISTS that element but is WEAK to a counter -- so the elemental system (examine,
# resistances, the co-pilot's advice) turns the frontier into a real tactical journey: read the
# march, bring the right element. No randomness -- the cycle is by index, so the world stays
# reproducible. `adj` flavours the rooms/foes; `element` is the foes' attack type; a warden resists
# `element` and is weak to `weak`; `warden` names the road-warden.
_THEMES = [
    {
        "adj": "forge-storm",
        "el": "FIR",
        "weak": "ICE",
        "warden": "Emberwrought",
        "drop": "ember_brand",
    },
    {
        "adj": "frost-wracked",
        "el": "ICE",
        "weak": "FIR",
        "warden": "Rimebound",
        "drop": "rime_edge",
    },
    {"adj": "storm-wound", "el": "LGT", "weak": "ERT", "warden": "Stormshod", "drop": "storm_pike"},
    {
        "adj": "shadow-eaten",
        "el": "DRK",
        "weak": "HLY",
        "warden": "Nightclad",
        "drop": "shadow_fang",
    },
    {"adj": "stonebound", "el": "ERT", "weak": "WND", "warden": "Stoneworn", "drop": "stone_maul"},
]


def _theme(config: dict[str, Any], n: int) -> dict[str, str]:
    """The elemental theme for march `n`, cycled deterministically from the first."""
    return _THEMES[(n - config["first_coil"]) % len(_THEMES)]


def _has_wayside(config: dict[str, Any], n: int) -> bool:
    """Whether march `n` grows an exploration wayside off the road. Every OTHER march does (a rhythm
    from the first march), so the flat frontier reads as a wide land with side-tracks to discover,
    not a metronomic corridor with one on every stretch. Deterministic (by index, not chance)."""
    return (n - config["first_coil"]) % 2 == 0


def _ordinal(n: int) -> str:
    """A display ordinal for a march number (Fourth, Fifth, ... then plain '12th' past named)."""
    if n in _ORDINALS:
        return _ORDINALS[n]
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def load_spiral_config(path: Path) -> dict[str, Any] | None:
    """Read a seed's optional spiral.yaml. Returns None when the seed ships none (no extension);
    fails loud (BlueprintError) on a malformed one -- required int fields, a sane band, a real
    cap."""
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise BlueprintError("spiral.yaml must be a mapping of config keys.")
    required = ("attach", "first_coil", "base_level", "levels_per_coil", "top_level")
    missing = [k for k in required if k not in raw]
    if missing:
        raise BlueprintError(f"spiral.yaml is missing required key(s): {', '.join(missing)}.")
    if not isinstance(raw["attach"], str):
        raise BlueprintError("spiral.yaml 'attach' must be a room label (string).")
    for key in ("first_coil", "base_level", "levels_per_coil", "top_level"):
        value = raw[key]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise BlueprintError(f"spiral.yaml '{key}' must be a positive integer, got {value!r}.")
    if raw["levels_per_coil"] < 1:
        raise BlueprintError("spiral.yaml 'levels_per_coil' must be >= 1 (the road must deepen).")
    if not raw["base_level"] <= raw["top_level"] <= LEVEL_MAX:
        raise BlueprintError(
            f"spiral.yaml needs base_level <= top_level <= {LEVEL_MAX} "
            f"(got base {raw['base_level']}, top {raw['top_level']})."
        )
    if "summit_drop" in raw and not isinstance(raw["summit_drop"], str):
        raise BlueprintError("spiral.yaml 'summit_drop' must be an item label (string).")
    return raw


def _boss_level(config: dict[str, Any], n: int) -> int:
    """The road-warden level for march `n`, deepening from base and capped at the far end."""
    raw = config["base_level"] + (n - config["first_coil"]) * config["levels_per_coil"]
    return min(config["top_level"], raw)


def _coil_numbers(config: dict[str, Any]) -> list[int]:
    """The march numbers to generate: from first_coil out to (and including) the final march -- the
    first whose road-warden reaches top_level. A hard cap of 500 marches backstops a bad config."""
    numbers: list[int] = []
    n = config["first_coil"]
    while n < config["first_coil"] + 500:
        numbers.append(n)
        if _boss_level(config, n) >= config["top_level"]:
            break
        n += 1
    return numbers


def _foe(
    label: str,
    name: str,
    room: str,
    level: int,
    *,
    boss: bool,
    element: str | None = None,
    resistances: dict[str, str] | None = None,
    drops: list[str] | None = None,
) -> Npc:
    """A generated Forgeward Road foe: a husk (normal), an optional wayside guardian (normal but
    carrying loot), or a lethal road-warden (boss), with level/tier-scaled reward and hp/atk tuned
    to its level. An optional `element` types its blows; an optional `resistances` grid makes a
    warden an elemental puzzle. `drops` are levelled gear prototypes the combat affix factory then
    rolls a rarity onto (varied loot); a boss with no `drops` falls back to the road keystone."""
    hp = (90 if boss else 50) + level * (5 if boss else 3)
    atk = (14 if boss else 8) + level // 2
    npc = Npc(
        name=name,
        keywords=label.split("_"),
        location=room,
        dialogue=[f"{name} rises from the wilds along the Forgeward Road."],
        next_line=0,
        hp=hp,
        hp_now=hp,
        xp=0,
        atk=atk,
        aggressive=True,
        level=level,
        tier="boss" if boss else "normal",
    )
    if element:
        npc["attack_element"] = element
    if resistances:
        npc["resistances"] = resistances
    if boss:
        npc["lethal"] = True
        npc["drops"] = drops if drops is not None else ["coil_keystone"]
    elif drops is not None:
        npc["drops"] = drops
    return npc


def generate_spiral(
    config: dict[str, Any], existing_rooms: dict[str, Room]
) -> tuple[dict[str, Room], dict[str, Npc], str]:
    """Generate the procedural Forgeward Road beyond the seed's hand-authored marches. Returns
    (rooms, npcs, first_room): a chain of marches running EAST from `attach` to the far Sovereign,
    and the room `attach.east` should point to.

    Fails loud if `attach` is not a real room -- a generator that hangs its road on nothing is a
    seed bug, not a silent no-op."""
    attach = config["attach"]
    if attach not in existing_rooms:
        raise BlueprintError(
            f"spiral.yaml 'attach' names room '{attach}', which is not in this seed."
        )
    rooms: dict[str, Room] = {}
    npcs: dict[str, Npc] = {}
    numbers = _coil_numbers(config)
    for index, n in enumerate(numbers):
        boss_level = _boss_level(config, n)
        summit = boss_level >= config["top_level"]
        ascent_id = f"coil_{n}_ascent"
        # The far room + boss carry STABLE labels (not the march number) so a capstone quest can
        # reference them regardless of how many marches the config generates.
        landing_id = SUMMIT_ROOM if summit else f"coil_{n}_landing"
        below = attach if index == 0 else f"coil_{numbers[index - 1]}_landing"
        above = "" if summit else f"coil_{numbers[index + 1]}_ascent"

        ord_name = _ordinal(n)
        theme = _theme(config, n)
        # The Forgeward Road runs OUTWARD across the deepening wilds, not up: `east` is onward
        # (deeper, higher level), `west` is back toward the settled world. A flat frontier.
        rooms[ascent_id] = Room(
            name=f"The {ord_name} March",
            desc=(
                f"The {ord_name} march of the Forgeward Road runs on through {theme['adj']} wilds, "
                f"the old Roadwork here run through with {theme['adj']} charge. Husks of fallen "
                "travellers walk the verge. The road goes on east, toward the waystation ahead; "
                "the way home lies back west."
            ),
            exits={"west": below, "east": landing_id},
        )
        if summit:
            landing_desc = (
                "The far end of the Forgeward Road: a vast forged waste at the world's heart, "
                "where the Forge burns close beyond the last horizon. The Sovereign keeps the "
                "final mile -- the last warden of the whole march. Beyond it, the Forge itself."
            )
        else:
            landing_desc = (
                f"The {ord_name} Waystation, a {theme['adj']} ring of cold road-lamps at the edge "
                "of the deeper wilds. Its warden holds the way; best it, and the Forgeward Road "
                "runs on east into the {adj} country ahead. The march lies back west."
            ).replace("{adj}", theme["adj"])
        landing_exits = {"west": ascent_id}
        if above:
            landing_exits["east"] = above
        rooms[landing_id] = Room(
            name=("The Forge's Edge" if summit else f"The {ord_name} Waystation"),
            desc=landing_desc,
            exits=landing_exits,
        )

        # A husk carries the march's element (its blows are typed) but no resistance grid, so it is
        # farmable with any element -- the tactical puzzle is the road-warden, which resists the
        # march's element and is weak to a counter. The far Sovereign stays untyped: a final test of
        # everything, not one more elemental gate.
        husk_id = f"spiral_husk_{n}"
        npcs[husk_id] = _foe(
            husk_id,
            f"a {theme['adj']} husk of the {ord_name} march",
            ascent_id,
            max(1, boss_level - 4),
            boss=False,
            element=theme["el"],
        )
        boss_id = SUMMIT_BOSS if summit else f"spiral_gate_{n}"
        if summit:
            # The far Sovereign's capstone reward: a seed may name a legendary via `summit_drop`
            # (the L-cap boss deserves better than the road keystone); default keeps it if unset.
            summit_drop = config.get("summit_drop")
            npcs[boss_id] = _foe(
                boss_id,
                "the Sovereign",
                landing_id,
                boss_level,
                boss=True,
                drops=[summit_drop] if summit_drop else None,
            )
        else:
            npcs[boss_id] = _foe(
                boss_id,
                f"the {theme['warden']} Warden of the {ord_name} Waystation",
                landing_id,
                boss_level,
                boss=True,
                element=theme["el"],
                resistances={theme["el"]: "Resist", theme["weak"]: "Weak"},
                drops=[theme["drop"]],
            )

        # Exploration off the main road: some marches fork to a WAYSIDE, a dead-end side-track with
        # a hoard-guardian over relic-salvage. It is optional (a normal foe, not a lethal gate), so
        # the flat frontier reads as a wide land to explore, not a single corridor. The branch
        # alternates north/south by index so side-tracks do not all fall the same way. The summit
        # has none: the far end is the finale, not a place to wander off.
        if not summit and _has_wayside(config, n):
            wayside_id = f"coil_{n}_wayside"
            branch = "north" if index % 2 == 0 else "south"
            back = "south" if branch == "north" else "north"
            rooms[ascent_id]["exits"][branch] = wayside_id
            rooms[wayside_id] = Room(
                name=f"The {ord_name} Wayside",
                desc=(
                    f"A side-track off the {ord_name} march, where the old Roadwork forks {branch} "
                    f"into a {theme['adj']} hollow. Relic-salvage from a caravan that never made "
                    f"the waystation lies scattered here, and a guardian stands over it. The march "
                    f"lies back {back}."
                ),
                exits={back: ascent_id},
            )
            # The wayside pays DIFFERENT loot from the main road: the road-wardens drop themed
            # WEAPONS, so a guardian drops the road keystone (an accessory). That gives exploration
            # its own reward type, and spreads the accessory across the frontier instead of gating
            # it behind the far Sovereign at the cap -- a mid-road Forger can earn one by wandering.
            guard_id = f"spiral_wayside_{n}"
            npcs[guard_id] = _foe(
                guard_id,
                f"a {theme['adj']} hoard-guardian of the {ord_name} wayside",
                wayside_id,
                max(1, boss_level - 2),
                boss=False,
                element=theme["el"],
                drops=["coil_keystone"],
            )

    first_room = f"coil_{numbers[0]}_ascent" if numbers else attach
    return rooms, npcs, first_room


def extend_world_with_road(
    world: dict[str, Room], npcs: dict[str, Npc], config: dict[str, Any]
) -> str:
    """Merge the procedural Forgeward Road into a seed's world IN PLACE: generate the marches, add
    their rooms and foes, and grow the attach room's `east` exit onto the first march (flat, no
    climb). Returns the first march's label. The merge happens BEFORE the loader's link check, so
    the generated data is validated by the same gates as the hand-authored world."""
    rooms, road_npcs, first_room = generate_spiral(config, world)
    world.update(rooms)
    npcs.update(road_npcs)
    world[config["attach"]]["exits"]["east"] = first_room
    return first_room


def spiral_zones(config: dict[str, Any]) -> dict[str, Zone]:
    """One AREA per generated march (its road + waystation rooms), so the procedural Forgeward Road
    is not a stretch of anonymous rooms: each march renders its own '[Area: The Nth March]' banner,
    like the hand-authored world, giving the frontier identity and a player their bearings.

    reset_mode is `never` (grouping + banner only): the generated rooms hold no resettable items,
    and felled foes already reassemble in combat, so there is nothing to repop -- the honest policy
    is a named area, not a reset that does nothing. Every generated room lands in one zone."""
    zones: dict[str, Zone] = {}
    for n in _coil_numbers(config):
        boss_level = _boss_level(config, n)
        summit = boss_level >= config["top_level"]
        landing = SUMMIT_ROOM if summit else f"coil_{n}_landing"
        march_rooms = [f"coil_{n}_ascent", landing]
        if not summit and _has_wayside(config, n):
            march_rooms.append(f"coil_{n}_wayside")  # the side-track belongs to its march's area
        # Layer-2 metadata the audit reads: each march is a band of the Forgeward Road, deepening
        # from its predecessor to its road-warden's level, so the generated frontier carries the
        # same region/level-band/biome geography the authored zones do (closing the L43-300 gap).
        lo = max(int(config["base_level"]), boss_level - int(config["levels_per_coil"]) + 1)
        zones[f"spiral_coil_{n}"] = Zone(
            name="The Forge's Edge" if summit else f"The {_ordinal(n)} March",
            rooms=march_rooms,
            reset_mode="never",
            beats_between=20,
            region="The Forgeward Road",
            level_min=lo,
            level_max=boss_level,
            biome="forgeward-marches",
        )
    return zones
