"""Test twin for kernel/world/armory.py -- the procedural gear factory.

Acceptance: forge_gear composes a valid, level-scaled equippable, and arm_guardians gives every
generated guardian a themed gear drop (so felling one drops something to wear; combat's affix
factory rolls rarity on top -- covered in test_combat). Refusal/scope: ambient wildlife and foes
that already drop something are left untouched.
"""

from __future__ import annotations

from kernel.world.armory import _FLAVOUR, _SLOTS, arm_guardians, forge_gear
from kernel.world.wildlands import generate_wildlands

_VALID_MODS = {"ATK", "DEF", "ACC", "EVA"}
_SLOT_NAMES = {s[0] for s in _SLOTS}


def test_forge_gear_makes_a_valid_levelscaled_equippable():
    label, item = forge_gear(60, "FIR", 0)  # idx 0 -> the weapon slot
    assert item["slot"] in _SLOT_NAMES
    assert set(item["mods"]) <= _VALID_MODS and all(v > 0 for v in item["mods"].values())
    assert item["location"] == "nowhere"  # a drop-only prototype
    assert "ember" in item["name"] and "ember" in item["keywords"]  # FIR -> ember flavour
    # the article agrees with the flavour word ("an ember-...", "a frost-...")
    assert item["name"].startswith("an ember-forged")
    assert label == "gear_ember_warblade_l60"


def test_the_factory_forges_every_equip_slot_including_leg_and_feet():
    # A 1-to-300 gear curve needs a full kit. leg + feet were once absent from the factory (only
    # ~2 authored pieces each existed world-wide), so a hero could never fill those slots from
    # drops. Pin that the factory now covers every equip slot, leg and feet included.
    forged = {forge_gear(50, "FIR", i)[1]["slot"] for i in range(len(_SLOTS) * 3)}
    assert forged == {"weapon", "body", "head", "arm", "leg", "feet", "accessory_1", "accessory_2"}


def test_gear_mods_climb_with_level():
    _, low = forge_gear(10, "ICE", 0)
    _, high = forge_gear(250, "ICE", 0)
    assert sum(high["mods"].values()) > sum(low["mods"].values())  # deeper foes drop stronger gear


def test_forge_gear_is_deterministic_and_dedupes():
    a = forge_gear(40, "LGT", 3)
    b = forge_gear(40, "LGT", 3)
    assert a == b  # same inputs -> same prototype (poolable, deduped by label)


def test_every_element_forges_a_flavoured_gear_name():
    for code, flavour in _FLAVOUR.items():
        _, item = forge_gear(30, code, 0)
        assert flavour in item["name"]


def _guarded_region():
    cfg = {
        "id": "arm_wild",
        "name": "The Armory Wilds",
        "region": "Emberreach",
        "biome": "volcanic-flats",
        "attach": "anchor",
        "attach_dir": "east",
        "level_min": 10,
        "level_max": 40,
        "trail_length": 60,
        "branch_every": 3,
        "branch_length": 3,
        "notable_every": 20,
    }
    _, npcs = generate_wildlands([cfg], {"anchor"})
    return npcs


def test_arm_guardians_gives_every_guardian_an_equippable_drop():
    npcs = _guarded_region()
    gear = arm_guardians(npcs)
    guardians = {k: v for k, v in npcs.items() if not v.get("ambient")}
    assert guardians, "the region seeded no guardian to arm"
    for label, npc in guardians.items():
        assert npc["drops"], f"guardian {label} was left unarmed"
        proto = npc["drops"][0]
        assert proto in gear and gear[proto]["slot"], "the drop is not a real equippable prototype"


def test_arm_guardians_leaves_ambient_wildlife_and_armed_foes_alone():
    npcs = _guarded_region()
    # a foe that already drops something must not be re-armed
    armed_before = next(v for v in npcs.values() if v.get("ambient"))
    armed_before["drops"] = ["some_relic"]
    arm_guardians(npcs)
    assert armed_before["drops"] == ["some_relic"]  # untouched
    # ambient wildlife stays lootless (mass gear would flood the floor)
    assert all(
        not v.get("drops") for k, v in npcs.items() if v.get("ambient") and v is not armed_before
    )


def test_registered_forged_gear_drops_and_the_affix_factory_rolls_it():
    # The full loop: a guardian's forged prototype, registered, clones onto the floor as equippable
    # gear whose rarity the affix factory has rolled (kernel.shelf.affixes). Real drop path.
    from kernel.world import combat, items
    from kernel.world.session import Session

    label, item = forge_gear(40, "FIR", 0)  # a weapon prototype
    items.register_prototypes({label: item})
    try:
        session = Session(player_id="hero", location="courtyard")
        foe: dict = {"name": "test guardian", "level": 40, "drops": [label]}
        line = combat._spawn_drops(session, foe)
        assert line and "forged" in line  # gear hit the floor
        floor = [items.ITEMS[i] for i in items.items_in("room:courtyard")]
        gear = [it for it in floor if "forged" in it["name"]]
        assert gear and gear[0]["slot"] == "weapon"  # a real equippable
        assert gear[0].get("rarity")  # the affix factory stamped a rarity (common..legendary)
    finally:
        for iid in list(items.ITEMS):
            if items.ITEMS[iid].get("prototype") == label or iid == label:
                items.ITEMS.pop(iid, None)
        items.PROTOTYPES.pop(label, None)
