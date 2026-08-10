"""Provider fixture check for the Native Seed GMCP contract examples."""

from __future__ import annotations

import json
from pathlib import Path

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
    SEED_CREATE_PACKAGE,
    SEED_CREATED_PACKAGE,
    SOURCE_CONNECTION_PACKAGE,
    SOURCE_TREE_PACKAGE,
    WORKSPACE_REQUEST_PACKAGE,
)

FIXTURE = Path(__file__).resolve().parents[1] / "contracts" / "native_seed.v1.examples.json"

EXPECTED_PACKAGES = {
    "Seed.Hello",
    "Seed.Profile",
    PROJECT_STATUS_PACKAGE,
    SOURCE_TREE_PACKAGE,
    SOURCE_CONNECTION_PACKAGE,
    MODEL_SCHEMA_PACKAGE,
    BUILD_REPORT_PACKAGE,
    ARCHITECTURE_MAP_PACKAGE,
    RESEARCH_FINDINGS_PACKAGE,
    FORM_SCHEMA_PACKAGE,
    BLUEPRINT_LIST_PACKAGE,
    DEPLOY_MANIFEST_PACKAGE,
    DEPLOY_STATUS_PACKAGE,
    SEED_CREATE_PACKAGE,
    FORM_SUBMIT_PACKAGE,
    WORKSPACE_REQUEST_PACKAGE,
    SEED_CREATED_PACKAGE,
}


def _packages() -> dict[str, dict[str, object]]:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw = doc["packages"]
    assert isinstance(raw, list)
    packages = {str(example["package"]): example for example in raw}
    assert len(packages) == len(raw)
    return packages


def test_native_seed_fixture_locks_the_provider_package_set() -> None:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert doc["contract"] == "native-seed-gmcp"
    assert doc["schema"] == 1
    assert doc["version"] == "1.0.0"
    assert set(_packages()) == EXPECTED_PACKAGES


def test_source_connection_fixture_names_the_engine_package() -> None:
    payload = _packages()[SOURCE_CONNECTION_PACKAGE]["payload"]
    assert isinstance(payload, dict)
    assert payload["source_id"] == "job-tracker-src"
    assert payload["owner"] == "seed-owner"
    assert payload["visibility"] == "private"
