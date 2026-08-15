"""Test twin for kernel/world/delve.py -- dungeon mouths become multi-room delves.

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

from kernel.world.delve import _DEPTH, _VAULT_OFF, generate_delves, load_dungeons, wire_delve_mouths
from kernel.world.seed import BlueprintError

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
    assert len(rooms) == _DEPTH + 1  # one chamber per depth, plus the treasure-vault pocket
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


def test_a_delve_forks_into_an_optional_guarded_treasure_vault():
    # A delve is a choice, not a corridor: a mid chamber opens a `vault` exit into a treasure pocket
    # that leads back `out`, and a named guardian holds it -- optional, but you must fight for it.
    rooms, npcs = generate_delves(_CFG)
    vault = f"black_hollow_delve_{_VAULT_OFF}"
    assert rooms[vault]["exits"].get("vault") == "black_hollow_delve_vault"
    pocket = rooms["black_hollow_delve_vault"]
    assert pocket["exits"].get("out") == vault, "the vault leads back to the descent"
    assert "treasure-vault" in pocket["name"] and "hoard" in pocket["desc"]
    guard = npcs["black_hollow_vault_guard"]
    assert guard["aggressive"] and not guard.get("ambient")  # a named guardian, an ambush
    # and it does NOT upstage the deep boss
    assert guard["level"] < npcs["black_hollow_deep_boss"]["level"]


def test_the_vault_is_reachable_and_optional_off_the_main_descent():
    # The vault hangs off the side: the straight down-descent to the boss never passes through it.
    rooms, _ = generate_delves(_CFG)
    descent = [f"black_hollow_delve_{i}" for i in range(1, _DEPTH + 1)]
    for label in descent:
        assert "black_hollow_delve_vault" not in [
            dest for d, dest in rooms[label]["exits"].items() if d in ("up", "down")
        ], "the vault must not sit on the main up/down spine"


def test_a_delve_reads_as_a_descent_with_distinct_depth_stages():
    # The chambers must not read alike: each names how deep it sits (threshold -> ... -> lair), so a
    # descent feels like progression. The four leads are distinct and the deepest is the lair.
    rooms, _ = generate_delves(_CFG)
    ordered = [rooms[f"black_hollow_delve_{i}"] for i in range(1, _DEPTH + 1)]
    stage_words = [r["name"].rsplit(", ", 1)[1] for r in ordered]
    assert stage_words[0] == "the threshold" and stage_words[-1] == "the lair"
    leads = {r["desc"].split(".")[0] for r in ordered}
    assert len(leads) == _DEPTH, "every depth must read differently, not one template repeated"


def test_a_delve_inherits_its_biome_note():
    # A dungeon carries the stone-and-air of the Reach it sinks below: a forest delve reads unlike
    # an ice delve, on the same dungeon.
    from kernel.world.delve import _BIOME_DELVE_NOTE

    forest = generate_delves(_CFG)[0]["black_hollow_delve_1"]["desc"]
    assert _BIOME_DELVE_NOTE["wild-forest"] in forest
    icy_cfg = [{**_CFG[0], "biome": "glacier-waste"}]
    icy = generate_delves(icy_cfg)[0]["black_hollow_delve_1"]["desc"]
    assert _BIOME_DELVE_NOTE["glacier-waste"] in icy and forest != icy


def test_an_unknown_biome_delve_falls_back_to_a_plain_note():
    from kernel.world.delve import _DEFAULT_DELVE_NOTE, _chamber

    desc = _chamber("Nowhere Deep", 1, "no-such-biome")["desc"]
    assert _DEFAULT_DELVE_NOTE in desc, "an unknown biome still gets a valid note, never a crash"


def test_delve_generation_is_deterministic():
    a, _ = generate_delves(_CFG)
    b, _ = generate_delves(_CFG)
    assert {k: v["desc"] for k, v in a.items()} == {k: v["desc"] for k, v in b.items()}


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
    aethryn = Path(__file__).resolve().parent.parent / "content" / "seeds" / "aethryn"
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
        with pytest.raises(BlueprintError, match=match):
            load_dungeons(p)
