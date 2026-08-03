"""Test twin for kernel/seedlab/workspace_gmcp.py -- the engine speaking the client's workspace
GMCP contracts.

Acceptance: each builder projects a seedlab record into the exact package shape the Master Client
parses (Project.Status, Source.Tree, Model.Schema, Build.Report), and a Seed.Create request mints a
real Seed and returns a Seed.Created verdict. Refusal (fail loud / honest): a malformed create frame
never reaches the Kernel and becomes an ok:false verdict; a duplicate name is refused with a reason;
the engine emits only what it models (empty entity fields; Build.Report carries real run steps and
an honest ok verdict but empty test/artifact seams, never a fabricated count).
"""

from __future__ import annotations

import json

import pytest

from kernel.gmcp import gmcp_frame
from kernel.seedlab.kernel import InMemorySeedStore, SeedKernel, SeedKernelError
from kernel.seedlab.project_model import Provenance, SpecSource, extract_model
from kernel.seedlab.source_connector import SourceRecord
from kernel.seedlab.tool_runner import ToolRunResult
from kernel.seedlab.workspace_gmcp import (
    ARCHITECTURE_MAP_PACKAGE,
    BUILD_REPORT_PACKAGE,
    MODEL_SCHEMA_PACKAGE,
    PROJECT_STATUS_PACKAGE,
    SOURCE_TREE_PACKAGE,
    SeedCreateRequest,
    WorkspaceContractError,
    architecture_map,
    build_report,
    create_from_request,
    load_module_designations,
    model_schema,
    parse_seed_create,
    project_status,
    seed_created,
    source_tree,
    workspace_packages,
)

_CLOCK = iter(f"2026-08-01T00:00:{n:02d}+00:00" for n in range(120))


def _kernel() -> SeedKernel:
    return SeedKernel(InMemorySeedStore(), clock=lambda: next(_CLOCK))


def _seed(kernel: SeedKernel, name: str = "Job Tracker", sid: str = "seed-jt"):
    return kernel.create_seed(name, "josh", "a tiny tracker", seed_id=sid)


def _source() -> SourceRecord:
    return SourceRecord(
        source_id="demo-src",
        provenance=Provenance("demo-src", owner="josh", visibility="private"),
        root="/home/josh/projects/job-tracker",
        file_count=2,
        branch="main",
        commit="a1b2c3d",
    )


def _model():
    spec = SpecSource(
        {"identity": "job-tracker", "entities": ["Application", "Tag"]},
        Provenance("job-tracker", owner="josh"),
    )
    return extract_model(spec)


def _run(
    profile: str = "ci", *, kind: str = "build", exit_code: int = 0, timed_out: bool = False
) -> ToolRunResult:
    return ToolRunResult(
        seed_id="seed-jt",
        kind=kind,
        profile=profile,
        argv=["make", kind],
        exit_code=exit_code,
        output="",
        duration=0.1,
        timed_out=timed_out,
        cwd="/srv/seed/work",
        when="2026-08-01T00:00:00+00:00",
    )


# --- Project.Status: the Seed's lifecycle projected -----------------------------------------------


def test_project_status_names_the_seed_and_its_phase() -> None:
    payload = project_status(_seed(_kernel()))
    assert payload == {"seed": "Job Tracker", "phase": "created"}  # no branch/build/tests known yet


def test_project_status_carries_branch_build_and_tests_when_known() -> None:
    payload = project_status(
        _seed(_kernel()),
        branch="main",
        build="passing",
        tests={"passed": 42, "failed": 0},
    )
    assert payload["branch"] == "main"
    assert payload["build"] == {"status": "passing"}
    assert payload["tests"] == {"passed": 42, "failed": 0}


# --- Source.Tree: the registered source projected ------------------------------------------------


def test_source_tree_lists_files_with_repo_branch_and_commit() -> None:
    payload = source_tree(_source(), ["src/app.py", "tests/test_app.py"], seed="Job Tracker")
    assert payload["seed"] == "Job Tracker"
    assert payload["repository"] == "job-tracker"  # the root's basename
    assert payload["branch"] == "main" and payload["commit"] == "a1b2c3d"
    assert payload["files"] == [
        {"path": "src/app.py", "kind": "file"},
        {"path": "tests/test_app.py", "kind": "file"},
    ]


def test_source_tree_omits_branch_when_there_is_no_vcs() -> None:
    no_vcs = SourceRecord(
        "s", Provenance("s"), root="/repos/plain", file_count=0, branch=None, commit=None
    )
    payload = source_tree(no_vcs, [], seed="s")
    assert "branch" not in payload and "commit" not in payload  # honest: nothing to claim


# --- Model.Schema: the extracted model projected (entity names, honest empty fields) -------------


def test_model_schema_emits_entity_names_with_empty_fields() -> None:
    payload = model_schema(_model(), seed="Job Tracker")
    assert payload["seed"] == "Job Tracker"
    assert payload["entities"] == [
        {"name": "Application", "fields": []},  # fields await a richer extractor stage, honestly
        {"name": "Tag", "fields": []},
    ]


def test_model_schema_defaults_the_seed_to_the_models_identity() -> None:
    assert model_schema(_model())["seed"] == "job-tracker"


# --- the create round-trip: a client request becomes a real Seed --------------------------------


def test_a_valid_create_request_parses() -> None:
    req = parse_seed_create({"name": "job-tracker", "kind": "Engineering", "description": " x "})
    assert req == SeedCreateRequest(name="job-tracker", kind="engineering", description="x")


@pytest.mark.parametrize(
    "frame",
    [
        ["not", "an", "object"],  # not a dict
        {"kind": "engineering"},  # no name
        {"name": "  "},  # blank name
        {"name": "ok", "kind": "spaceship"},  # unknown kind
        {"name": "ok"},  # missing kind
    ],
)
def test_a_malformed_create_request_fails_loud(frame) -> None:
    with pytest.raises(WorkspaceContractError):
        parse_seed_create(frame)


def test_create_from_request_mints_a_real_seed_and_returns_the_verdict() -> None:
    kernel = _kernel()
    verdict = create_from_request(
        kernel,
        {"name": "job-tracker", "kind": "engineering", "description": "a tracker"},
        owner="josh",
    )
    assert verdict["name"] == "job-tracker" and verdict["ok"] is True
    seed_id = str(verdict["id"])
    record = kernel.get(seed_id)  # the Seed really exists in the store now
    assert record.identity.name == "job-tracker"
    assert record.identity.purpose == "a tracker"  # description folded into purpose


def test_create_folds_kind_into_purpose_when_no_description() -> None:
    kernel = _kernel()
    verdict = create_from_request(kernel, {"name": "world-x", "kind": "game"}, owner="josh")
    record = kernel.get(str(verdict["id"]))
    assert record.identity.purpose == "game Seed"  # intent not lost though the Kernel has no kind


def test_a_malformed_create_frame_never_reaches_the_kernel() -> None:
    kernel = _kernel()
    verdict = create_from_request(kernel, {"kind": "engineering"}, owner="josh")  # no name
    assert verdict["ok"] is False and "name" in str(verdict["reason"])
    assert kernel.list_seeds() == []  # nothing was minted


def test_a_kernel_refusal_becomes_an_honest_ok_false_verdict() -> None:
    # a fixed minter forces the second create to collide on id, so the Kernel refuses; the refusal
    # is surfaced as a verdict, not a crash.
    kernel = SeedKernel(
        InMemorySeedStore(), clock=lambda: next(_CLOCK), id_minter=lambda name: "seed-fixed"
    )
    first = create_from_request(kernel, {"name": "dup", "kind": "game"}, owner="josh")
    assert first["ok"] is True
    second = create_from_request(kernel, {"name": "dup", "kind": "game"}, owner="josh")
    assert second["ok"] is False and second["reason"]  # a reason, never a crash
    assert len(kernel.list_seeds()) == 1  # only the first was minted


def test_seed_created_shapes_success_and_refusal() -> None:
    assert seed_created("s", True, seed_id="seed-1") == {"name": "s", "ok": True, "id": "seed-1"}
    assert seed_created("s", False, reason="taken") == {"name": "s", "ok": False, "reason": "taken"}


# --- the aggregate a gateway would push ---------------------------------------------------------


def test_workspace_packages_always_has_status_and_adds_the_rest_when_present() -> None:
    kernel = _kernel()
    record = _seed(kernel)
    just_status = workspace_packages(record)
    assert [p for p, _ in just_status] == [PROJECT_STATUS_PACKAGE]

    full = workspace_packages(
        record,
        source=_source(),
        files=["src/app.py"],
        model=_model(),
    )
    names = [p for p, _ in full]
    assert names == [PROJECT_STATUS_PACKAGE, SOURCE_TREE_PACKAGE, MODEL_SCHEMA_PACKAGE]
    status_payload = full[0][1]
    assert status_payload["branch"] == "main"  # the source's branch flows into the status


# --- Build.Report: a Seed's tool runs projected into a run summary --------------------------------


def test_build_report_projects_runs_into_steps_and_an_ok_verdict() -> None:
    payload = build_report([_run("lint"), _run("test", kind="test")], seed="Job Tracker")
    assert payload["seed"] == "Job Tracker"
    assert payload["ok"] is True  # every step passed
    assert payload["steps"] == [
        {"name": "lint", "status": "passed"},
        {"name": "test", "status": "passed"},
    ]
    # the seams stay empty until a stage sources them (No Vision Theater)
    assert "tests" not in payload
    assert "artifacts" not in payload


def test_build_report_is_not_ok_when_any_step_fails_or_times_out() -> None:
    failed = build_report([_run("lint"), _run("build", exit_code=1)], seed="s")
    assert failed["ok"] is False
    assert failed["steps"] == [
        {"name": "lint", "status": "passed"},
        {"name": "build", "status": "failed"},
    ]

    slow = build_report([_run("e2e", timed_out=True)], seed="s")
    assert slow["ok"] is False
    assert slow["steps"] == [{"name": "e2e", "status": "timed out"}]


def test_build_report_empty_run_log_is_not_ok() -> None:
    # nothing ran, so nothing succeeded -- an empty log is honestly not ok, with no steps.
    payload = build_report([], seed="s")
    assert payload == {"seed": "s", "ok": False, "steps": []}


def test_build_report_step_name_falls_back_so_it_is_never_dropped() -> None:
    # the client drops a nameless step; a profileless run still names itself by kind.
    payload = build_report([_run("", kind="test")], seed="s")
    assert payload["steps"] == [{"name": "test", "status": "passed"}]


def test_build_report_fills_the_test_and_artifact_seams_when_given() -> None:
    payload = build_report(
        [_run("test", kind="test")],
        seed="s",
        tests={"passed": 12, "failed": 1, "skipped": 2},
        artifacts=[{"name": "app.whl", "kind": "wheel", "bytes": 4096}],
    )
    assert payload["tests"] == {"passed": 12, "failed": 1, "skipped": 2}
    assert payload["artifacts"] == [{"name": "app.whl", "kind": "wheel", "bytes": 4096}]


def test_build_report_frames_as_gmcp() -> None:
    # the payload the gateway would push is JSON-able through the real framer.
    frame = gmcp_frame(BUILD_REPORT_PACKAGE, build_report([_run()], seed="s"))
    assert isinstance(frame, bytes)
    assert b"Build.Report" in frame


def test_workspace_packages_adds_build_report_only_when_runs_happened() -> None:
    kernel = _kernel()
    record = _seed(kernel)
    without = workspace_packages(record)
    assert BUILD_REPORT_PACKAGE not in [p for p, _ in without]

    withruns = workspace_packages(record, runs=[_run()])
    names = [p for p, _ in withruns]
    assert names == [PROJECT_STATUS_PACKAGE, BUILD_REPORT_PACKAGE]
    assert withruns[-1][1]["seed"] == record.identity.name


# --- Architecture.Map: the classification registry projected into a module map --------------------


def _modules() -> list[dict[str, object]]:
    return [
        {
            "designation": "MOD-04.001",
            "name": "accounts",
            "domain": "04",
            "function": "logins",
            "file": "kernel/world/accounts.py",
            "status": "active",
        },
        {
            "designation": "MOD-10.067",
            "name": "posture",
            "domain": "10",
            "function": "kpi scorecard",
            "file": "kernel/posture.py",
            "status": "active",
        },
        {
            "designation": "MOD-04.002",
            "name": "combat",
            "domain": "04",
        },  # sparse: some fields absent
    ]


def test_architecture_map_groups_by_domain_and_counts() -> None:
    payload = architecture_map(_modules())
    assert payload["module_count"] == 3
    assert payload["source"] == "registry/designations/modules.json"
    assert payload["domains"] == [{"domain": "04", "count": 2}, {"domain": "10", "count": 1}]


def test_architecture_map_sorts_modules_by_designation() -> None:
    payload = architecture_map(_modules())
    modules = payload["modules"]
    assert isinstance(modules, list)
    designations = [m["designation"] for m in modules]
    assert designations == ["MOD-04.001", "MOD-04.002", "MOD-10.067"]  # sorted, stable


def test_architecture_map_omits_a_field_the_record_lacks_never_invents_it() -> None:
    payload = architecture_map(_modules())
    modules = payload["modules"]
    assert isinstance(modules, list)
    sparse = next(m for m in modules if m["designation"] == "MOD-04.002")
    assert "function" not in sparse and "file" not in sparse  # absent, not a fabricated blank
    assert sparse["domain"] == "04"


def test_architecture_map_labels_the_seed_when_given() -> None:
    payload = architecture_map(_modules(), seed="Codeforge")
    assert payload["seed"] == "Codeforge"
    assert "seed" not in architecture_map(_modules())  # unlabeled when not given


def test_architecture_map_frames_as_gmcp() -> None:
    frame = gmcp_frame(ARCHITECTURE_MAP_PACKAGE, architecture_map(_modules(), seed="s"))
    assert isinstance(frame, bytes)
    assert b"Architecture.Map" in frame


def test_workspace_packages_adds_the_architecture_map_only_when_modules_given() -> None:
    kernel = _kernel()
    record = _seed(kernel)
    assert ARCHITECTURE_MAP_PACKAGE not in [p for p, _ in workspace_packages(record)]
    withmods = workspace_packages(record, modules=_modules())
    assert [p for p, _ in withmods] == [PROJECT_STATUS_PACKAGE, ARCHITECTURE_MAP_PACKAGE]


def test_load_module_designations_reads_a_registry_and_skips_non_dicts(tmp_path) -> None:
    registry = tmp_path / "modules.json"
    registry.write_text(
        json.dumps([{"designation": "MOD-01.001", "name": "x"}, "not-a-record"]), encoding="utf-8"
    )
    loaded = load_module_designations(registry)
    assert loaded == [{"designation": "MOD-01.001", "name": "x"}]  # the stray string is dropped


def test_load_module_designations_fails_loud_on_a_non_list_registry(tmp_path) -> None:
    registry = tmp_path / "bad.json"
    registry.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    with pytest.raises(SeedKernelError, match="not a JSON list"):
        load_module_designations(registry)


def test_load_the_real_registry_projects_a_map() -> None:
    # the shipped registry loads and projects (proves the default path resolves from the repo root).
    payload = architecture_map(load_module_designations())
    count = payload["module_count"]
    assert isinstance(count, int) and count > 0
    assert payload["domains"]  # at least one domain grouped
