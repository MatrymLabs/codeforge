"""Test twin for parts/world/delve.py -- dungeon mouths become multi-room delves.

Acceptance: a dungeon config sinks a connected descent of chambers, each with a foe that deepens in
level, ending in a named non-ambient boss (armory-armed in world assembly), and the mouth opens
`down` into it. Refusal: a malformed dungeon fails loud. Load: the shipped manifest is valid.
"""

from __future__ import annotations

import tempfile
from collections import deque
from pathlib import Path

import pytest
import yaml

from parts.world.delve import _DEPTH, generate_delves, load_dungeons, wire_delve_mouths
from parts.world.seed import SeedError

_CFG = [
    {
        "room": "black_hollow",
        "name": "The Black Hollow",
        "zone": "Duskwood",
        "level": 50,
        "biome": "wild-forest",
    }
]


def test_a_dungeon_sinks_a_connected_descent_of_chambers():
    rooms, npcs = generate_delves(_CFG)
    assert len(rooms) == _DEPTH  # one chamber per depth
    # every chamber is reachable walking `down` from the mouth once the mouth is wired
    world = {"black_hollow": {"name": "mouth", "desc": "d", "exits": {}}}
    world.update(rooms)
    wire_delve_mouths(world, _CFG)
    assert world["black_hollow"]["exits"]["down"] == "black_hollow_delve_1"
    seen, q = {"black_hollow"}, deque(["black_hollow"])
    while q:
        for dest in world[q.popleft()]["exits"].values():
            if dest not in seen:
                seen.add(dest)
                q.append(dest)
    assert set(rooms) <= seen, "a delve chamber is unreachable from the mouth"


def test_foes_deepen_and_the_bottom_holds_a_named_lethal_boss():
    _, npcs = generate_delves(_CFG)
    trash = [n for k, n in npcs.items() if k.endswith("_foe")]
    assert len(trash) == _DEPTH - 1 and all(n.get("ambient") for n in trash)  # trash: no bounty
    levels = [n["level"] for n in trash]
    assert levels == sorted(levels), "delve foes do not deepen in level"
    boss = npcs["black_hollow_deep_boss"]
    assert not boss.get("ambient")  # the boss mints a bounty
    assert boss["tier"] == "boss" and boss["lethal"] and boss["hp"] > 0
    assert boss["level"] > max(levels)  # the deep boss out-levels the trash
    assert boss["name"].split()[0].lower() in boss["keywords"]  # a proper name to hunt


def test_wire_delve_mouths_skips_a_missing_mouth_room():
    world: dict = {}  # the mouth room is absent
    wire_delve_mouths(world, _CFG)  # must not raise
    assert world == {}


def test_load_dungeons_reads_the_shipped_manifest():
    aethryn = Path(__file__).resolve().parent.parent / "seeds" / "aethryn"
    configs = load_dungeons(aethryn / "dungeons.yaml")
    assert configs and all({"room", "name", "zone", "level", "biome"} <= set(c) for c in configs)


@pytest.mark.parametrize(
    "bad, match",
    [
        ({"name": "X", "zone": "Z", "biome": "wild-forest"}, "missing required key 'level'"),
        ({"name": "X", "zone": "Z", "level": 0, "biome": "wild-forest"}, "'level' must be an int"),
    ],
)
def test_a_malformed_dungeon_fails_loud(bad, match):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "dungeons.yaml"
        p.write_text(yaml.safe_dump({"pit": bad}))
        with pytest.raises(SeedError, match=match):
            load_dungeons(p)
