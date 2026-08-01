"""Test twin for parts/seedlab/workspace_verb.py + its engine-tick wiring.

Acceptance: the `workspace` verb lists/creates/inspects/operates engineering Seeds over an injected
Kernel, and is reachable + owner-gated through forge.handle_command (a feature isn't wired until the
tick proves it).

Refusal: a non-owner is denied at the command spine; unknown ids and bad usage fail cleanly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts.seedlab.kernel import InMemorySeedStore, SeedKernel, SeedKernelError
from parts.seedlab.model_store import InMemorySeedModels
from parts.seedlab.project_model import Provenance
from parts.seedlab.source_connector import LocalSource
from parts.seedlab.source_modeler import model_and_store
from parts.seedlab.workspace_verb import workspace_command
from parts.world.session import Session


def _kernel() -> SeedKernel:
    return SeedKernel(InMemorySeedStore(), clock=lambda: "2026-08-01T00:00:00+00:00")


def _owner() -> Session:
    s = Session(player_id="owner")
    s.rank = "owner"
    return s


# --- unit: dispatch over an injected Kernel ----------------------------------------------------
def test_list_always_shows_the_reference_game_seed() -> None:
    # Stage 8: the flagship game is one kind of Seed, so it always appears in the workspace list.
    out = workspace_command(_owner(), "list", kernel=_kernel())
    assert "Aethryn" in out and "reference game" in out


def test_create_then_list_status_start_stop() -> None:
    k = _kernel()
    assert "Created workspace" in workspace_command(
        _owner(), "create MyProj tracks tasks", kernel=k
    )
    sid = k.list_seeds()[0].identity.seed_id
    assert "MyProj" in workspace_command(_owner(), "list", kernel=k)
    assert "CREATED" in workspace_command(_owner(), f"status {sid}", kernel=k)
    assert "RUNNING" in workspace_command(_owner(), f"start {sid}", kernel=k)
    assert "STOPPED" in workspace_command(_owner(), f"stop {sid}", kernel=k)


def test_create_needs_a_name() -> None:
    assert "usage: workspace create" in workspace_command(_owner(), "create", kernel=_kernel())


def test_status_of_an_unknown_workspace_is_clean() -> None:
    assert "workspace: no Seed" in workspace_command(_owner(), "status nope", kernel=_kernel())


def test_model_subcommand_empty_then_populated(tmp_path: Path) -> None:
    k = _kernel()
    workspace_command(_owner(), "create Widget a demo", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    store = InMemorySeedModels()
    assert "No models" in workspace_command(_owner(), f"model {sid}", kernel=k, model_store=store)

    src_root = tmp_path / "proj"
    (src_root / "widget").mkdir(parents=True)
    (src_root / "widget" / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "pyproject.toml").write_text("[project]\nname = 'widget'\n", encoding="utf-8")
    model_and_store(store, sid, LocalSource(src_root, Provenance("widget-src", owner="owner")))
    out = workspace_command(_owner(), f"model {sid}", kernel=k, model_store=store)
    assert "widget" in out


def _source_dir(tmp_path: Path, name: str = "gizmo") -> Path:
    root = tmp_path / name
    (root / name).mkdir(parents=True)
    (root / name / "__init__.py").write_text("", encoding="utf-8")
    (root / "pyproject.toml").write_text(f"[project]\nname = '{name}'\n", encoding="utf-8")
    return root


def test_connect_models_a_source_in_world(tmp_path: Path) -> None:
    # The in-MUD loop: create a workspace, connect a source, model it, `model` shows it -- no CLI.
    k = _kernel()
    workspace_command(_owner(), "create Proj a demo", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    store = InMemorySeedModels()
    path = _source_dir(tmp_path)

    out = workspace_command(_owner(), f"connect {sid} {path}", kernel=k, model_store=store)
    assert "Connected" in out and "modeled it" in out and "gizmo" in out
    assert "gizmo" in workspace_command(_owner(), f"model {sid}", kernel=k, model_store=store)


def test_connect_needs_a_seed_and_path() -> None:
    assert "usage: workspace connect" in workspace_command(
        _owner(), "connect only-one", kernel=_kernel()
    )


def test_connect_to_an_unknown_workspace_is_clean(tmp_path: Path) -> None:
    out = workspace_command(_owner(), f"connect nope {tmp_path}", kernel=_kernel())
    assert "workspace: no Seed" in out


def test_connect_to_a_bad_path_is_clean() -> None:
    k = _kernel()
    workspace_command(_owner(), "create Proj x", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    out = workspace_command(_owner(), f"connect {sid} /no/such/dir/xyz", kernel=k)
    assert "workspace:" in out and "directory" in out


def test_model_of_an_unknown_workspace_is_clean() -> None:
    assert "workspace: no Seed" in workspace_command(_owner(), "model nope", kernel=_kernel())


def test_unknown_subcommand_shows_usage() -> None:
    assert "workspace commands:" in workspace_command(_owner(), "frobnicate", kernel=_kernel())


def test_a_non_owner_cannot_operate_anothers_workspace() -> None:
    k = _kernel()
    workspace_command(_owner(), "create Shared x", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    intruder = Session(player_id="mallory")
    assert "workspace:" in workspace_command(intruder, f"start {sid}", kernel=k)  # Kernel authz


@pytest.mark.parametrize("sub", ["status", "start", "model"])
def test_subcommands_need_an_id(sub: str) -> None:
    assert f"usage: workspace {sub}" in workspace_command(_owner(), sub, kernel=_kernel())


def test_a_create_failure_is_reported_cleanly() -> None:
    class _FailKernel(SeedKernel):
        def create_seed(self, *a: object, **k: object):
            raise SeedKernelError("boom")

    out = workspace_command(_owner(), "create X", kernel=_FailKernel(InMemorySeedStore()))
    assert out == "workspace: boom"


# --- engine tick: reachable + owner-gated ------------------------------------------------------
def test_reachable_for_an_owner_through_the_tick(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    from forge import handle_command

    assert "workspace" in handle_command(_owner(), "workspace").lower()


def test_denied_for_a_player_at_the_spine(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    from forge import handle_command

    assert "authority" in handle_command(Session(player_id="p"), "workspace").lower()


def test_create_persists_across_the_tick(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    from forge import handle_command

    handle_command(_owner(), "workspace create ProjX a demo")
    assert "ProjX" in handle_command(_owner(), "workspace list")  # persisted via the file store
