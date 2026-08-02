"""Test twin for kernel/world/generation_contract.py -- the generator's contract and its checks.

Acceptance: the shipped contract loads with the 16 required fields, the historical layers, the six
dungeon beats, the forbidden changes, and archetype shares that sum to 1; missing_fields measures an
area against the required set; distribution_gaps passes a batch that matches the mix and flags one
that is skewed; the tier map turns a canon_status into a C0-C4 label. Refusal: a contract missing a
section or whose archetype shares do not sum to 1 fails loud; a field present-but-empty still counts
as missing (a placeholder cannot pass); an unknown archetype in a batch is reported.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kernel.world import generation_contract as gc
from kernel.world.seed import SeedError

# --- Acceptance: the shipped contract is complete and well-formed --------------------------------


def test_contract_carries_the_sixteen_required_fields():
    fields = gc.required_area_fields()
    assert len(fields) == 16
    assert {"identity", "historical_layer", "provenance", "generation_seed"} <= set(fields)


def test_archetype_shares_sum_to_one():
    shares = gc.archetype_shares()
    assert abs(sum(shares.values()) - 1.0) < 1e-9
    assert shares["natural"] == 0.35


def test_the_supporting_lists_are_present():
    assert len(gc.historical_layers()) == 7
    assert gc.dungeon_grammar()[0] == "threshold" and gc.dungeon_grammar()[-1] == "aftermath"
    assert any("Netharion" in line for line in gc.forbidden_changes())


def test_canon_tier_map():
    assert gc.canon_tier_for("GENERATED_LOCAL") == "C3"
    assert gc.canon_tier_for("CANON_LOCKED") == "C1"
    assert gc.canon_tier_for("RUMOR") == "C4"
    assert gc.canon_tier_for("something_else") == "C3"  # a safe default


# --- Acceptance: missing_fields measures one area ------------------------------------------------


def test_missing_fields_is_empty_for_a_complete_area():
    area = {field: "x" for field in gc.required_area_fields()}
    assert gc.missing_fields(area) == []


def test_missing_fields_flags_absent_and_empty_fields():
    area = {field: "x" for field in gc.required_area_fields()}
    del area["identity"]  # absent
    area["hazard"] = ""  # present but empty (a placeholder must not pass)
    missing = gc.missing_fields(area)
    assert set(missing) == {"identity", "hazard"}


def test_a_real_zero_or_false_is_not_blank():
    # A generation_seed of 0 is a valid value, not a missing field (regression: `not 0` is True).
    area = {field: "x" for field in gc.required_area_fields()}
    area["generation_seed"] = 0
    assert gc.missing_fields(area) == []


# --- Acceptance: distribution_gaps measures a batch ----------------------------------------------


def test_a_batch_matching_the_mix_has_no_gaps():
    batch = (
        ["natural"] * 7 + ["present_use"] * 4 + ["old_world"] * 4 + ["scar"] * 3 + ["faction"] * 2
    )
    areas = [{"id": f"a{i}", "archetype": a} for i, a in enumerate(batch)]
    assert gc.distribution_gaps(areas) == []


def test_a_skewed_batch_is_flagged():
    areas = [{"id": f"b{i}", "archetype": "natural"} for i in range(20)]
    gaps = gc.distribution_gaps(areas)
    assert gaps  # all-natural drifts far from the 35 percent target
    assert any("natural" in g for g in gaps)


def test_an_unknown_archetype_in_a_batch_is_reported():
    areas = [{"id": "weird", "archetype": "interdimensional"}]
    assert any("unknown archetype" in g for g in gc.distribution_gaps(areas))


def test_an_empty_batch_has_no_opinion():
    assert gc.distribution_gaps([]) == []


# --- Refusal: a malformed contract fails loud ----------------------------------------------------


def _write(tmp_path: Path, data: object) -> Path:
    p = tmp_path / "generation_contract.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def _good() -> dict:
    return {
        "required_area_fields": ["identity", "provenance"],
        "historical_layers": ["recent event"],
        "dungeon_grammar": ["threshold"],
        "forbidden_changes": ["Rename Aethryn"],
        "minor_area_archetypes": [
            {"id": "natural", "share": 0.6},
            {"id": "old_world", "share": 0.4},
        ],
    }


def test_missing_file_fails_loud(tmp_path: Path):
    with pytest.raises(SeedError, match="not found"):
        gc.load_contract(tmp_path / "nope.yaml")


def test_a_non_mapping_file_fails_loud(tmp_path: Path):
    with pytest.raises(SeedError, match="not a mapping"):
        gc.load_contract(_write(tmp_path, ["not", "a", "contract"]))


def test_a_missing_section_fails_loud(tmp_path: Path):
    data = _good()
    del data["forbidden_changes"]
    with pytest.raises(SeedError, match="forbidden_changes"):
        gc.load_contract(_write(tmp_path, data))


def test_shares_that_do_not_sum_to_one_fail_loud(tmp_path: Path):
    data = _good()
    data["minor_area_archetypes"] = [{"id": "natural", "share": 0.5}, {"id": "scar", "share": 0.2}]
    with pytest.raises(SeedError, match="sum to 1.0"):
        gc.load_contract(_write(tmp_path, data))


def test_an_archetype_missing_its_share_fails_loud(tmp_path: Path):
    data = _good()
    data["minor_area_archetypes"] = [{"id": "natural"}, {"id": "scar", "share": 1.0}]
    with pytest.raises(SeedError, match="needs an id and share"):
        gc.load_contract(_write(tmp_path, data))
