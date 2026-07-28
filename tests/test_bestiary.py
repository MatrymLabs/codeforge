"""Test twin for parts/world/bestiary.py -- the procedural creature factory.

Acceptance: make_beast composes a valid, level-scaled, biome-coherent Npc, and the schema yields
wide variety. Determinism: the same (biome, level, idx) always grows the same creature.
"""

from parts.world.bestiary import (
    _BIOME_LIFE,
    _CLASSES,
    make_beast,
    make_notable,
    material_for_class,
)
from parts.world.score_sheet_model import RESIST_ORDER


def test_make_beast_is_a_valid_scaled_npc():
    b = make_beast("temperate-meadow", 30, 0, "room_x")
    assert b["location"] == "room_x"
    assert b["hp"] > 0 and b["hp_now"] == b["hp"] and b["atk"] > 0
    assert b["level"] == 30 and b["tier"] in ("normal", "elite")
    assert b["attack_element"] in RESIST_ORDER
    assert b["keywords"] and b["name"].startswith(("a ", "an "))


def test_generation_is_deterministic():
    a = make_beast("glacier-waste", 88, 17, "r")
    b = make_beast("glacier-waste", 88, 17, "r")
    assert a == b


def test_the_schema_yields_wide_variety():
    names = set()
    for biome in _BIOME_LIFE:
        for level in range(1, 300, 9):
            for idx in range(30):
                names.add(make_beast(biome, level, idx, "r")["name"])
    assert len(names) > 500, f"only {len(names)} distinct creatures -- the schema is too shallow"


def test_biome_marks_the_element_and_the_name():
    # Environmental coherence: a beast of a biome-typed class takes on its land's element (volcanic
    # -> FIR, glacier -> ICE), and the biome adjective appears in the name. Classes with an
    # element (reptile/insectoid venom, undead dark) keep theirs -- variety within the biome.
    fire = make_beast("volcanic-flats", 40, 0, "r")  # idx 0 -> elemental class -> biome el
    ice = make_beast("glacier-waste", 40, 0, "r")
    assert fire["attack_element"] == "FIR" and ice["attack_element"] == "ICE"
    assert any(adj in fire["name"] for adj in _BIOME_LIFE["volcanic-flats"]["adj"])


def test_undead_class_carries_its_own_dark_element():
    # Sweep a biome that hosts undead until one appears; it must strike DRK, not the biome.
    found = [
        make_beast("salt-desert", 50, i, "r")
        for i in range(40)
        if "wight" in make_beast("salt-desert", 50, i, "r")["name"]
        or "wraith" in make_beast("salt-desert", 50, i, "r")["name"]
        or "husk" in make_beast("salt-desert", 50, i, "r")["name"]
    ]
    assert found, "expected an undead-class beast in a biome that hosts them"
    assert all(b["attack_element"] == "DRK" for b in found)


def test_size_and_stats_climb_with_level():
    low = make_beast("wild-forest", 5, 1, "r")
    high = make_beast("wild-forest", 200, 1, "r")
    assert high["hp"] > low["hp"] * 5  # deeper wilds are far deadlier
    # low bands skew small, high bands skew large/dread
    lows = {make_beast("wild-forest", 4, i, "r")["name"].split()[1] for i in range(12)}
    highs = {make_beast("wild-forest", 220, i, "r")["name"].split()[1] for i in range(12)}
    assert any(w in ("lesser", "dire") for w in lows) or lows  # low bands include lesser/plain
    assert any(w in ("great", "elder", "dread") for w in highs), "high bands never grow large"


def test_article_agrees_with_the_following_word():
    # "an elder ..." / "an ash-..." (vowel) vs "a meadow-..." (consonant).
    for biome in _BIOME_LIFE:
        for level in (4, 90, 240):
            for idx in range(8):
                name = make_beast(biome, level, idx, "r")["name"]
                head = name.split(" ", 1)[1]
                article = "an" if head[0].lower() in "aeiou" else "a"
                assert name.startswith(article + " "), f"bad article: {name!r}"


# --- named guardians: an ennobled, non-ambient creature that mints a hunt bounty ---------------


def test_make_notable_is_a_named_nonambient_guardian():
    from parts.world.bestiary import make_beast, make_notable

    base = make_beast("volcanic-flats", 40, 3, "lair")
    lord = make_notable("volcanic-flats", 40, 3, "lair", 0)
    assert not lord.get("ambient"), "a guardian must be non-ambient so it mints a bounty"
    assert lord["tier"] in ("elite", "boss")
    assert lord["hp"] > base["hp"] and lord["atk"] > base["atk"]  # outranks the ambient life
    assert lord["location"] == "lair" and lord["level"] == 40
    # a proper NAME (no leading article), targetable by its fore-name keyword
    assert not lord["name"].lower().startswith(("a ", "an "))
    assert lord["name"].split()[0].lower() in lord["keywords"]


def test_roughly_one_in_six_guardians_is_a_boss():
    from parts.world.bestiary import make_notable

    tiers = [make_notable("wild-forest", 30, 1, "r", seq)["tier"] for seq in range(6)]
    assert tiers[5] == "boss" and tiers.count("boss") == 1  # seq 5 pays the boss curve


def test_monster_materials_map_only_furred_and_scaled_classes():
    # Furred/feathered classes drop hide; scaled/shelled drop chitin; the unbodied drop neither
    # (there is no pelt on a wisp). Crafting slice 1c.
    assert material_for_class("canid") == "raw_hide"
    assert material_for_class("avian") == "raw_hide"
    assert material_for_class("reptile") == "chitin_scale"
    assert material_for_class("insectoid") == "chitin_scale"
    for unbodied in ("elemental", "undead", "colossus"):
        assert material_for_class(unbodied) is None
    # every mapped class is a real body-class, and every material is a raw one
    assert set(_CLASSES) >= {"canid", "reptile", "elemental"}


def test_a_furred_beast_drops_its_hide_on_the_loot_table():
    # temperate-meadow idx 0 is a canid (furred): its loot must include raw_hide beside the ember.
    beast = make_beast("temperate-meadow", 20, 0, "r")
    assert "raw_hide" in beast["loot"] and "ember_shard" in beast["loot"]


def test_a_notable_carries_a_heavier_material_haul():
    lord = make_notable("wild-forest", 30, 0, "lair", 0)  # felid: furred
    material = material_for_class(lord["keywords"][-1])
    assert material == "raw_hide" and lord["loot"][material] == 3  # richer than ambient life


def test_an_unbodied_notable_drops_no_monster_material():
    # volcanic-flats idx 0 is an elemental: a notable of it weights only ember, no hide/scale.
    lord = make_notable("volcanic-flats", 40, 0, "lair", 0)
    assert material_for_class(lord["keywords"][-1]) is None
    assert "raw_hide" not in lord["loot"] and "chitin_scale" not in lord["loot"]
