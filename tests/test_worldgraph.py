"""Test twin for kernel/world/worldgraph.py -- the region topology and reachability.

Acceptance: the shipped graph covers all 14 canon regions, the whole world is reachable from the
spawn by land or sea (find-unreachable is clean), The Deepreach connects by its one-way land listing
(undirected), and the island / sky regions connect only by shared sea. Refusal: a graph missing a
region, naming an unknown neighbour or sea, or self-linking fails loud; an isolated region is
FLAGGED unreachable (the guard bites); inspecting or reaching an unknown region is refused.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kernel.world import canon, worldgraph
from kernel.world.seed import BlueprintError

_SEAS = [
    "western_ocean",
    "northland_sea",
    "central_sea",
    "sundaram_sea",
    "southern_ocean",
    "eastern_ocean",
]


# --- Acceptance: the shipped graph is complete and fully connected -------------------------------


def test_graph_covers_every_canon_region():
    rows = worldgraph.load_graph()["regions"]
    assert set(rows) == {r["id"] for r in canon.regions()}


def test_the_whole_world_is_reachable_from_the_spawn():
    assert worldgraph.unreachable_regions() == []
    assert len(worldgraph.reachable_from()) == 14


def test_the_deepreach_connects_by_its_one_way_land_listing():
    # The Deepreach lists surface regions; those do not list it back. Undirected reachability still
    # links them: zhaar_desert reaches the_deepreach even though zhaar does not list it.
    assert "the_deepreach" in worldgraph.neighbors("zhaar_desert")
    assert "the_deepreach" not in worldgraph.load_graph()["regions"]["zhaar_desert"]["land"]


def test_the_voidscar_connects_only_by_shared_sea():
    nbrs = worldgraph.neighbors("the_voidscar")
    assert nbrs  # not stranded
    # All neighbours share the eastern ocean; the region has no land links.
    assert worldgraph.load_graph()["regions"]["the_voidscar"]["land"] == []
    assert "skyward_spires" in nbrs  # another eastern-ocean region


def test_region_detail_reports_facts_and_topology():
    text = worldgraph.region_detail("veridia")
    assert "Veridia" in text and "1-30" in text
    assert "reachable from veridia: yes" in text


def test_graph_lines_lists_every_region():
    text = worldgraph.graph_lines()
    for region in canon.regions():
        assert region["id"] in text


# --- Refusal: an isolated region is flagged, unknowns are refused --------------------------------


def test_an_isolated_region_is_flagged_unreachable():
    synthetic = {
        "seas": _SEAS,
        "regions": {
            "a": {"land": ["b"], "seas": []},
            "b": {"land": ["a"], "seas": []},
            "island": {"land": [], "seas": []},
        },
    }
    assert worldgraph.unreachable_regions("a", synthetic) == ["island"]


def test_neighbors_of_an_unknown_region_is_refused():
    with pytest.raises(BlueprintError, match="unknown region"):
        worldgraph.neighbors("mordor", worldgraph.load_graph())


def test_reachable_from_an_unknown_start_is_refused():
    with pytest.raises(BlueprintError, match="unknown start"):
        worldgraph.reachable_from("mordor")


def test_region_detail_for_a_graph_region_absent_from_canon_is_refused():
    synthetic = {"seas": _SEAS, "regions": {"ghostland": {"land": [], "seas": []}}}
    with pytest.raises(BlueprintError, match="not in canon"):
        worldgraph.region_detail("ghostland", synthetic)


# --- Refusal: a malformed graph file fails loud --------------------------------------------------


def _full_regions() -> dict:
    return {r["id"]: {"land": [], "seas": []} for r in canon.regions()}


def _write(tmp_path: Path, data: object) -> Path:
    p = tmp_path / "world_graph.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def test_missing_file_fails_loud(tmp_path: Path):
    with pytest.raises(BlueprintError, match="not found"):
        worldgraph.load_graph(tmp_path / "nope.yaml")


def test_a_non_mapping_file_fails_loud(tmp_path: Path):
    with pytest.raises(BlueprintError, match="not a mapping"):
        worldgraph.load_graph(_write(tmp_path, ["a", "b"]))


def test_no_seas_fails_loud(tmp_path: Path):
    with pytest.raises(BlueprintError, match="bodies of water"):
        worldgraph.load_graph(_write(tmp_path, {"seas": [], "regions": _full_regions()}))


def test_non_mapping_regions_fails_loud(tmp_path: Path):
    with pytest.raises(BlueprintError, match="'regions' must be a mapping"):
        worldgraph.load_graph(_write(tmp_path, {"seas": _SEAS, "regions": ["veridia"]}))


def test_a_missing_region_fails_loud(tmp_path: Path):
    regions = _full_regions()
    del regions["veridia"]
    with pytest.raises(BlueprintError, match="no topology row"):
        worldgraph.load_graph(_write(tmp_path, {"seas": _SEAS, "regions": regions}))


def test_a_non_canon_region_fails_loud(tmp_path: Path):
    regions = _full_regions()
    regions["atlantis"] = {"land": [], "seas": []}
    with pytest.raises(BlueprintError, match="not a canon region"):
        worldgraph.load_graph(_write(tmp_path, {"seas": _SEAS, "regions": regions}))


def test_a_self_link_fails_loud(tmp_path: Path):
    regions = _full_regions()
    regions["veridia"]["land"] = ["veridia"]
    with pytest.raises(BlueprintError, match="cannot border itself"):
        worldgraph.load_graph(_write(tmp_path, {"seas": _SEAS, "regions": regions}))


def test_an_unknown_land_neighbour_fails_loud(tmp_path: Path):
    regions = _full_regions()
    regions["veridia"]["land"] = ["narnia"]
    with pytest.raises(BlueprintError, match="unknown land neighbour"):
        worldgraph.load_graph(_write(tmp_path, {"seas": _SEAS, "regions": regions}))


def test_an_unknown_sea_fails_loud(tmp_path: Path):
    regions = _full_regions()
    regions["veridia"]["seas"] = ["sea_of_monsters"]
    with pytest.raises(BlueprintError, match="unknown sea"):
        worldgraph.load_graph(_write(tmp_path, {"seas": _SEAS, "regions": regions}))
