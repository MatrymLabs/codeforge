"""Test twin for kernel/world/delve_sets.py -- a matched gear set per dungeon, across its delve.

Acceptance: each dungeon forges a three-piece set (head/body/arm, distinct slots), one piece hung on
each delve trash foe as a guaranteed drop, with a set bonus the engine pays only when all three are
worn. Refusal: a shallow delve (< 2 trash foes) forms no set. Determinism: same dungeon, same set.
"""

from __future__ import annotations

from kernel.world.delve_sets import SET_PREFIX, forge_delve_sets, is_delve_set_piece
from kernel.world.gearsets import active_set_bonuses
from kernel.world.seed import Npc

_DUNGEONS = [{"room": "the_black_hollow", "name": "The Black Hollow", "level": 50}]


def _foe(room: str, depth: int) -> Npc:
    return Npc(
        name=f"a {room} lurker",
        keywords=["lurker"],
        location=f"{room}_delve_{depth}",
        dialogue=[],
        next_line=0,
        hp=80,
        hp_now=80,
        xp=0,
        atk=6,
        level=50,
        ambient=True,
    )


def _delve_npcs(room: str, depth_count: int = 3) -> dict[str, Npc]:
    return {f"{room}_delve_{d}_foe": _foe(room, d) for d in range(1, depth_count + 1)}


def test_each_delve_trash_foe_drops_one_set_piece_in_a_distinct_slot():
    npcs = _delve_npcs("the_black_hollow")
    items, sets = forge_delve_sets(_DUNGEONS, npcs)
    assert len(items) == 3 and all(is_delve_set_piece(label) for label in items)
    slots = {item["slot"] for item in items.values()}
    assert slots == {"head", "body", "arm"}, "the three pieces wear together, never fighting a slot"
    for depth in (1, 2, 3):
        drops = npcs[f"the_black_hollow_delve_{depth}_foe"]["drops"]
        assert any(is_delve_set_piece(d) for d in drops), f"foe {depth} carries a set piece"


def test_the_bonus_pays_only_on_a_complete_set():
    _, sets = forge_delve_sets(_DUNGEONS, _delve_npcs("the_black_hollow"))
    gear_set = sets[f"{SET_PREFIX}the_black_hollow"]
    full = set(gear_set["pieces"])
    assert active_set_bonuses(full, sets) == gear_set["bonus"], "wearing all three earns the bonus"
    assert active_set_bonuses(set(list(full)[:2]), sets) == {}, "two of three earns nothing"


def test_the_set_is_named_for_its_dungeon():
    _, sets = forge_delve_sets(_DUNGEONS, _delve_npcs("the_black_hollow"))
    assert sets[f"{SET_PREFIX}the_black_hollow"]["name"] == "The Black Hollow set"


def test_a_shallow_delve_forms_no_set():
    # only one trash foe -> fewer than two pieces -> no set worth collecting
    items, sets = forge_delve_sets(_DUNGEONS, _delve_npcs("the_black_hollow", depth_count=1))
    assert sets == {}


def test_forging_is_deterministic():
    a = forge_delve_sets(_DUNGEONS, _delve_npcs("the_black_hollow"))
    b = forge_delve_sets(_DUNGEONS, _delve_npcs("the_black_hollow"))
    assert a == b
