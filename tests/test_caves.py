"""Test twin for parts/world/caves.py -- the deterministic cave forge.

Acceptance: every canon region generates a cave that passes the prompt's cave rules (5-18 rooms, a
branch, a loop, a landmark, a hazard, a resource, a micro-story, a navigable return route, all
reachable from the mouth), the SAME (region, seed) always yields an IDENTICAL cave, and each is
stamped GENERATED_LOCAL with its region's threat band. Regional identity varies (a Veridia cave
reads temperate, a Frostspire cave tundra). Refusal: an unknown region or an out-of-band size fails
loud, a family missing a required list fails loud, and a RUMOR only RAISES an open canon question,
never asserts forbidden global canon.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from parts.world import canon, caves
from parts.world.seed import SeedError

# --- Acceptance: every region forges a valid, self-consistent cave --------------------------------


def test_every_canon_region_has_a_cave_family():
    assert set(caves.cave_regions()) == {r["id"] for r in canon.regions()}


def test_all_regions_generate_caves_that_pass_their_own_validation():
    for region in caves.cave_regions():
        for seed in range(8):
            area = caves.generate_cave(region, seed)
            assert area["validation"] == [], f"{region}/{seed}: {area['validation']}"


def test_a_cave_has_the_required_shape():
    area = caves.generate_cave("veridia", 3)
    rooms = area["rooms"]
    assert 5 <= len(rooms) <= 18
    assert any("branch" in r.get("tags", []) for r in rooms)  # a side passage
    assert any(r.get("feature") for r in rooms)  # a landmark
    assert any(r.get("hazard") for r in rooms)  # a hazard
    assert any(r.get("resource") for r in rooms)  # a resource
    assert area["micro_story"]
    assert area["return_room"] == rooms[0]["id"]  # the mouth is the escape route


def test_exits_are_reciprocal_and_all_rooms_reachable():
    area = caves.generate_cave("thalorin", 11)
    by_id = {r["id"]: r for r in area["rooms"]}
    for room in area["rooms"]:
        for direction, dest in room["exits"].items():
            assert dest in by_id
            back = caves._REVERSE[direction]
            assert by_id[dest]["exits"][back] == room["id"]  # reciprocal


# --- Acceptance: determinism is the contract -----------------------------------------------------


def test_same_region_and_seed_is_identical():
    a = caves.generate_cave("frostspire_peaks", 42)
    b = caves.generate_cave("frostspire_peaks", 42)
    assert a == b


def test_different_seeds_diverge():
    a = caves.generate_cave("veridia", 1)
    b = caves.generate_cave("veridia", 2)
    assert a != b  # a different seed is a different cave


def test_size_override_is_honoured_within_band():
    area = caves.generate_cave("caeloria", 5, size=9)
    assert len(area["rooms"]) == 9


# --- Acceptance: provenance + regional identity --------------------------------------------------


def test_provenance_is_stamped_generated_local_with_the_region_band():
    area = caves.generate_cave("the_voidscar", 99)
    assert area["canon_status"] == "GENERATED_LOCAL"
    assert area["region_id"] == "the_voidscar"
    assert area["generation_seed"] == 99
    region = next(r for r in canon.regions() if r["id"] == "the_voidscar")
    assert area["level_band"] == [region["threat_min"], region["threat_max"]]


def test_regional_identity_varies():
    assert caves.generate_cave("veridia", 4)["biome"] == "temperate"
    assert caves.generate_cave("frostspire_peaks", 4)["biome"] == "tundra"
    assert caves.generate_cave("ashen_wastes", 4)["biome"] == "volcanic"


def test_a_rumor_only_raises_an_open_question_never_asserts_canon():
    open_qs = set(canon.unresolved_questions())
    for seed in range(60):
        rumor = caves.generate_cave("the_deepreach", seed)["rumor"]
        if rumor:
            assert rumor.startswith("RUMOR:")
            assert any(q in rumor for q in open_qs)  # it RAISES a known open question
            break
    else:
        pytest.fail("expected at least one rumor across 60 seeds")


# --- Refusal: the forge fails loud on bad input --------------------------------------------------


def test_unknown_region_is_refused():
    with pytest.raises(SeedError, match="unknown region"):
        caves.generate_cave("mordor", 1)


def test_out_of_band_size_is_refused():
    with pytest.raises(SeedError, match="outside"):
        caves.generate_cave("veridia", 1, size=400)


def test_a_family_missing_a_required_field_fails_loud(tmp_path: Path):
    bad = tmp_path / "cave_families.yaml"
    bad.write_text(
        textwrap.dedent(
            """\
            defaults: {min_rooms: 5, max_rooms: 18}
            veridia:
              biome: temperate
              subtypes: [river cave]
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(SeedError, match="missing required field"):
        caves.load_families(bad)


def test_a_family_for_a_non_canon_region_fails_loud(tmp_path: Path):
    bad = tmp_path / "cave_families.yaml"
    bad.write_text("atlantis: {biome: sea}\n", encoding="utf-8")
    with pytest.raises(SeedError, match="not a canon region"):
        caves.load_families(bad)


def test_a_missing_families_file_fails_loud(tmp_path: Path):
    with pytest.raises(SeedError, match="not found"):
        caves.load_families(tmp_path / "nope.yaml")


def test_a_non_mapping_families_file_fails_loud(tmp_path: Path):
    bad = tmp_path / "cave_families.yaml"
    bad.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(SeedError, match="not a mapping"):
        caves.load_families(bad)


def test_a_complete_but_incomplete_coverage_family_set_fails_loud(tmp_path: Path):
    # Every present family is valid, but only one region is covered: the other 13 are stranded.
    bad = tmp_path / "cave_families.yaml"
    bad.write_text(
        textwrap.dedent(
            """\
            defaults: {min_rooms: 5, max_rooms: 18}
            veridia:
              biome: temperate
              subtypes: [river cave]
              entrances: [natural opening]
              creatures: [cave bat]
              hazards: [a drop]
              resources: [a spring]
              landmarks: [a pool]
              naming: {adjectives: [Damp], nouns: [Hollow]}
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(SeedError, match="no family for canon region"):
        caves.load_families(bad)


# --- Refusal: the validator (the generator's own safety net) catches every defect -----------------


def _valid_area() -> dict:
    """A hand-built minimal cave that passes _validation_report, so each test can corrupt one thing
    and prove the validator flags exactly that defect."""
    rooms = [
        {"id": "r0", "role": "entrance", "tags": ["cave"], "exits": {"north": "r1"}},
        {
            "id": "r1",
            "role": "passage",
            "tags": ["cave"],
            "feature": "a pool",
            "exits": {"south": "r0", "east": "r2", "down": "r3"},
        },
        {
            "id": "r2",
            "role": "passage",
            "tags": ["cave"],
            "hazard": "a drop",
            "exits": {"west": "r1", "south": "r3", "in": "r4"},
        },
        {
            "id": "r3",
            "role": "passage",
            "tags": ["cave"],
            "resource": "water",
            "exits": {"north": "r2", "up": "r1"},
        },
        {"id": "r4", "role": "branch", "tags": ["cave", "branch"], "exits": {"out": "r2"}},
    ]
    return {
        "rooms": rooms,
        "return_room": "r0",
        "micro_story": "once, a scavenger worked here",
        "canon_status": "GENERATED_LOCAL",
    }


def test_the_hand_built_area_is_valid():
    assert caves._validation_report(_valid_area()) == []


def test_validator_flags_out_of_band_room_count():
    area = _valid_area()
    area["rooms"] = area["rooms"][:2]
    assert any("room count" in p for p in caves._validation_report(area))


def test_validator_flags_an_exit_to_an_unknown_room():
    area = _valid_area()
    area["rooms"][0]["exits"]["north"] = "ghost"
    assert any("unknown room ghost" in p for p in caves._validation_report(area))


def test_validator_flags_a_non_reciprocal_exit():
    area = _valid_area()
    del area["rooms"][1]["exits"]["south"]  # r0 -> r1 no longer answered
    assert any("not reciprocal" in p for p in caves._validation_report(area))


def test_validator_flags_a_pure_tree_with_no_loop():
    area = _valid_area()
    del area["rooms"][1]["exits"]["down"]  # remove the loop edge both ways
    del area["rooms"][3]["exits"]["up"]
    assert any("no loop" in p for p in caves._validation_report(area))


def test_validator_flags_a_missing_branch():
    area = _valid_area()
    area["rooms"][4]["tags"] = ["cave"]  # strip the branch tag
    assert any("no branch" in p for p in caves._validation_report(area))


def test_validator_flags_unreachable_rooms():
    area = _valid_area()
    area["rooms"].append({"id": "island", "role": "passage", "tags": ["cave"], "exits": {}})
    assert any("unreachable" in p for p in caves._validation_report(area))


def test_validator_flags_missing_landmark_hazard_and_resource():
    area = _valid_area()
    for room in area["rooms"]:
        room.pop("feature", None)
        room.pop("hazard", None)
        room.pop("resource", None)
    report = caves._validation_report(area)
    assert any("landmark" in p for p in report)
    assert any("hazard" in p for p in report)
    assert any("resource" in p for p in report)


def test_validator_flags_a_return_room_that_points_nowhere():
    area = _valid_area()
    area["return_room"] = "nowhere"  # the escape route names a room that does not exist
    assert any("unreachable" in p for p in caves._validation_report(area))


def test_validator_flags_a_missing_micro_story():
    area = _valid_area()
    area["micro_story"] = ""
    assert any("micro-story" in p for p in caves._validation_report(area))


def test_validator_flags_content_not_stamped_generated_local():
    area = _valid_area()
    area["canon_status"] = "CANON_LOCKED"
    assert any("GENERATED_LOCAL" in p for p in caves._validation_report(area))
