"""Test twin for kernel/world/quest_archetypes.py -- the quest archetype catalog and completeness.

Acceptance: every shipped archetype is recognised by its own generated id, and the hand-written arcs
fall through to `authored`. Completeness (the governance gate): on the LIVE booted world, every
quest classifies to exactly one archetype (or authored) -- no quest matches two, none uncatalogued.
"""

from __future__ import annotations

from kernel.world.quest_archetypes import (
    AUTHORED,
    CATALOG,
    archetype,
    classify,
)


def test_catalog_is_well_formed():
    keys = [a.key for a in CATALOG]
    assert len(keys) == len(set(keys)), "archetype keys are unique"
    assert AUTHORED not in keys, "authored is the fallback, not a catalog entry"
    for a in CATALOG:
        assert a.name and a.purpose and a.loop and a.scope, f"{a.key} is missing design fields"
        assert archetype(a.key) is a


def test_each_archetype_recognises_its_own_generated_id():
    # a representative live id for each generator's shape
    samples = {
        "bounty_the_black_hollow_deep_boss": "bounty",
        "cull_veridia_wild_canid_6": "cull",
        "forage_veridia_wild_ember_shard_5": "forage",
        "story_greenhold": "storyline",
        "errand_greenhold": "errand",
        "spine_forgeward_road": "spine",
    }
    for qid, key in samples.items():
        assert classify(qid) == key, f"{qid} should classify as {key}"


def test_a_hand_written_arc_is_authored():
    assert classify("the_endless_journey") == AUTHORED
    assert classify("coilward_contract") == AUTHORED


def test_the_live_world_partitions_cleanly_into_archetypes():
    # the completeness gate: whatever seed booted, every quest matches at most one archetype, and
    # classify agrees with the predicates. So no archetype is uncatalogued and none double-counts.
    from kernel.world import quest

    for qid in quest._QUESTS:
        matches = [a.key for a in CATALOG if a.member(qid)]
        assert len(matches) <= 1, f"{qid} matches two archetypes {matches} -- predicates overlap"
        assert classify(qid) == (matches[0] if matches else AUTHORED)
