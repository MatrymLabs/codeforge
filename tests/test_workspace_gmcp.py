"""Test twin for kernel/seedlab/workspace_gmcp.py -- the engine speaking the client's workspace
GMCP contracts.

Acceptance: each builder projects a seedlab record into the exact package shape the Master Client
parses (Project.Status, Source.Tree, Source.Connection, Model.Schema, Build.Report), and a
Seed.Create request mints a real Seed and returns a Seed.Created verdict. Refusal (fail loud /
honest): a malformed create frame never reaches the Kernel and becomes an ok:false verdict; a
duplicate name is refused with a reason; the engine emits only what it models (empty entity fields;
Build.Report carries real run steps and optional test/artifact seams, never fabricated evidence).
"""

from __future__ import annotations

import json

import pytest

from kernel.blueprint import from_dict as make_blueprint
from kernel.gmcp import gmcp_frame
from kernel.seed_package import compile_manifest
from kernel.seedlab.form import FormDefinition
from kernel.seedlab.kernel import BlueprintKernel, BlueprintKernelError, InMemorySeedStore
from kernel.seedlab.project_model import Provenance, SpecSource, extract_model
from kernel.seedlab.source_connector import SourceRecord
from kernel.seedlab.tool_runner import ToolRunResult
from kernel.seedlab.workspace_gmcp import (
    ARCHITECTURE_MAP_PACKAGE,
    BLUEPRINT_LIST_PACKAGE,
    BUILD_REPORT_PACKAGE,
    DEPLOY_MANIFEST_PACKAGE,
    DEPLOY_STATUS_PACKAGE,
    FORM_SCHEMA_PACKAGE,
    FORM_SUBMIT_PACKAGE,
    MODEL_SCHEMA_PACKAGE,
    PROJECT_STATUS_PACKAGE,
    RESEARCH_FINDINGS_PACKAGE,
    SOURCE_CONNECTION_PACKAGE,
    SOURCE_TREE_PACKAGE,
    SeedCreateRequest,
    WorkspaceContractError,
    architecture_map,
    blueprint_list,
    build_report,
    create_from_form_submit,
    create_from_request,
    deploy_manifest,
    deploy_status,
    form_schema,
    load_module_designations,
    load_research_findings,
    model_schema,
    parse_form_submit,
    parse_seed_create,
    project_status,
    research_findings,
    seed_created,
    source_connection_package,
    source_tree,
    summarize_test_runs,
    workspace_packages,
)

_CLOCK = iter(f"2026-08-01T00:00:{n:02d}+00:00" for n in range(120))


def _kernel() -> BlueprintKernel:
    return BlueprintKernel(InMemorySeedStore(), clock=lambda: next(_CLOCK))


def _seed(kernel: BlueprintKernel, name: str = "Job Tracker", sid: str = "seed-jt"):
    return kernel.create_seed(name, "seed-owner", "a tiny tracker", seed_id=sid)


def _source() -> SourceRecord:
    return SourceRecord(
        source_id="demo-src",
        provenance=Provenance("demo-src", owner="seed-owner", visibility="private"),
        root="/srv/seeds/job-tracker",
        file_count=2,
        branch="main",
        commit="a1b2c3d",
    )


def _model():
    spec = SpecSource(
        {"identity": "job-tracker", "entities": ["Application", "Tag"]},
        Provenance("job-tracker", owner="seed-owner"),
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
        owner="seed-owner",
    )
    assert verdict["name"] == "job-tracker" and verdict["ok"] is True
    seed_id = str(verdict["id"])
    record = kernel.get(seed_id)  # the Seed really exists in the store now
    assert record.identity.name == "job-tracker"
    assert record.identity.purpose == "a tracker"  # description folded into purpose


def test_create_folds_kind_into_purpose_when_no_description() -> None:
    kernel = _kernel()
    verdict = create_from_request(kernel, {"name": "world-x", "kind": "game"}, owner="seed-owner")
    record = kernel.get(str(verdict["id"]))
    assert record.identity.purpose == "game Seed"  # intent not lost though the Kernel has no kind


def test_a_malformed_create_frame_never_reaches_the_kernel() -> None:
    kernel = _kernel()
    verdict = create_from_request(kernel, {"kind": "engineering"}, owner="seed-owner")  # no name
    assert verdict["ok"] is False and "name" in str(verdict["reason"])
    assert kernel.list_seeds() == []  # nothing was minted


def test_a_kernel_refusal_becomes_an_honest_ok_false_verdict() -> None:
    # a fixed minter forces the second create to collide on id, so the Kernel refuses; the refusal
    # is surfaced as a verdict, not a crash.
    kernel = BlueprintKernel(
        InMemorySeedStore(), clock=lambda: next(_CLOCK), id_minter=lambda name: "seed-fixed"
    )
    first = create_from_request(kernel, {"name": "dup", "kind": "game"}, owner="seed-owner")
    assert first["ok"] is True
    second = create_from_request(kernel, {"name": "dup", "kind": "game"}, owner="seed-owner")
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
    assert names == [
        PROJECT_STATUS_PACKAGE,
        SOURCE_TREE_PACKAGE,
        SOURCE_CONNECTION_PACKAGE,
        MODEL_SCHEMA_PACKAGE,
    ]
    status_payload = full[0][1]
    assert status_payload["branch"] == "main"  # the source's branch flows into the status


def test_source_connection_projects_the_registered_connector() -> None:
    payload = source_connection_package(_source(), seed="Job Tracker")
    assert payload["seed"] == "Job Tracker"
    assert payload["source_id"] == "demo-src"
    assert payload["owner"] == "seed-owner"
    assert payload["visibility"] == "private"


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


def test_summarize_test_runs_collapses_test_outcomes() -> None:
    summary = summarize_test_runs([_run(kind="test"), _run(kind="test", exit_code=1)])
    assert summary == {"passed": 1, "failed": 1, "skipped": 0}


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

    withruns = workspace_packages(record, runs=[_run(kind="test")])
    names = [p for p, _ in withruns]
    assert names == [PROJECT_STATUS_PACKAGE, BUILD_REPORT_PACKAGE]
    assert withruns[-1][1]["seed"] == record.identity.name
    assert withruns[-1][1]["tests"] == {"passed": 1, "failed": 0, "skipped": 0}


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
    with pytest.raises(BlueprintKernelError, match="not a JSON list"):
        load_module_designations(registry)


def test_load_the_real_registry_projects_a_map() -> None:
    # the shipped registry loads and projects (proves the default path resolves from the repo root).
    payload = architecture_map(load_module_designations())
    count = payload["module_count"]
    assert isinstance(count, int) and count > 0
    assert payload["domains"]  # at least one domain grouped


# --- Research.Findings: the R&D Factory + FGL provenance projected into a finding list ------------


def _findings() -> list[dict[str, object]]:
    return [
        {
            "id": "EXP-05",
            "title": "FTS5 world search",
            "question": "Does an FTS5 index beat a linear room scan at scale?",
            "status": "complete",
            "verdict": "verified improvement",
            "source": "rd/labs/algorithms",
            "evidence": "rd/evidence/EXP-05/benchmark.json",
            "summary": "80-129x faster world search",
        },
        {
            "id": "EXP-31",
            "title": "Probabilistic structures",
            "verdict": "hardware store part",
        },  # sparse: some fields absent
        {
            "id": "EXP-24",
            "verdict": "verified improvement",
        },
    ]


def test_research_findings_groups_by_verdict_and_counts() -> None:
    payload = research_findings(_findings())
    assert payload["finding_count"] == 3
    assert payload["verdicts"] == [
        {"verdict": "hardware store part", "count": 1},
        {"verdict": "verified improvement", "count": 2},
    ]


def test_research_findings_sorts_by_id() -> None:
    payload = research_findings(_findings())
    findings = payload["findings"]
    assert isinstance(findings, list)
    assert [f["id"] for f in findings] == ["EXP-05", "EXP-24", "EXP-31"]  # sorted, stable


def test_research_findings_omits_a_field_the_record_lacks_never_invents_it() -> None:
    payload = research_findings(_findings())
    findings = payload["findings"]
    assert isinstance(findings, list)
    sparse = next(f for f in findings if f["id"] == "EXP-31")
    assert "question" not in sparse and "evidence" not in sparse  # absent, not a fabricated blank
    assert sparse["verdict"] == "hardware store part"


def test_research_findings_labels_the_seed_when_given() -> None:
    payload = research_findings(_findings(), seed="Aethryn")
    assert payload["seed"] == "Aethryn"
    assert "seed" not in research_findings(_findings())  # unlabeled when not given


def test_research_findings_empty_surface_is_honest() -> None:
    payload = research_findings([])
    assert payload["finding_count"] == 0
    assert payload["verdicts"] == [] and payload["findings"] == []


def test_research_findings_frames_as_gmcp() -> None:
    frame = gmcp_frame(RESEARCH_FINDINGS_PACKAGE, research_findings(_findings(), seed="s"))
    assert isinstance(frame, bytes)
    assert b"Research.Findings" in frame


def test_workspace_packages_adds_research_only_when_findings_given() -> None:
    kernel = _kernel()
    record = _seed(kernel)
    assert RESEARCH_FINDINGS_PACKAGE not in [p for p, _ in workspace_packages(record)]
    withresearch = workspace_packages(record, findings=_findings())
    assert [p for p, _ in withresearch] == [PROJECT_STATUS_PACKAGE, RESEARCH_FINDINGS_PACKAGE]


def test_load_research_findings_reads_a_manifest_and_skips_non_dicts(tmp_path) -> None:
    manifest = tmp_path / "experiments.json"
    manifest.write_text(
        json.dumps([{"id": "EXP-01", "verdict": "neutral"}, "not-a-record"]), encoding="utf-8"
    )
    loaded = load_research_findings(manifest)
    assert loaded == [{"id": "EXP-01", "verdict": "neutral"}]  # the stray string is dropped


def test_load_research_findings_fails_loud_on_a_non_list_manifest(tmp_path) -> None:
    manifest = tmp_path / "bad.json"
    manifest.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    with pytest.raises(BlueprintKernelError, match="not a JSON list"):
        load_research_findings(manifest)


# --- Form.Schema + Form.Submit: the Seed Creation Wizard (CR-0002) -------------------------------

_FORM_CATALOG = {
    "common_question_ids": ["name", "owner", "purpose"],
    "questions": {
        "name": {"prompt": "What is this Seed called?", "kind": "text"},
        "owner": {"prompt": "Who owns it (account)?", "kind": "text"},
        "purpose": {"prompt": "In one line, what is it for?", "kind": "text"},
        "world_scale": {"prompt": "World scale?", "kind": "choice", "choices": ["small", "large"]},
        "combat": {"prompt": "Does it have combat?", "kind": "bool"},
        "pvp": {
            "prompt": "PvP ruleset?",
            "kind": "choice",
            "choices": ["none", "open"],
            "applies_when": {"combat": True},
        },
    },
    "product_types": {
        "game": {
            "name": "Game world",
            "description": "a playable world",
            "question_ids": ["world_scale", "combat", "pvp"],
            "domain_modules": ["game", "economy"],
        },
        "education": {
            "name": "Education",
            "description": "a classroom",
            "question_ids": ["world_scale"],
            "domain_modules": ["education"],
        },
    },
}


def _form_def() -> FormDefinition:
    return FormDefinition.from_dict(_FORM_CATALOG)


def test_form_schema_projects_the_catalog() -> None:
    payload = form_schema(_form_def())
    assert payload["schema"] == 1  # the Form's real wire version, so a client reads it knowingly
    assert payload["common_question_ids"] == ["name", "owner", "purpose"]
    questions = payload["questions"]
    assert isinstance(questions, dict)
    assert set(questions) == {"name", "owner", "purpose", "world_scale", "combat", "pvp"}
    types = payload["product_types"]
    assert isinstance(types, list)
    assert [pt["id"] for pt in types] == ["game", "education"]  # catalog order preserved
    game = next(pt for pt in types if pt["id"] == "game")
    assert game["domain_modules"] == ["game", "economy"] and game["name"] == "Game world"


def test_form_schema_question_carries_choices_and_applies_when() -> None:
    questions = form_schema(_form_def())["questions"]
    assert isinstance(questions, dict)
    pvp = questions["pvp"]
    assert pvp["kind"] == "choice" and pvp["choices"] == ["none", "open"]
    assert pvp["applies_when"] == {"combat": True}  # an object the client reads as a branch trigger
    assert pvp["required"] is True


def test_form_schema_omits_choices_and_applies_when_for_a_plain_text_question() -> None:
    questions = form_schema(_form_def())["questions"]
    assert isinstance(questions, dict)
    name = questions["name"]
    assert name["kind"] == "text"
    assert "choices" not in name and "applies_when" not in name  # absent, not a fabricated blank


def test_form_schema_labels_the_seed_when_given() -> None:
    assert form_schema(_form_def(), seed="codeforge")["seed"] == "codeforge"
    assert "seed" not in form_schema(_form_def())  # unlabeled when not given


def test_form_schema_frames_as_gmcp() -> None:
    frame = gmcp_frame(FORM_SCHEMA_PACKAGE, form_schema(_form_def(), seed="s"))
    assert isinstance(frame, bytes)
    assert b"Form.Schema" in frame
    assert FORM_SUBMIT_PACKAGE == "Form.Submit"  # the client -> engine reply direction's name


def test_form_schema_projection_matches_the_engine_form() -> None:
    # The projected question_ids of every product type must resolve in the projected question bank,
    # so the client renders exactly the set the engine's own EngineeringForm would walk.
    definition = _form_def()
    payload = form_schema(definition)
    questions = payload["questions"]
    types = payload["product_types"]
    assert isinstance(questions, dict) and isinstance(types, list)
    common = payload["common_question_ids"]
    assert isinstance(common, list)
    for pt in types:
        for qid in [*common, *pt["question_ids"]]:
            assert qid in questions  # no dangling reference the client could not render


# --- the submit round-trip ---


def test_parse_form_submit_validates_a_good_frame() -> None:
    request = parse_form_submit({"product_type": "game", "answers": {"name": "arena"}})
    assert request.product_type == "game" and request.answers == {"name": "arena"}


def test_parse_form_submit_allows_an_empty_answers_map() -> None:
    # the Form re-validates and fails on a missing required answer; an empty map is a valid SHAPE
    assert parse_form_submit({"product_type": "game"}).answers == {}


@pytest.mark.parametrize(
    "bad",
    [
        ["not", "an", "object"],
        {"answers": {"name": "x"}},  # no product_type
        {"product_type": "  "},  # blank product_type
        {"product_type": "game", "answers": ["not", "a", "map"]},  # answers not an object
    ],
)
def test_parse_form_submit_fails_loud_on_a_malformed_frame(bad) -> None:
    with pytest.raises(WorkspaceContractError):
        parse_form_submit(bad)


def _game_answers() -> dict[str, object]:
    return {
        "name": "Arena",
        "purpose": "a pvp world",
        "world_scale": "large",
        "combat": True,
        "pvp": "open",
    }


def test_create_from_form_submit_mints_a_seed_with_the_forms_verdict() -> None:
    kernel = _kernel()
    verdict = create_from_form_submit(
        kernel,
        _form_def(),
        {"product_type": "game", "answers": _game_answers()},
        owner="seed-owner",
    )
    assert verdict["ok"] is True and verdict["name"] == "Arena"
    record = kernel.get(str(verdict["id"]))
    assert record.identity.product_type == "game"
    assert record.identity.domain_modules == ("game", "economy")  # the Form's selection lands


def test_create_from_form_submit_overrides_owner_with_the_authenticated_account() -> None:
    kernel = _kernel()
    # a client cannot mint under another account by typing a name in the owner box
    answers = {**_game_answers(), "owner": "someone_else"}
    verdict = create_from_form_submit(
        kernel, _form_def(), {"product_type": "game", "answers": answers}, owner="seed-owner"
    )
    assert verdict["ok"] is True
    assert kernel.get(str(verdict["id"])).identity.owner == "seed-owner"  # authenticated owner wins


def test_create_from_form_submit_refuses_a_missing_required_answer() -> None:
    kernel = _kernel()
    partial = {"name": "Arena", "purpose": "p"}  # no world_scale/combat -> Form fails loud
    verdict = create_from_form_submit(
        kernel, _form_def(), {"product_type": "game", "answers": partial}, owner="seed-owner"
    )
    assert verdict["ok"] is False and "required" in str(verdict["reason"])
    assert verdict["name"] == "Arena"  # the honest verdict still names what was attempted


def test_create_from_form_submit_refuses_a_malformed_frame() -> None:
    kernel = _kernel()
    verdict = create_from_form_submit(kernel, _form_def(), "not-an-object", owner="seed-owner")
    assert verdict["ok"] is False and "object" in str(verdict["reason"])


def test_create_from_form_submit_refuses_an_out_of_range_choice() -> None:
    kernel = _kernel()
    answers = {**_game_answers(), "world_scale": "galactic"}  # not a choice
    verdict = create_from_form_submit(
        kernel, _form_def(), {"product_type": "game", "answers": answers}, owner="seed-owner"
    )
    assert verdict["ok"] is False and "world_scale" in str(verdict["reason"])


def test_create_from_form_submit_refuses_a_duplicate_name() -> None:
    # a fixed minter forces both submits onto one id, so the Kernel refuses the second, honestly
    kernel = BlueprintKernel(
        InMemorySeedStore(), clock=lambda: next(_CLOCK), id_minter=lambda name: "seed-dupe"
    )
    frame = {"product_type": "game", "answers": _game_answers()}
    first = create_from_form_submit(kernel, _form_def(), frame, owner="seed-owner")
    assert first["ok"] is True
    second = create_from_form_submit(kernel, _form_def(), frame, owner="seed-owner")
    assert second["ok"] is False and "already exists" in str(second["reason"])


# --- Blueprint.List: filed Blueprints -> the client's Blueprint Panel (CR-0003) ------------------


def _blueprints() -> list:
    return [
        make_blueprint(
            {
                "blueprint_id": "zone_scheduler",
                "title": "Zone Scheduler",
                "intent": "Reset zones on a cadence.",
                "requirements": ["Deterministic order.", "Idempotent resets."],
                "security": ["Threat: a runaway reset loop.", "Authz: owner-only trigger."],
                "tasks": ["Model the schedule.", "Wire the tick."],
                "stack": {"engine": "custom Python", "tests": "pytest"},
                "status": "validated",
            }
        ),
        make_blueprint(
            {
                "blueprint_id": "arc",
                "title": "ARC",
                "intent": "Compose the readiness gates.",
                "requirements": ["Each gate is independent."],
                "security": ["Trust boundary: the gate inputs."],
                "status": "draft",  # tasks/stack omitted -> default empty, honestly
            }
        ),
    ]


def test_blueprint_list_projects_the_canonical_records() -> None:
    payload = blueprint_list(_blueprints())
    assert payload["blueprint_count"] == 2
    blueprints = payload["blueprints"]
    assert isinstance(blueprints, list)
    arc = next(b for b in blueprints if b["blueprint_id"] == "arc")
    assert arc["title"] == "ARC" and arc["status"] == "draft"
    assert arc["requirements"] == ["Each gate is independent."]
    assert arc["tasks"] == [] and arc["stack"] == {}  # omitted -> empty, never invented


def test_blueprint_list_groups_by_status_and_counts() -> None:
    payload = blueprint_list(_blueprints())
    assert payload["statuses"] == [
        {"status": "draft", "count": 1},
        {"status": "validated", "count": 1},
    ]


def test_blueprint_list_sorts_by_id() -> None:
    payload = blueprint_list(_blueprints())
    blueprints = payload["blueprints"]
    assert isinstance(blueprints, list)
    assert [b["blueprint_id"] for b in blueprints] == ["arc", "zone_scheduler"]  # sorted, stable


def test_blueprint_list_projects_only_real_fields_no_compile_progress() -> None:
    # A Blueprint is a static validated spec: the projection must carry ONLY its authored fields,
    # never a fabricated "compile progress" / phase / steps-executed the engine does not track.
    payload = blueprint_list(_blueprints())
    blueprints = payload["blueprints"]
    assert isinstance(blueprints, list)
    assert set(blueprints[0]) == {
        "blueprint_id",
        "title",
        "intent",
        "requirements",
        "security",
        "tasks",
        "stack",
        "status",
    }


def test_blueprint_list_labels_the_seed_when_given() -> None:
    assert blueprint_list(_blueprints(), seed="Aethryn")["seed"] == "Aethryn"
    assert "seed" not in blueprint_list(_blueprints())  # unlabeled when not given


def test_blueprint_list_empty_is_honest() -> None:
    payload = blueprint_list([])
    assert payload["blueprint_count"] == 0
    assert payload["statuses"] == [] and payload["blueprints"] == []


def test_blueprint_list_frames_as_gmcp() -> None:
    frame = gmcp_frame(BLUEPRINT_LIST_PACKAGE, blueprint_list(_blueprints(), seed="s"))
    assert isinstance(frame, bytes)
    assert b"Blueprint.List" in frame


def test_workspace_packages_adds_blueprints_only_when_given() -> None:
    kernel = _kernel()
    record = _seed(kernel)
    assert BLUEPRINT_LIST_PACKAGE not in [p for p, _ in workspace_packages(record)]
    withbp = workspace_packages(record, blueprints=_blueprints())
    assert [p for p, _ in withbp] == [PROJECT_STATUS_PACKAGE, BLUEPRINT_LIST_PACKAGE]


# --- Deploy.Manifest: the sizing manifest -> the client's Deployment Panel (CR-0004) --------------


def test_deploy_manifest_projects_the_real_sizing():
    manifest = compile_manifest("Aethryn", "prototype")
    payload = deploy_manifest(manifest)
    assert payload["project"] == "Aethryn"
    assert payload["tier_id"] == "prototype" and payload["tier_name"] == "Prototype"
    assert isinstance(payload["hardware"], str) and payload["hardware"]  # the honest hardware read
    sizing = payload["sizing"]
    assert isinstance(sizing, dict)
    assert sizing["target_players"] == 500 and sizing["rooms"] > 0  # real derived counts
    assert isinstance(sizing["storage_human"], str)  # the human storage string, for the panel


def test_deploy_manifest_carries_only_the_real_manifest_fields():
    # No Vision Theater: the projection is the manifest's own derived fields, never an invented
    # "deploy status" / "url" / "health" the engine lacks (this is sizing, not a live deploy).
    payload = deploy_manifest(compile_manifest("Aethryn", "prototype"))
    assert set(payload) == {"schema", "project", "tier_id", "tier_name", "hardware", "sizing"}
    sizing = payload["sizing"]
    assert isinstance(sizing, dict)
    assert set(sizing) == {
        "target_players",
        "rooms",
        "zones",
        "regions",
        "settlements",
        "dungeons",
        "bosses",
        "npcs",
        "monsters",
        "quests",
        "crafting_recipes",
        "storage_bytes",
        "storage_human",
    }


def test_deploy_manifest_labels_the_seed_when_given():
    manifest = compile_manifest("Aethryn", "prototype")
    assert deploy_manifest(manifest, seed="Aethryn")["seed"] == "Aethryn"
    assert "seed" not in deploy_manifest(manifest)  # unlabeled when not given


def test_deploy_manifest_frames_as_gmcp():
    frame = gmcp_frame(DEPLOY_MANIFEST_PACKAGE, deploy_manifest(compile_manifest("s", "prototype")))
    assert isinstance(frame, bytes)
    assert b"Deploy.Manifest" in frame


def test_workspace_packages_adds_the_manifest_only_when_given():
    kernel = _kernel()
    record = _seed(kernel)
    assert DEPLOY_MANIFEST_PACKAGE not in [p for p, _ in workspace_packages(record)]
    withdeploy = workspace_packages(record, manifest=compile_manifest("s", "prototype"))
    assert [p for p, _ in withdeploy] == [PROJECT_STATUS_PACKAGE, DEPLOY_MANIFEST_PACKAGE]


# --- Deploy.Status: the running instance's own live status (7b, no cloud) -------------------------


def test_deploy_status_reports_the_instances_own_facts():
    payload = deploy_status(
        version="0.1.0",
        seed="first-forge",
        uptime_seconds=125.7,
        connections=3,
        max_connections=128,
        tls=True,
    )
    assert payload["version"] == "0.1.0" and payload["seed"] == "first-forge"
    assert payload["uptime_seconds"] == 125  # floored to whole seconds
    assert payload["connections"] == {"current": 3, "max": 128}
    assert payload["tls"] is True


def test_deploy_status_never_reports_a_negative_uptime():
    # a monotonic hiccup or a zero start must never surface a negative uptime
    payload = deploy_status(
        version="v",
        seed="s",
        uptime_seconds=-4.0,
        connections=0,
        max_connections=1,
        tls=False,
    )
    assert payload["uptime_seconds"] == 0


def test_deploy_status_carries_only_real_instance_facts():
    # No Vision Theater: an instance self-report, never a fabricated cloud URL / region / health.
    payload = deploy_status(
        version="v",
        seed="s",
        uptime_seconds=1.0,
        connections=0,
        max_connections=1,
        tls=False,
    )
    assert set(payload) == {"version", "seed", "uptime_seconds", "connections", "tls"}


def test_deploy_status_frames_as_gmcp():
    frame = gmcp_frame(
        DEPLOY_STATUS_PACKAGE,
        deploy_status(
            version="v", seed="s", uptime_seconds=1.0, connections=0, max_connections=1, tls=False
        ),
    )
    assert isinstance(frame, bytes) and b"Deploy.Status" in frame
