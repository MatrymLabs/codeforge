"""Test twin for kernel/seedlab/workspace_verb.py + its engine-tick wiring.

Acceptance: the `workspace` verb lists/creates/inspects/operates engineering Seeds over an injected
Kernel, and is reachable + owner-gated through forge.handle_command (a feature isn't wired until the
tick proves it).

Refusal: a non-owner is denied at the command spine; unknown ids and bad usage fail cleanly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.seedlab.kernel import BlueprintKernel, BlueprintKernelError, InMemorySeedStore
from kernel.seedlab.model_store import InMemorySeedModels
from kernel.seedlab.project_model import Provenance
from kernel.seedlab.source_connector import LocalSource
from kernel.seedlab.source_modeler import model_and_store
from kernel.seedlab.workspace_verb import GmcpPush, workspace_command
from kernel.world.session import Session


def _kernel() -> BlueprintKernel:
    return BlueprintKernel(InMemorySeedStore(), clock=lambda: "2026-08-01T00:00:00+00:00")


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


# --- live GMCP push: the client's Project Hub updates when a workspace is resolved ----------------
def _capture() -> tuple[list[tuple[str, str, object]], GmcpPush]:
    """A fake gmcp_push that records (player_id, package, data) instead of touching the bus."""
    frames: list[tuple[str, str, object]] = []

    def push(player_id: str, package: str, data: object) -> None:
        frames.append((player_id, package, data))

    return frames, push


def test_status_pushes_a_live_project_status_frame() -> None:
    k = _kernel()
    workspace_command(_owner(), "create MyProj tracks tasks", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    frames, push = _capture()
    workspace_command(_owner(), f"status {sid}", kernel=k, gmcp_push=push)
    assert len(frames) == 1
    player_id, package, data = frames[0]
    assert player_id == "owner"  # pushed to the acting owner's channel
    assert package == "Project.Status"
    assert isinstance(data, dict) and data["seed"] == "MyProj"  # the resolved workspace


def test_lifecycle_changes_push_the_new_status() -> None:
    # create -> start -> stop each resolves a record, so each pushes the updated Project.Status.
    k = _kernel()
    frames, push = _capture()
    workspace_command(_owner(), "create Widget a demo", kernel=k, gmcp_push=push)
    sid = k.list_seeds()[0].identity.seed_id
    workspace_command(_owner(), f"start {sid}", kernel=k, gmcp_push=push)
    workspace_command(_owner(), f"stop {sid}", kernel=k, gmcp_push=push)
    phases = [data["phase"] for _pid, _pkg, data in frames]  # type: ignore[index]
    assert phases == ["created", "running", "stopped"]  # one live frame per lifecycle step


def test_an_unknown_workspace_pushes_nothing() -> None:
    # a refused lookup never fabricates a frame: the Project Hub must not light up on a bad id.
    frames, push = _capture()
    workspace_command(_owner(), "status nope", kernel=_kernel(), gmcp_push=push)
    assert frames == []


def test_a_session_without_a_player_id_pushes_nothing() -> None:
    # a bare/plain-text session has no GMCP channel, so the verb pushes nothing (and never crashes).
    k = _kernel()
    workspace_command(_owner(), "create P a demo", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    frames, push = _capture()
    workspace_command(Session(player_id=""), f"status {sid}", kernel=k, gmcp_push=push)
    assert frames == []


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


def test_connect_pushes_source_tree_and_model_schema(tmp_path: Path) -> None:
    # Connect resolves a real source AND a fresh model, so it lights up the Source Explorer, the
    # connector surface, and the Model view: one Source.Tree frame, one Source.Connection frame,
    # and one Model.Schema frame, to the acting owner.
    k = _kernel()
    workspace_command(_owner(), "create Proj a demo", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    store = InMemorySeedModels()
    frames, push = _capture()
    workspace_command(
        _owner(),
        f"connect {sid} {_source_dir(tmp_path)}",
        kernel=k,
        model_store=store,
        gmcp_push=push,
    )
    by_package = {pkg: data for _pid, pkg, data in frames}
    assert set(by_package) == {"Source.Tree", "Source.Connection", "Model.Schema"}
    tree = by_package["Source.Tree"]
    assert isinstance(tree, dict) and tree["seed"] == "Proj"  # labelled by the seed's name
    assert tree["repository"] == "gizmo"
    files = tree["files"]
    assert isinstance(files, list) and any(e["path"].endswith("__init__.py") for e in files)
    connection = by_package["Source.Connection"]
    assert isinstance(connection, dict) and connection["source_id"] == "gizmo"
    schema = by_package["Model.Schema"]
    assert isinstance(schema, dict) and schema["seed"] == "Proj" and "entities" in schema


def test_model_inspect_pushes_a_live_model_schema(tmp_path: Path) -> None:
    # Inspecting a modelled workspace refreshes the client's Model view with the latest schema.
    k = _kernel()
    workspace_command(_owner(), "create Proj a demo", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    store = InMemorySeedModels()
    model_and_store(
        store, sid, LocalSource(_source_dir(tmp_path), Provenance("gizmo-src", owner="owner"))
    )
    frames, push = _capture()
    workspace_command(_owner(), f"model {sid}", kernel=k, model_store=store, gmcp_push=push)
    assert len(frames) == 1
    _pid, package, data = frames[0]
    assert package == "Model.Schema"
    assert isinstance(data, dict) and data["seed"] == "Proj"


def test_model_with_no_models_pushes_nothing() -> None:
    # No Vision Theater: an empty model store lights up nothing (the Model view must not fabricate).
    k = _kernel()
    workspace_command(_owner(), "create Proj a demo", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    frames, push = _capture()
    out = workspace_command(
        _owner(), f"model {sid}", kernel=k, model_store=InMemorySeedModels(), gmcp_push=push
    )
    assert "No models" in out and frames == []


def test_connect_to_a_bad_path_pushes_nothing(tmp_path: Path) -> None:
    # A refused connect (no such dir) resolves no source, so it must push no frame.
    k = _kernel()
    workspace_command(_owner(), "create Proj a demo", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    frames, push = _capture()
    out = workspace_command(
        _owner(),
        f"connect {sid} {tmp_path / 'no-such-dir'}",
        kernel=k,
        model_store=InMemorySeedModels(),
        gmcp_push=push,
    )
    assert "workspace:" in out and frames == []


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


def test_connect_respects_an_allowed_sources_root(tmp_path: Path, monkeypatch) -> None:
    base = tmp_path / "allowed"
    base.mkdir()
    inside = _source_dir(base, "widget")
    outside = _source_dir(tmp_path, "sneaky")
    monkeypatch.setenv("SEEDLAB_SOURCES", str(base))

    k = _kernel()
    workspace_command(_owner(), "create Proj x", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    store = InMemorySeedModels()

    ok = workspace_command(_owner(), f"connect {sid} {inside}", kernel=k, model_store=store)
    assert "Connected" in ok  # a path under the allowed root is fine
    denied = workspace_command(_owner(), f"connect {sid} {outside}", kernel=k, model_store=store)
    assert "outside the allowed sources root" in denied  # a path outside is refused


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
    class _FailKernel(BlueprintKernel):
        def create_seed(self, *a: object, **k: object):
            raise BlueprintKernelError("boom")

    out = workspace_command(_owner(), "create X", kernel=_FailKernel(InMemorySeedStore()))
    assert out == "workspace: boom"


# --- engine tick: reachable + owner-gated ------------------------------------------------------
def test_reachable_for_an_owner_through_the_tick(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    from forge import handle_command  # noqa: PLC0415

    assert "workspace" in handle_command(_owner(), "workspace").lower()


def test_denied_for_a_player_at_the_spine(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    from forge import handle_command  # noqa: PLC0415

    assert "authority" in handle_command(Session(player_id="p"), "workspace").lower()


def test_create_persists_across_the_tick(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    from forge import handle_command  # noqa: PLC0415

    handle_command(_owner(), "workspace create ProjX a demo")
    assert "ProjX" in handle_command(_owner(), "workspace list")  # persisted via the file store


# --- run/report: tool-run evidence lights the 4th panel (Build.Report) ---------------------------
_ECHO = {"say-ok": ["python", "-c", "print('tooling ok')"]}


def _runnable(tmp_path: Path) -> tuple[BlueprintKernel, str, Path]:
    k = _kernel()
    workspace_command(_owner(), "create Proj a demo", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    return k, sid, _source_dir(tmp_path)


def test_run_records_evidence_and_pushes_build_report(tmp_path: Path) -> None:
    from kernel.seedlab.tool_runner import InMemoryRunLog  # noqa: PLC0415

    k, sid, src = _runnable(tmp_path)
    log = InMemoryRunLog()
    frames, push = _capture()
    out = workspace_command(
        _owner(), f"run {sid} {src} say-ok", kernel=k, run_log=log, allowlist=_ECHO, gmcp_push=push
    )
    assert "OK" in out and "say-ok" in out  # the run's human view
    assert len(log.for_seed(sid)) == 1 and log.for_seed(sid)[0].ok  # evidence recorded
    by_pkg = {pkg: data for _pid, pkg, data in frames}
    report = by_pkg["Build.Report"]  # the 4th panel's package, live
    assert isinstance(report, dict) and report["seed"] == "Proj" and report["ok"] is True
    assert report["steps"] and report["steps"][0]["status"] == "passed"


def test_run_refuses_an_unlisted_profile_and_pushes_nothing(tmp_path: Path) -> None:
    from kernel.seedlab.tool_runner import InMemoryRunLog  # noqa: PLC0415

    k, sid, src = _runnable(tmp_path)
    log = InMemoryRunLog()
    frames, push = _capture()
    out = workspace_command(
        _owner(), f"run {sid} {src} rm-rf", kernel=k, run_log=log, allowlist=_ECHO, gmcp_push=push
    )
    assert "not an approved command profile" in out
    assert log.for_seed(sid) == [] and frames == []  # nothing ran, nothing pushed


def test_run_respects_the_allowed_sources_root(tmp_path: Path, monkeypatch) -> None:
    from kernel.seedlab.tool_runner import InMemoryRunLog  # noqa: PLC0415

    k, sid, _src = _runnable(tmp_path / "inside")
    outside = _source_dir(tmp_path / "outside", "sneaky")
    monkeypatch.setenv("SEEDLAB_SOURCES", str(tmp_path / "inside"))
    out = workspace_command(
        _owner(), f"run {sid} {outside} say-ok", kernel=k, run_log=InMemoryRunLog(), allowlist=_ECHO
    )
    assert "outside the allowed sources root" in out


def test_run_usage_and_unknown_seed_are_clean(tmp_path: Path) -> None:
    assert "usage: workspace run" in workspace_command(_owner(), "run only two", kernel=_kernel())
    out = workspace_command(
        _owner(), f"run nope {tmp_path} say-ok", kernel=_kernel(), allowlist=_ECHO
    )
    assert "workspace:" in out


def test_report_replays_the_recorded_runs_and_pushes(tmp_path: Path) -> None:
    from kernel.seedlab.tool_runner import InMemoryRunLog  # noqa: PLC0415

    k, sid, src = _runnable(tmp_path)
    log = InMemoryRunLog()
    workspace_command(_owner(), f"run {sid} {src} say-ok", kernel=k, run_log=log, allowlist=_ECHO)
    frames, push = _capture()
    out = workspace_command(_owner(), f"report {sid}", kernel=k, run_log=log, gmcp_push=push)
    assert "1 run(s), 1 ok" in out
    assert [pkg for _p, pkg, _d in frames] == ["Build.Report"]  # inspect resolves state -> re-push


def test_report_with_no_runs_is_honest_and_pushes_nothing(tmp_path: Path) -> None:
    from kernel.seedlab.tool_runner import InMemoryRunLog  # noqa: PLC0415

    k, sid, _ = _runnable(tmp_path)
    frames, push = _capture()
    out = workspace_command(
        _owner(), f"report {sid}", kernel=k, run_log=InMemoryRunLog(), gmcp_push=push
    )
    assert "No tool runs" in out and frames == []


def test_report_reachable_through_the_tick(tmp_path: Path, monkeypatch) -> None:
    # A feature is not wired until handle_command proves it (the engine-tick law).
    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path / "lab"))
    from forge import handle_command  # noqa: PLC0415

    s = _owner()
    handle_command(s, "workspace create TickProj proves reachability")
    out = handle_command(s, "workspace report " + _tick_seed_id(tmp_path))
    assert "No tool runs" in out or "workspace:" in out


def _tick_seed_id(tmp_path: Path) -> str:
    from kernel.seedlab.kernel import BlueprintKernel, FileSeedStore  # noqa: PLC0415

    k = BlueprintKernel(FileSeedStore(tmp_path / "lab" / "seeds"))
    seeds = [r for r in k.list_seeds() if r.identity.name == "TickProj"]
    return seeds[0].identity.seed_id if seeds else "unknown"


# --- backup / restore: surface the Seed backup lifecycle in-world (Slice C in the MUD) -----------
def _backups(tmp_path: Path):
    from kernel.seedlab.backup import BlueprintBackups  # noqa: PLC0415

    return BlueprintBackups(tmp_path / "bk", clock=lambda: "2026-08-02T00:00:00+00:00")


def test_backup_then_list_then_restore_rolls_back(tmp_path: Path) -> None:
    k = _kernel()
    store = _backups(tmp_path)
    workspace_command(_owner(), "create Proj a demo", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    workspace_command(_owner(), f"start {sid}", kernel=k)  # RUNNING is the state we back up

    out = workspace_command(_owner(), f"backup {sid}", kernel=k, backups=store)
    assert "Backed up" in out
    bid = store.list_backups(sid)[-1].backup_id
    assert bid in out

    listing = workspace_command(_owner(), f"backups {sid}", kernel=k, backups=store)
    assert bid in listing and "INTACT" in listing

    workspace_command(_owner(), f"stop {sid}", kernel=k)  # a change to undo
    restored = workspace_command(_owner(), f"restore {sid} {bid}", kernel=k, backups=store)
    assert "RUNNING" in restored  # rolled back to the backed-up state
    assert k.get(sid).status == "running"


def test_backup_of_an_unknown_workspace_is_clean(tmp_path: Path) -> None:
    out = workspace_command(_owner(), "backup nope", kernel=_kernel(), backups=_backups(tmp_path))
    assert "workspace: no Seed" in out


def test_backups_of_a_workspace_with_none_is_honest(tmp_path: Path) -> None:
    k = _kernel()
    workspace_command(_owner(), "create Proj a demo", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    out = workspace_command(_owner(), f"backups {sid}", kernel=k, backups=_backups(tmp_path))
    assert "No backups" in out


def test_restore_needs_a_backup_id(tmp_path: Path) -> None:
    out = workspace_command(
        _owner(), "restore only-one-arg", kernel=_kernel(), backups=_backups(tmp_path)
    )
    assert "usage: workspace restore" in out


def test_restore_of_a_missing_backup_is_refused(tmp_path: Path) -> None:
    k = _kernel()
    workspace_command(_owner(), "create Proj a demo", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    out = workspace_command(
        _owner(), f"restore {sid} bk-nope", kernel=k, backups=_backups(tmp_path)
    )
    assert "workspace:" in out and "missing" in out


def test_a_non_owner_cannot_restore_a_workspace(tmp_path: Path) -> None:
    k = _kernel()
    store = _backups(tmp_path)
    workspace_command(_owner(), "create Proj a demo", kernel=k)
    sid = k.list_seeds()[0].identity.seed_id
    workspace_command(_owner(), f"backup {sid}", kernel=k, backups=store)
    bid = store.list_backups(sid)[-1].backup_id
    intruder = Session(player_id="mallory")
    intruder.rank = (
        "owner"  # even a rank-owner who is not the SEED's owner is refused by the Kernel
    )
    out = workspace_command(intruder, f"restore {sid} {bid}", kernel=k, backups=store)
    assert "workspace:" in out and "owner" in out


def test_backup_and_restore_through_the_tick(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path))
    from forge import handle_command  # noqa: PLC0415

    handle_command(_owner(), "workspace create ProjX a demo")
    # find the created seed id from the list output's second line
    handle_command(_owner(), "workspace list")
    from kernel.seedlab.kernel import BlueprintKernel, FileSeedStore  # noqa: PLC0415

    sid = next(
        r.identity.seed_id
        for r in BlueprintKernel(FileSeedStore(tmp_path / "seeds")).list_seeds()
        if r.identity.name == "ProjX"
    )
    handle_command(_owner(), f"workspace start {sid}")
    out = handle_command(_owner(), f"workspace backup {sid}")
    assert "Backed up" in out
    bid = out.split("-> ")[1].split(" ")[0]
    handle_command(_owner(), f"workspace stop {sid}")
    restored = handle_command(_owner(), f"workspace restore {sid} {bid}")
    assert "RUNNING" in restored  # the file-backed backup + restore survived the real tick


def test_backup_needs_a_seed_id() -> None:
    assert "usage: workspace backup" in workspace_command(_owner(), "backup", kernel=_kernel())


def test_backups_needs_a_seed_id() -> None:
    assert "usage: workspace backups" in workspace_command(_owner(), "backups", kernel=_kernel())


def test_backups_of_an_unknown_workspace_is_clean(tmp_path: Path) -> None:
    out = workspace_command(_owner(), "backups nope", kernel=_kernel(), backups=_backups(tmp_path))
    assert "workspace: no Seed" in out
