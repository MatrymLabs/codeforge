"""Test twin for evolution store + the read-only MUD command.

Acceptance: a run round-trips to disk and the `evolution` views render it. Guarantee: the MUD
surface is READ-ONLY -- it lists/shows recorded runs and never executes a bake-off or writes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts import blueprint as bp
from parts.evolution import store
from parts.evolution.bakeoff import build_score_sheet_pairs, run_bakeoff
from parts.evolution.command import evolution
from parts.evolution.genome import BlueprintGenome


def _run():
    seed = bp.Blueprint("fit_column", "Fit Column", "Fit text to a width.", ("pure",))
    genome = BlueprintGenome(
        genome_id="fit_column",
        seed=seed,
        purpose="Evolve a fixed-width column formatter.",
        test_obligations=("matches the oracle",),
        documentation_obligations=("docstring",),
        expression_targets=("code", "tests"),
    )
    return run_bakeoff(genome, build_score_sheet_pairs("fit_column"), run_id="run_alpha")


@pytest.fixture
def evo_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CODEFORGE_EVOLUTION_DIR", str(tmp_path))
    return tmp_path


def test_a_run_round_trips_to_disk(evo_dir: Path) -> None:
    path = store.write_run(_run())
    assert path.exists() and path.suffix == ".json"
    assert store.list_runs() == ["run_alpha"]
    summary = store.load_summary("run_alpha")
    assert summary and summary["genome_id"] == "fit_column"
    assert "BLUEPRINT EVOLUTION LAB" in (store.load_report("run_alpha") or "")


def test_status_with_no_runs_guides_to_make(evo_dir: Path) -> None:
    out = evolution("status")
    assert "no runs recorded" in out and "make evolution" in out


def test_status_lists_a_recorded_run(evo_dir: Path) -> None:
    store.write_run(_run())
    out = evolution()  # default view is status
    assert "run_alpha" in out and "fit_column" in out


def test_show_renders_the_stored_report(evo_dir: Path) -> None:
    store.write_run(_run())
    out = evolution("show run_alpha")
    assert "BLUEPRINT EVOLUTION LAB" in out and "HUMAN_DECISION_REQUIRED" in out


def test_show_an_unknown_run_is_guided(evo_dir: Path) -> None:
    assert "No recorded run" in evolution("show ghost")


def test_explain_describes_the_doctrine(evo_dir: Path) -> None:
    out = evolution("explain")
    assert "READ-ONLY" in out and "human_decision_required" in out


def test_an_unknown_view_is_guided(evo_dir: Path) -> None:
    assert "Unknown evolution view" in evolution("promote everything")


def test_show_without_an_id_is_guided(evo_dir: Path) -> None:
    assert "Show which run?" in evolution("show")


def test_store_helpers_accept_an_explicit_root_and_handle_absence(tmp_path: Path) -> None:
    # Explicit root (not the env default) + the missing-run/missing-dir paths.
    assert store.list_runs(root=tmp_path / "absent") == []
    assert store.load_summary("ghost", root=tmp_path) is None
    assert store.load_report("ghost", root=tmp_path) is None
    store.write_run(_run(), root=tmp_path)
    assert store.list_runs(root=tmp_path) == ["run_alpha"]


def test_evolution_is_reachable_and_read_only_through_the_tick(evo_dir: Path) -> None:
    # A feature isn't wired until handle_command proves a player can reach it -- and reaching
    # it must NOT produce a run (the MUD never executes the lab).
    from forge import handle_command
    from parts.session import Session

    out = handle_command(Session(player_id="evo_tick"), "evolution")
    assert "EVOLUTION LAB" in out
    assert store.list_runs() == []  # the read-only view created nothing
