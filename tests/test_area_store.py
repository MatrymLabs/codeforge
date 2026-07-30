"""Test twin for parts/world/area_store.py -- the bench where generated areas wait for publication.

Acceptance: an area generated for (region, seed) saves, reloads identically, previews with its
provenance, and promotes GENERATED_LOCAL -> AUTHORED_LOCAL (version bumped); export writes a
snapshot without disturbing the bench copy; list-areas reports what is stored; the CLI `run` routes
each mutating subcommand. Refusal: promoting a non-GENERATED_LOCAL area is refused loud, loading or
promoting or exporting an unknown area is refused, and a bad or missing argument returns a usage
error rather than a crash.

Every test uses a tmp_path bench, so the real world_areas/ is never touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts.world import area_store
from parts.world.seed import SeedError

# --- Acceptance: the generate -> preview -> promote -> export lifecycle ---------------------------


def test_generate_saves_and_reloads_identically(tmp_path: Path):
    area = area_store.generate_and_save("veridia", 7, area_dir=tmp_path)
    assert area["canon_status"] == "GENERATED_LOCAL"
    assert area_store.load_area(area["id"], tmp_path) == area  # round-trips through JSON


def test_regenerating_the_same_inputs_overwrites_identically(tmp_path: Path):
    a = area_store.generate_and_save("caeloria", 4, area_dir=tmp_path)
    b = area_store.generate_and_save("caeloria", 4, area_dir=tmp_path)
    assert a == b  # 'regenerate before publication' is deterministic
    assert area_store.list_areas(tmp_path) == [a["id"]]  # not two copies


def test_preview_carries_identity_and_verdict(tmp_path: Path):
    area = area_store.generate_and_save("thalorin", 2, area_dir=tmp_path)
    text = area_store.preview(area)
    assert area["id"] in text
    assert "GENERATED_LOCAL" in text
    assert "validation: VALID" in text


def test_preview_shows_a_hidden_feature_and_a_rumor_when_present(tmp_path: Path):
    area = area_store.generate_and_save("the_deepreach", 1, area_dir=tmp_path)
    area["hidden"] = "a concealed alcove"
    area["rumor"] = "RUMOR: whether Netharion survived. No one down here can prove it."
    text = area_store.preview(area)
    assert "hidden: a concealed alcove" in text
    assert "RUMOR:" in text


def test_promote_flips_status_and_bumps_version(tmp_path: Path):
    area = area_store.generate_and_save("frostspire_peaks", 3, area_dir=tmp_path)
    promoted = area_store.promote(area["id"], tmp_path)
    assert promoted["canon_status"] == "AUTHORED_LOCAL"
    assert promoted["version"] == area["version"] + 1
    # The bench copy is the promoted one now (persisted).
    assert area_store.load_area(area["id"], tmp_path)["canon_status"] == "AUTHORED_LOCAL"


def test_export_snapshots_without_disturbing_the_bench(tmp_path: Path):
    area = area_store.generate_and_save("zhaar_desert", 9, area_dir=tmp_path)
    dest = tmp_path / "out" / "snapshot.json"
    written = area_store.export_area(area["id"], dest, tmp_path)
    assert written.exists()
    assert area_store.load_area(area["id"], tmp_path) == area  # bench copy unchanged


def test_list_areas_reports_the_bench(tmp_path: Path):
    assert area_store.list_areas(tmp_path) == []
    area_store.generate_and_save("veridia", 1, area_dir=tmp_path)
    area_store.generate_and_save("veridia", 2, area_dir=tmp_path)
    assert len(area_store.list_areas(tmp_path)) == 2


# --- Acceptance: the CLI dispatcher --------------------------------------------------------------


def test_run_generate_then_preview_then_promote(tmp_path: Path):
    code, text = area_store.run(["generate-area", "veridia", "--seed", "5"], tmp_path)
    assert code == 0 and "gen_cave_veridia_5" in text

    code, text = area_store.run(["preview-area", "gen_cave_veridia_5"], tmp_path)
    assert code == 0 and "GENERATED_LOCAL" in text

    code, text = area_store.run(["promote", "gen_cave_veridia_5"], tmp_path)
    assert code == 0 and "AUTHORED_LOCAL" in text


def test_run_generate_honours_size(tmp_path: Path):
    code, text = area_store.run(
        ["generate-area", "caeloria", "--seed", "1", "--size", "10"], tmp_path
    )
    assert code == 0
    assert len(area_store.load_area("gen_cave_caeloria_1", tmp_path)["rooms"]) == 10


def test_run_generate_tolerates_a_stray_flag(tmp_path: Path):
    # An unrecognized flag is ignored (seed defaults to 0), never a crash.
    code, text = area_store.run(["generate-area", "veridia", "--nope", "x"], tmp_path)
    assert code == 0 and "gen_cave_veridia_0" in text


def test_run_export(tmp_path: Path):
    area_store.generate_and_save("eldryn_forest", 8, area_dir=tmp_path)
    dest = tmp_path / "exported.json"
    code, text = area_store.run(["export", "gen_cave_eldryn_forest_8", str(dest)], tmp_path)
    assert code == 0 and dest.exists()


def test_run_list_areas_empty_and_full(tmp_path: Path):
    code, text = area_store.run(["list-areas"], tmp_path)
    assert code == 0 and "no generated areas" in text
    area_store.generate_and_save("veridia", 3, area_dir=tmp_path)
    code, text = area_store.run(["list-areas"], tmp_path)
    assert "gen_cave_veridia_3" in text


# --- Refusal: bad inputs are refused, not swallowed ----------------------------------------------


def test_promote_refuses_non_generated_content(tmp_path: Path):
    area = area_store.generate_and_save("veridia", 7, area_dir=tmp_path)
    area_store.promote(area["id"], tmp_path)  # now AUTHORED_LOCAL
    with pytest.raises(SeedError, match="only GENERATED_LOCAL"):
        area_store.promote(area["id"], tmp_path)  # cannot re-promote


def test_loading_an_unknown_area_fails_loud(tmp_path: Path):
    with pytest.raises(SeedError, match="no stored area"):
        area_store.load_area("gen_cave_nowhere_1", tmp_path)


def test_run_reports_a_refusal_as_exit_1(tmp_path: Path):
    code, text = area_store.run(["promote", "gen_cave_nowhere_1"], tmp_path)
    assert code == 1 and "refused" in text


def test_run_generate_for_an_unknown_region_is_refused(tmp_path: Path):
    code, text = area_store.run(["generate-area", "mordor"], tmp_path)
    assert code == 1 and "refused" in text


def test_run_usage_errors():
    assert area_store.run([])[0] == 2
    assert area_store.run(["generate-area"])[0] == 2
    assert area_store.run(["preview-area"])[0] == 2
    assert area_store.run(["promote"])[0] == 2
    assert area_store.run(["export", "only-one-arg"])[0] == 2
    assert area_store.run(["bogus-command"])[0] == 2
