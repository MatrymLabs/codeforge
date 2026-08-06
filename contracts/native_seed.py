"""Generate the Native Seed GMCP contract examples.

The Master Client and Forge already share a live GMCP surface for Native Seed mode. This module
publishes deterministic example payloads as a committed contract artifact so provider and consumer
tests can catch drift without introducing a shared runtime package.

Regenerate with `make contracts`; `tests/test_native_seed_contracts.py` fails if the committed
examples no longer match the current Forge builders.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from kernel.blueprint import from_dict as make_blueprint
from kernel.gmcp import SEED_PROTOCOL, seed_hello, seed_profile
from kernel.seed_package import compile_manifest
from kernel.seedlab import workspace_gmcp as gmcp
from kernel.seedlab.form import FormDefinition
from kernel.seedlab.kernel import InMemorySeedStore, SeedKernel
from kernel.seedlab.project_model import Provenance, SpecSource, extract_model
from kernel.seedlab.source_connector import SourceRecord
from kernel.seedlab.tool_runner import ToolRunResult

CONTRACT_VERSION = "1.0.0"
EXAMPLES_PATH = Path(__file__).resolve().parent / "native_seed.v1.examples.json"
REGISTRY_PATH = Path(__file__).resolve().parent / "native_seed.v1.registry.json"

# The JSON registry is the published metadata authority for the Native Seed package surface.
# Payload examples remain separate because they are generated from live Forge builders; this
# registry describes ownership and compatibility without making consumers depend on Forge code.
PACKAGE_REGISTRY: tuple[dict[str, str], ...] = (
    {
        "package": "Seed.Hello",
        "direction": "server_to_client",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/gmcp.py",
        "text_fallback": "The Seed connection is ready.",
    },
    {
        "package": "Seed.Profile",
        "direction": "server_to_client",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/gmcp.py",
        "text_fallback": "Seed profile information is available.",
    },
    {
        "package": "Project.Status",
        "direction": "server_to_client",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "Project status updated.",
    },
    {
        "package": "Source.Tree",
        "direction": "server_to_client",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "The source tree is available.",
    },
    {
        "package": "Source.Connection",
        "direction": "server_to_client",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "The source connection is ready.",
    },
    {
        "package": "Model.Schema",
        "direction": "server_to_client",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "The project model is available.",
    },
    {
        "package": "Build.Report",
        "direction": "server_to_client",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "The build report is available.",
    },
    {
        "package": "Architecture.Map",
        "direction": "server_to_client",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "The architecture map is available.",
    },
    {
        "package": "Research.Findings",
        "direction": "server_to_client",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "Research findings are available.",
    },
    {
        "package": "Form.Schema",
        "direction": "server_to_client",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "The Engineering Form is ready.",
    },
    {
        "package": "Blueprint.List",
        "direction": "server_to_client",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "Blueprints are available.",
    },
    {
        "package": "Deploy.Manifest",
        "direction": "server_to_client",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "The deployment manifest is available.",
    },
    {
        "package": "Deploy.Status",
        "direction": "server_to_client",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "Deployment status updated.",
    },
    {
        "package": "Seed.Create",
        "direction": "client_to_server",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "Seed creation was requested.",
    },
    {
        "package": "Form.Submit",
        "direction": "client_to_server",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "Engineering Form answers were submitted.",
    },
    {
        "package": "Workspace.Request",
        "direction": "client_to_server",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "Workspace access was requested.",
    },
    {
        "package": "Seed.Created",
        "direction": "server_to_client",
        "status": "implemented",
        "owner": "Seed Runtime",
        "source": "kernel/seedlab/workspace_gmcp.py",
        "text_fallback": "The Seed creation result is available.",
    },
)


def build_registry() -> dict[str, Any]:
    """Return the versioned metadata registry for the Native Seed package surface."""
    return {
        "contract": "native-seed-gmcp",
        "schema": 1,
        "version": CONTRACT_VERSION,
        "protocol": SEED_PROTOCOL,
        "source": "codeforge/contracts/native_seed.py",
        "classification": "internal",
        "compatibility_policy": (
            "Additive fields are allowed; breaking changes require a new major contract version "
            "and an explicit migration or rejection rule."
        ),
        "packages": [
            {
                **package,
                "schema_version": "1",
                "classification": "internal",
                "compatibility": "additive_fields_only",
            }
            for package in PACKAGE_REGISTRY
        ],
    }


def _example(
    package: str,
    direction: str,
    payload: Mapping[str, object],
    *,
    status: str = "implemented",
) -> dict[str, object]:
    """One package fixture with enough metadata to prevent direction/implementation ambiguity."""
    return {
        "package": package,
        "direction": direction,
        "status": status,
        "payload": dict(payload),
    }


def _form_definition() -> FormDefinition:
    return FormDefinition.from_dict(
        {
            "common_question_ids": ["name", "owner", "purpose"],
            "questions": {
                "name": {"prompt": "What is this Seed called?", "kind": "text"},
                "owner": {"prompt": "Who owns it (account)?", "kind": "text"},
                "purpose": {"prompt": "In one line, what is it for?", "kind": "text"},
                "world_scale": {
                    "prompt": "World scale?",
                    "kind": "choice",
                    "choices": ["small", "large"],
                },
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
                "tool": {
                    "name": "Engineering tool",
                    "description": "a small software tool",
                    "question_ids": [],
                    "domain_modules": ["engineering"],
                },
            },
        }
    )


def _seed_profile() -> dict[str, object]:
    """The deterministic contract example built through Forge's profile emitter."""
    return seed_profile(
        "job-tracker",
        "Job Tracker",
        "Matrym Labs",
        "1.0.0",
        theme="forge",
        terminology={"seed": "workspace"},
        panels=[
            {
                "name": "Project Hub",
                "binding": "Project.Status.seed",
                "fallback": "Project status and lifecycle phase.",
            },
            {
                "name": "Source Workspace",
                "binding": "Source.Tree.files",
                "fallback": "Repository files exposed by the Seed.",
            },
            {
                "name": "Build Report",
                "binding": "Build.Report.steps",
                "fallback": "Build and test run summary.",
            },
        ],
        accessibility=["screen_reader"],
    )


def _source() -> SourceRecord:
    return SourceRecord(
        source_id="src-job-tracker",
        provenance=Provenance("src-job-tracker", owner="josh", visibility="private"),
        root="/home/josh/projects/job-tracker",
        file_count=2,
        branch="main",
        commit="a1b2c3d",
    )


def _model():
    return extract_model(
        SpecSource(
            {"identity": "job-tracker", "entities": ["Application", "Task"]},
            Provenance("job-tracker", owner="josh"),
        )
    )


def _runs() -> list[ToolRunResult]:
    return [
        ToolRunResult(
            seed_id="seed-job-tracker",
            kind="build",
            profile="lint",
            argv=["make", "lint"],
            exit_code=0,
            output="",
            duration=0.1,
            timed_out=False,
            cwd="/srv/job-tracker",
            when="2026-08-04T12:00:00+00:00",
        ),
        ToolRunResult(
            seed_id="seed-job-tracker",
            kind="test",
            profile="test",
            argv=["make", "test"],
            exit_code=0,
            output="",
            duration=0.2,
            timed_out=False,
            cwd="/srv/job-tracker",
            when="2026-08-04T12:00:01+00:00",
        ),
    ]


def _modules() -> list[dict[str, object]]:
    return [
        {
            "designation": "MOD-01.001",
            "name": "seedlab",
            "domain": "01",
            "function": "Seed lifecycle and workspace projection.",
            "file": "kernel/seedlab/kernel.py",
            "status": "prototype",
        },
        {
            "designation": "MOD-02.001",
            "name": "workspace_gmcp",
            "domain": "02",
            "function": "Native Seed GMCP package projection.",
            "file": "kernel/seedlab/workspace_gmcp.py",
            "status": "active",
        },
    ]


def _findings() -> list[dict[str, object]]:
    return [
        {
            "id": "EXP-05",
            "title": "Source model extraction",
            "question": "Can a Seed expose a small project model to the client?",
            "status": "complete",
            "verdict": "prototype proven",
            "source": "kernel/seedlab/source_modeler.py",
            "evidence": "tests/test_source_modeler.py",
            "summary": "A small source tree can become a persisted project model.",
        }
    ]


def _blueprints() -> list:
    return [
        make_blueprint(
            {
                "blueprint_id": "artifact_registry",
                "title": "Artifact Registry",
                "intent": "Record produced target artifacts with provenance.",
                "requirements": ["Artifact identity is stable.", "Source and run evidence link."],
                "security": ["Only the Seed runtime may register artifacts."],
                "tasks": ["Define the record.", "Persist the registry.", "Expose a report."],
                "stack": {"runtime": "CodeForge SeedLab", "tests": "pytest"},
                "status": "draft",
            }
        )
    ]


def build_examples() -> dict[str, Any]:
    """The Native Seed GMCP contract examples as one deterministic JSON document."""
    clock = iter(f"2026-08-04T12:00:{n:02d}+00:00" for n in range(10))
    kernel = SeedKernel(InMemorySeedStore(), clock=lambda: next(clock))
    record = kernel.create_seed(
        "job-tracker",
        "josh",
        "a tiny tracker",
        seed_id="seed-job-tracker",
        product_type="tool",
        domain_modules=("engineering",),
    )
    source = _source()
    form_def = _form_definition()
    form_submit: dict[str, object] = {
        "product_type": "game",
        "answers": {
            "name": "Arena",
            "owner": "josh",
            "purpose": "a pvp test world",
            "world_scale": "small",
            "combat": True,
            "pvp": "open",
        },
    }

    return {
        "contract": "native-seed-gmcp",
        "schema": 1,
        "version": CONTRACT_VERSION,
        "protocol": SEED_PROTOCOL,
        "source": "codeforge kernel/gmcp.py + kernel/seedlab/workspace_gmcp.py",
        "packages": [
            _example(
                "Seed.Hello",
                "server_to_client",
                seed_hello("job-tracker", "1.0.0", profile="job-tracker@1"),
            ),
            _example(
                "Seed.Profile",
                "server_to_client",
                _seed_profile(),
            ),
            _example(
                gmcp.PROJECT_STATUS_PACKAGE,
                "server_to_client",
                gmcp.project_status(
                    record,
                    branch="main",
                    build="passing",
                    tests={"passed": 2, "failed": 0},
                ),
            ),
            _example(
                gmcp.SOURCE_TREE_PACKAGE,
                "server_to_client",
                gmcp.source_tree(source, ["src/app.py", "tests/test_app.py"], seed="job-tracker"),
            ),
            _example(
                gmcp.SOURCE_CONNECTION_PACKAGE,
                "server_to_client",
                gmcp.source_connection_package(source, seed="job-tracker"),
            ),
            _example(gmcp.MODEL_SCHEMA_PACKAGE, "server_to_client", gmcp.model_schema(_model())),
            _example(
                gmcp.BUILD_REPORT_PACKAGE,
                "server_to_client",
                gmcp.build_report(
                    _runs(),
                    seed="job-tracker",
                    tests={"passed": 2, "failed": 0, "skipped": 0},
                    artifacts=[{"name": "job-tracker.tar.gz", "kind": "archive", "bytes": 4096}],
                ),
            ),
            _example(
                gmcp.ARCHITECTURE_MAP_PACKAGE,
                "server_to_client",
                gmcp.architecture_map(_modules(), seed="job-tracker"),
            ),
            _example(
                gmcp.RESEARCH_FINDINGS_PACKAGE,
                "server_to_client",
                gmcp.research_findings(_findings(), seed="job-tracker"),
            ),
            _example(
                gmcp.FORM_SCHEMA_PACKAGE,
                "server_to_client",
                gmcp.form_schema(form_def, seed="job-tracker"),
            ),
            _example(
                gmcp.BLUEPRINT_LIST_PACKAGE,
                "server_to_client",
                gmcp.blueprint_list(_blueprints(), seed="job-tracker"),
            ),
            _example(
                gmcp.DEPLOY_MANIFEST_PACKAGE,
                "server_to_client",
                gmcp.deploy_manifest(
                    compile_manifest("job-tracker", "prototype"), seed="job-tracker"
                ),
            ),
            _example(
                gmcp.DEPLOY_STATUS_PACKAGE,
                "server_to_client",
                gmcp.deploy_status(
                    version="0.1.0",
                    seed="job-tracker",
                    uptime_seconds=90,
                    connections=1,
                    max_connections=64,
                    tls=True,
                ),
            ),
            _example(
                gmcp.SEED_CREATE_PACKAGE,
                "client_to_server",
                {
                    "name": "job-tracker",
                    "kind": "engineering",
                    "description": "a tiny tracker",
                },
            ),
            _example(
                gmcp.FORM_SUBMIT_PACKAGE,
                "client_to_server",
                form_submit,
            ),
            _example(
                gmcp.WORKSPACE_REQUEST_PACKAGE,
                "client_to_server",
                {"tier": "prototype"},
            ),
            _example(
                gmcp.SEED_CREATED_PACKAGE,
                "server_to_client",
                gmcp.seed_created("job-tracker", True, seed_id="seed-job-tracker"),
            ),
        ],
    }


def render() -> str:
    """The committed fixture text: pretty JSON plus a trailing newline."""
    return json.dumps(build_examples(), indent=2) + "\n"


def render_registry() -> str:
    """The committed registry text: pretty JSON plus a trailing newline."""
    return json.dumps(build_registry(), indent=2) + "\n"


def write() -> Path:
    EXAMPLES_PATH.write_text(render(), encoding="utf-8")
    REGISTRY_PATH.write_text(render_registry(), encoding="utf-8")
    return EXAMPLES_PATH


if __name__ == "__main__":
    path = write()
    print(f"wrote {path}")
