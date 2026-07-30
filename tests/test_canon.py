"""Test twin for parts/world/canon.py -- Aethryn's LOCKED canon and its drift guardrail.

Acceptance: the real canon loads and exposes exactly 7 Seven Crown sites and 14 regions, each with
its required fields and CANON_LOCKED status; check_canon confirms the shipped world still matches
canon (zero drift). Refusal: a malformed canon (wrong crown count, an unlocked crown, a missing
field, inverted threat band, a bad canon_status, a non-aethryn world) fails loud with SeedError, so
a file that could mislead a generator can never load silently. The pure correspondence check also
FLAGS a planted drift, proving the guardrail bites rather than always passing.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from parts.world import canon
from parts.world.seed import SeedError

# --- Acceptance: the real canon is well-formed and complete --------------------------------------


def test_canon_loads_with_seven_crowns_and_fourteen_regions():
    data = canon.load_canon()
    assert data["world"]["id"] == "aethryn"
    assert len(canon.seven_crowns(data)) == 7
    assert len(canon.regions(data)) == 14


def test_every_seven_crown_site_is_locked_and_fully_specified():
    fields = ("id", "map_name", "mythic_title", "region", "ancient_function", "modern_condition")
    for crown in canon.seven_crowns():
        for field in fields:
            assert crown.get(field), f"{crown.get('id')} missing {field}"
        assert crown["canon_status"] == "CANON_LOCKED"


def test_every_region_is_locked_with_an_ordered_threat_band():
    for region in canon.regions():
        assert region["canon_status"] == "CANON_LOCKED"
        assert region["threat_min"] <= region["threat_max"]


def test_locked_region_names_covers_the_fourteen():
    names = canon.locked_region_names()
    assert len(names) == 14
    assert "Veridia" in names and "The Voidscar" in names


def test_unresolved_questions_are_carried_and_never_empty():
    questions = canon.unresolved_questions()
    assert questions  # the world keeps mysteries OPEN
    assert any("Netharion" in q for q in questions)


def test_collective_names_carry_per_name_tiers_matching_the_source():
    terms = {t["id"]: t for t in canon.collective_names()}
    assert len(terms) == 6
    # The neutral / common names are anchored; the ideological ones are belief (RUMOR).
    assert terms["seven_crowns"]["canon_status"] == "CANON_LOCKED"
    assert terms["seven_wounds"]["canon_status"] == "CANON_LOCKED"
    for ideological in ("seven_blasphemies", "murdered_crowns", "seven_lessons", "seven_engines"):
        assert terms[ideological]["canon_status"] == "RUMOR"
    assert all(t["usage"] for t in terms.values())  # each names the worldview that uses it


def test_a_collective_name_missing_its_usage_is_refused(tmp_path: Path):
    body = (
        _GOOD_WORLD
        + _seven_good_crowns()
        + _fourteen_good_regions()
        + textwrap.dedent(
            """\
        collective_names:
          - {id: seven_crowns, name: The Seven Crowns, canon_status: CANON_LOCKED}
        """
        )
    )
    with pytest.raises(SeedError, match="needs a name and usage"):
        canon.load_canon(_write(tmp_path, body))


def test_generated_statuses_are_the_lower_three_only():
    assert canon.is_generated_status("GENERATED_LOCAL")
    assert canon.is_generated_status("AUTHORED_LOCAL")
    assert canon.is_generated_status("RUMOR")
    assert not canon.is_generated_status("CANON_LOCKED")
    assert not canon.is_generated_status("CANON_WORKING")


# --- Acceptance: the shipped world matches canon (the whole thesis) ------------------------------


def test_check_canon_finds_no_drift_in_the_shipped_world():
    assert canon.check_canon() == []


# --- Refusal: the guardrail bites when the world drifts from canon -------------------------------


def test_correspondence_flags_a_missing_region_and_a_missing_crown_site():
    data = canon.load_canon()
    # A world that registers no zones and no places drifts from EVERY locked region and crown.
    violations = canon._correspondence_violations(data, zone_names=set(), place_names=set())
    assert len(violations) == 14 + 7
    assert any("Veridia" in v for v in violations)
    assert any("The Flamewrought Forge" in v for v in violations)


# --- Refusal: a malformed canon file fails loud --------------------------------------------------


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "canon.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


_GOOD_WORLD = "world: {id: aethryn, canon_status: CANON_LOCKED}\n"


def test_missing_file_fails_loud(tmp_path: Path):
    with pytest.raises(SeedError, match="not found"):
        canon.load_canon(tmp_path / "nope.yaml")


def test_a_non_aethryn_world_is_refused(tmp_path: Path):
    with pytest.raises(SeedError, match="aethryn"):
        canon.load_canon(_write(tmp_path, "world: {id: elsewhere, canon_status: CANON_LOCKED}\n"))


def test_a_bad_canon_status_is_refused(tmp_path: Path):
    with pytest.raises(SeedError, match="canon_status"):
        canon.load_canon(_write(tmp_path, "world: {id: aethryn, canon_status: MADE_UP}\n"))


def test_the_wrong_number_of_crowns_is_refused(tmp_path: Path):
    body = _GOOD_WORLD + textwrap.dedent(
        """\
        seven_crowns:
          - {id: only_one, map_name: One, mythic_title: T, region: R, canon_status: CANON_LOCKED,
             ancient_function: f, modern_condition: c}
        """
    )
    with pytest.raises(SeedError, match="exactly 7"):
        canon.load_canon(_write(tmp_path, body))


def test_a_crown_missing_a_field_is_refused(tmp_path: Path):
    crowns = "\n".join(
        f"  - {{id: c{i}, map_name: M{i}, mythic_title: T{i}, region: R{i}, "
        f"canon_status: CANON_LOCKED, ancient_function: f, modern_condition: c}}"
        for i in range(6)
    )
    # The 7th crown omits map_name.
    crowns += (
        "\n  - {id: c6, mythic_title: T6, region: R6, canon_status: CANON_LOCKED, "
        "ancient_function: f, modern_condition: c}"
    )
    body = _GOOD_WORLD + "seven_crowns:\n" + crowns + "\n"
    with pytest.raises(SeedError, match="missing required field 'map_name'"):
        canon.load_canon(_write(tmp_path, body))


def test_an_unlocked_crown_is_refused(tmp_path: Path):
    crowns = "\n".join(
        f"  - {{id: c{i}, map_name: M{i}, mythic_title: T{i}, region: R{i}, "
        f"canon_status: CANON_LOCKED, ancient_function: f, modern_condition: c}}"
        for i in range(6)
    )
    crowns += (
        "\n  - {id: c6, map_name: M6, mythic_title: T6, region: R6, "
        "canon_status: CANON_WORKING, ancient_function: f, modern_condition: c}"
    )
    body = _GOOD_WORLD + "seven_crowns:\n" + crowns + "\n"
    with pytest.raises(SeedError, match="must be CANON_LOCKED"):
        canon.load_canon(_write(tmp_path, body))


def _seven_good_crowns() -> str:
    lines = "\n".join(
        f"  - {{id: c{i}, map_name: M{i}, mythic_title: T{i}, region: R{i}, "
        f"canon_status: CANON_LOCKED, ancient_function: f, modern_condition: c}}"
        for i in range(7)
    )
    return "seven_crowns:\n" + lines + "\n"


def _fourteen_good_regions() -> str:
    rows = "\n".join(
        f"  - {{id: r{i}, name: R{i}, threat_min: 1, threat_max: 5, canon_status: CANON_LOCKED}}"
        for i in range(14)
    )
    return "regions:\n" + rows + "\n"


def test_the_wrong_number_of_regions_is_refused(tmp_path: Path):
    body = (
        _GOOD_WORLD
        + _seven_good_crowns()
        + textwrap.dedent(
            """\
        regions:
          - {id: r1, name: R1, threat_min: 1, threat_max: 5, canon_status: CANON_LOCKED}
        """
        )
    )
    with pytest.raises(SeedError, match="exactly 14"):
        canon.load_canon(_write(tmp_path, body))


def test_an_inverted_threat_band_is_refused(tmp_path: Path):
    region_rows = "\n".join(
        f"  - {{id: r{i}, name: R{i}, threat_min: 1, threat_max: 5, canon_status: CANON_LOCKED}}"
        for i in range(13)
    )
    # The 14th region inverts its band.
    region_rows += (
        "\n  - {id: r13, name: R13, threat_min: 90, threat_max: 10, canon_status: CANON_LOCKED}"
    )
    body = _GOOD_WORLD + _seven_good_crowns() + "regions:\n" + region_rows + "\n"
    with pytest.raises(SeedError, match="threat_min exceeds threat_max"):
        canon.load_canon(_write(tmp_path, body))
