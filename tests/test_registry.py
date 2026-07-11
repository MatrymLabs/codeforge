"""Test twin for parts/registry.py -- the Classification Registry filing engine.

Acceptance (valid records load, mint returns the next free id, a clean collective
validates) and refusal (malformed designation, bad status, missing field, unknown
field, duplicates, orphaned paths, dangling supersedes) are both pinned.
"""

import json
from pathlib import Path

import pytest

from parts.registry import (
    Designation,
    RegistryError,
    load_collective,
    load_designations,
    mint_designation,
    save_designations,
    validate,
)


def _rec(designation: str = "RM-UM03-S02-N001-001-R0", **over: object) -> Designation:
    base: dict[str, object] = dict(
        designation=designation,
        name="Classroom of Practical Arts",
        status="prototype",
        function="Room for lessons, quizzes, and Professor Codex.",
        label="classroom",
        file="seeds/first-forge/rooms.yaml",
    )
    base.update(over)
    return Designation(**base)  # type: ignore[arg-type]


# --- the designation is canonical --------------------------------------------


def test_structural_fields_are_parsed_from_the_designation() -> None:
    d = _rec("PRT-UM05-S01-N001-007-R2")
    assert d.type == "PRT"
    assert d.domain == "UM05"
    assert d.sector == "S01"
    assert d.node == "N001"
    assert d.sequence == "007"
    assert d.revision == "R2"


def test_a_malformed_designation_is_refused() -> None:
    with pytest.raises(RegistryError, match="not a valid designation"):
        _rec("ROOM-UM03-S02-N1-001-R0")


def test_an_unknown_domain_is_refused() -> None:
    # UM11 matches the id pattern but is not one of the ten unimatrices
    with pytest.raises(RegistryError, match="not a unimatrix"):
        _rec("RM-UM11-S01-N001-001-R0")


def test_a_bad_status_is_refused() -> None:
    with pytest.raises(RegistryError, match="status"):
        _rec(status="live")


def test_a_missing_required_field_is_refused() -> None:
    with pytest.raises(RegistryError, match="'label' is required"):
        _rec(label="")


# --- loading -----------------------------------------------------------------


def test_load_designations_reads_a_list(tmp_path: Path) -> None:
    path = tmp_path / "rooms.json"
    path.write_text(
        json.dumps(
            [
                {
                    "designation": "RM-UM03-S02-N001-001-R0",
                    "name": "Classroom",
                    "status": "prototype",
                    "function": "lessons",
                    "label": "classroom",
                    "file": "seeds/x.yaml",
                }
            ]
        )
    )
    records = load_designations(path)
    assert len(records) == 1 and records[0].label == "classroom"


def test_missing_file_loads_empty(tmp_path: Path) -> None:
    assert load_designations(tmp_path / "absent.json") == []


def test_designations_are_parsed_once_and_cached(tmp_path: Path) -> None:
    # The registry is immutable within a run: a second load of an unchanged file returns the
    # SAME object (no re-decode of the JSON), via the shared mtime-guarded loader cache.
    path = tmp_path / "rooms.json"
    path.write_text(
        json.dumps(
            [
                {
                    "designation": "RM-UM03-S02-N001-001-R0",
                    "name": "Classroom",
                    "status": "prototype",
                    "function": "lessons",
                    "label": "classroom",
                    "file": "seeds/x.yaml",
                }
            ]
        )
    )
    first = load_designations(path)
    second = load_designations(path)
    assert first is second  # unchanged file -> reused, not re-parsed


def test_a_non_list_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"not": "a list"}))
    with pytest.raises(RegistryError, match="must be a list"):
        load_designations(path)


def test_an_unknown_field_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            [
                {
                    "designation": "RM-UM03-S02-N001-001-R0",
                    "name": "x",
                    "status": "prototype",
                    "function": "y",
                    "label": "z",
                    "file": "f",
                    "bogus": 1,
                }
            ]
        )
    )
    with pytest.raises(RegistryError, match="unknown field"):
        load_designations(path)


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "designations" / "rooms.json"
    save_designations([_rec()], path)
    assert load_designations(path)[0].designation == "RM-UM03-S02-N001-001-R0"


def test_load_collective_merges_every_file(tmp_path: Path) -> None:
    save_designations([_rec("RM-UM03-S02-N001-001-R0")], tmp_path / "rooms.json")
    save_designations(
        [_rec("NPC-UM03-S02-N002-001-R0", label="codex", name="Codex", file="seeds/x.yaml")],
        tmp_path / "npcs.json",
    )
    assert len(load_collective(tmp_path)) == 2


def test_load_collective_absent_dir_is_empty(tmp_path: Path) -> None:
    assert load_collective(tmp_path / "nope") == []


# --- minting -----------------------------------------------------------------


def test_mint_returns_the_first_free_sequence() -> None:
    assert mint_designation("RM", "UM03", []) == "RM-UM03-S01-N001-001-R0"


def test_mint_fills_the_lowest_gap() -> None:
    existing = ["RM-UM03-S01-N001-001-R0", "RM-UM03-S01-N001-003-R0"]
    assert mint_designation("RM", "UM03", existing) == "RM-UM03-S01-N001-002-R0"


def test_mint_is_scoped_by_domain_and_node() -> None:
    # a different domain never collides with this node's sequence
    existing = ["RM-UM08-S01-N001-001-R0"]
    assert mint_designation("RM", "UM03", existing) == "RM-UM03-S01-N001-001-R0"


def test_a_minted_designation_is_itself_valid() -> None:
    minted = mint_designation("PRT", "UM05", [], node="N012")
    assert _rec(minted, label="minted", name="m", file="f").designation == minted


def test_mint_refuses_a_bad_type() -> None:
    with pytest.raises(RegistryError, match="type"):
        mint_designation("ROOM", "UM03", [])


# --- validation --------------------------------------------------------------


def test_a_clean_collective_validates(tmp_path: Path) -> None:
    (tmp_path / "seeds").mkdir()
    (tmp_path / "seeds" / "rooms.yaml").write_text("x")
    ok = _rec(file="seeds/rooms.yaml")
    assert validate([ok], root=tmp_path) == []


def test_validate_flags_duplicate_designations() -> None:
    dupes = [_rec(), _rec()]
    problems = validate(dupes, check_files=False)
    assert any("duplicate designation" in p for p in problems)


def test_validate_flags_a_label_filed_twice_under_one_type() -> None:
    twins = [_rec("RM-UM03-S02-N001-001-R0"), _rec("RM-UM03-S02-N001-002-R0")]
    problems = validate(twins, check_files=False)
    assert any("filed 2x" in p for p in problems)


def test_validate_flags_an_orphaned_file(tmp_path: Path) -> None:
    # a built room (active) with a missing source file is an orphan
    problems = validate([_rec(status="active", file="seeds/ghost.yaml")], root=tmp_path)
    assert any("file not found" in p for p in problems)


def test_validate_flags_missing_tests(tmp_path: Path) -> None:
    # a built object whose tests path doesn't exist is flagged (the file exists)
    (tmp_path / "seeds").mkdir()
    (tmp_path / "seeds" / "rooms.yaml").write_text("x")
    rec = _rec(status="active", file="seeds/rooms.yaml", tests="tests/ghost.py")
    assert any("tests not found" in p for p in validate([rec], root=tmp_path))


def test_validate_flags_a_dangling_supersede() -> None:
    problems = validate([_rec(superseded_by="RM-UM03-S02-N001-999-R0")], check_files=False)
    assert any("is not filed" in p for p in problems)


def test_the_shipped_registry_validates() -> None:
    # the real registry/designations/*.json must always be clean -- it can never rot
    records = load_collective()
    assert records, "expected the shipped registry to hold records"
    assert validate(records) == []


def test_a_prototype_is_exempt_from_the_file_check(tmp_path: Path) -> None:
    # a planned room (prototype) has no source file yet -- it must still validate clean
    planned = _rec(status="prototype", file="seeds/haven-city/rooms.yaml")
    assert validate([planned], root=tmp_path) == []
    # but a non-prototype with the same ghost file is still flagged
    built = _rec("RM-UM02-S01-N001-009-R0", status="active", file="seeds/haven-city/rooms.yaml")
    assert any("file not found" in p for p in validate([built], root=tmp_path))
