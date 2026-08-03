"""Test twin for kernel/world/survey.py -- the Surveyor: read-only Aethryn world validation.

Acceptance: against the shipped seed every check is CLEAN (no duplicate ids, no broken region
references, no canon drift), the aggregate `validate` is empty, and the CLI dispatcher routes each
real subcommand to a 0 exit. Refusal: a location placed in a region canon does not know is FLAGGED
by broken_references (proven on a synthetic record), a cross-file id collision is caught, and an
unknown or not-yet-built subcommand is refused (exit 2) rather than silently faked.
"""

from __future__ import annotations

from kernel.world import survey

# --- Acceptance: the shipped world is internally consistent and faithful to canon ----------------


def test_the_shipped_world_validates_clean():
    assert survey.validate() == []


def test_no_broken_region_references_in_the_seed():
    assert survey.broken_references() == []


def test_no_duplicate_ids_across_world_files():
    assert survey.duplicate_ids() == []


def test_locations_are_placed_and_tagged_with_their_source():
    locs = survey.locations()
    assert len(locs) >= 45  # settlements + dungeons
    greenhold = next(loc for loc in locs if loc["id"] == "greenhold")
    assert greenhold["zone"] == "Veridia"
    assert greenhold["source"] == "settlements.yaml"


# --- Acceptance: the CLI dispatcher routes the real subcommands -----------------------------------


def test_run_routes_each_real_subcommand_to_a_clean_exit():
    for command in ("validate", "check-canon", "find-broken-references"):
        code, text = survey.run([command])
        assert code == 0, f"{command} -> {text}"
        assert "CLEAN" in text


def test_run_list_regions_shows_all_fourteen_with_threat_bands():
    code, text = survey.run(["list-regions"])
    assert code == 0
    assert "Veridia" in text and "250-300" in text  # first + last band present


def test_run_list_locations_reports_a_count_and_names():
    code, text = survey.run(["list-locations"])
    assert code == 0
    assert "Greenhold" in text


def test_no_invalid_faction_references_in_the_seed():
    assert survey.faction_references() == []


def test_faction_references_flags_a_location_under_an_unknown_faction(monkeypatch):
    def fake_locations():
        return [{"id": "spy_den", "source": "settlements.yaml", "faction": "the_illuminati"}]

    monkeypatch.setattr(survey, "locations", fake_locations)
    violations = survey.faction_references()
    assert len(violations) == 1
    assert "spy_den" in violations[0] and "the_illuminati" in violations[0]


def test_run_find_unreachable_is_clean_on_the_connected_world():
    code, text = survey.run(["find-unreachable"])
    assert code == 0 and "CLEAN" in text


def test_run_inspect_shows_a_region_and_refuses_an_unknown_one():
    code, text = survey.run(["inspect", "veridia"])
    assert code == 0 and "Veridia" in text
    code, text = survey.run(["inspect", "nowhere"])
    assert code == 1 and "refused" in text
    assert survey.run(["inspect"])[0] == 2  # missing arg


def test_run_graph_lists_the_topology():
    code, text = survey.run(["graph"])
    assert code == 0 and "the_voidscar" in text


def test_validate_surfaces_an_unreachable_region(monkeypatch):
    monkeypatch.setattr(survey.worldgraph, "unreachable_regions", lambda: ["the_voidscar"])
    assert any("the_voidscar" in v and "unreachable" in v for v in survey.validate())


def test_run_find_unreachable_reports_a_stranded_region_as_exit_1(monkeypatch):
    monkeypatch.setattr(survey.worldgraph, "unreachable_regions", lambda: ["skyward_spires"])
    code, text = survey.run(["find-unreachable"])
    assert code == 1
    assert "skyward_spires" in text and "problem" in text


# --- Refusal: the guardrail bites, and unknown commands are refused honestly ----------------------


def test_broken_references_flags_a_location_in_an_unknown_region(monkeypatch):
    # A settlement placed in a region canon has never heard of must be caught.
    def fake_locations():
        return [
            {"id": "nowhere_keep", "source": "settlements.yaml", "zone": "Atlantis", "level": 5}
        ]

    monkeypatch.setattr(survey, "locations", fake_locations)
    violations = survey.broken_references()
    assert len(violations) == 1
    assert "nowhere_keep" in violations[0] and "Atlantis" in violations[0]


def test_duplicate_ids_flags_a_cross_file_collision(monkeypatch):
    def fake_records(filename):
        return (
            {"greenhold": {"name": "X"}}
            if filename in ("waystones.yaml", "settlements.yaml")
            else {}
        )

    monkeypatch.setattr(survey, "_records", fake_records)
    violations = survey.duplicate_ids()
    assert any("greenhold" in v for v in violations)


def test_validate_surfaces_a_planted_defect(monkeypatch):
    monkeypatch.setattr(survey, "broken_references", lambda: ["boom: bad ref"])
    assert "boom: bad ref" in survey.validate()


def test_run_refuses_an_unknown_subcommand():
    code, text = survey.run(["obliterate-everything"])
    assert code == 2
    assert "unknown or not-yet-built" in text


def test_run_with_no_args_prints_usage():
    code, text = survey.run([])
    assert code == 2
    assert "world validate" in text
