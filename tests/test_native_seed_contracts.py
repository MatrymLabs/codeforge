"""Drift gate for the Native Seed GMCP contract examples.

Forge publishes deterministic example packages for the Master Client. These tests prove the
committed examples still match the live Forge builders and that client-to-server request fixtures
still parse through Forge's authoritative request parsers.
"""

from __future__ import annotations

from contracts import native_seed
from kernel.gmcp import gmcp_frame, read_gmcp_package, seed_hello
from kernel.seedlab import workspace_gmcp as workspace

EXPECTED_PACKAGES = {
    "Seed.Hello",
    "Seed.Profile",
    "Project.Status",
    "Source.Tree",
    "Source.Connection",
    "Model.Schema",
    "Build.Report",
    "Architecture.Map",
    "Research.Findings",
    "Form.Schema",
    "Blueprint.List",
    "Deploy.Manifest",
    "Deploy.Status",
    "Seed.Create",
    "Form.Submit",
    "Workspace.Request",
    "Seed.Created",
}


def _doc() -> dict[str, object]:
    return native_seed.build_examples()


def _packages() -> dict[str, dict[str, object]]:
    raw = _doc()["packages"]
    assert isinstance(raw, list)
    packages = {str(example["package"]): example for example in raw}
    assert len(packages) == len(raw)  # no duplicate package names hidden by the map
    return packages


def _payload(package: str) -> dict[str, object]:
    payload = _packages()[package]["payload"]
    assert isinstance(payload, dict)
    return payload


def test_committed_native_seed_examples_match_live_builders() -> None:
    committed = native_seed.EXAMPLES_PATH.read_text(encoding="utf-8")
    assert committed == native_seed.render(), (
        "native_seed.v1.examples.json is stale: run `make contracts` and commit the result"
    )


def test_committed_native_seed_registry_matches_live_metadata() -> None:
    committed = native_seed.REGISTRY_PATH.read_text(encoding="utf-8")
    assert committed == native_seed.render_registry(), (
        "native_seed.v1.registry.json is stale: run `make contracts` and commit the result"
    )


def test_native_seed_registry_covers_exactly_the_locked_package_set() -> None:
    examples = _packages()
    registry = native_seed.build_registry()
    raw = registry["packages"]
    assert isinstance(raw, list)
    metadata = {str(package["package"]): package for package in raw}
    assert len(metadata) == len(raw)
    assert set(metadata) == set(examples)
    for package_name, package in metadata.items():
        assert package["direction"] == examples[package_name]["direction"]
        assert package["status"] == examples[package_name]["status"]
        assert package["source"]
        assert package["owner"]
        assert package["schema_version"] == "1"
        assert package["classification"] == "internal"
        assert package["compatibility"] == "additive_fields_only"
        assert package["text_fallback"]


def test_native_seed_examples_cover_the_locked_package_set() -> None:
    doc = _doc()
    assert doc["contract"] == "native-seed-gmcp"
    assert doc["schema"] == 1 and doc["version"]
    assert set(_packages()) == EXPECTED_PACKAGES


def test_seed_hello_fixture_matches_the_engine_builder() -> None:
    assert _payload("Seed.Hello") == seed_hello("job-tracker", "1.0.0", profile="job-tracker@1")


def test_all_server_to_client_fixtures_frame_as_gmcp() -> None:
    for example in _packages().values():
        if example["direction"] != "server_to_client":
            continue
        package = str(example["package"])
        payload = example["payload"]
        assert read_gmcp_package(gmcp_frame(package, payload)) == (package, payload)


def test_client_to_server_seed_create_fixture_parses_authoritatively() -> None:
    request = workspace.parse_seed_create(_payload("Seed.Create"))
    assert request.name == "job-tracker"
    assert request.kind == "engineering"
    assert request.description == "a tiny tracker"


def test_client_to_server_form_submit_fixture_parses_authoritatively() -> None:
    request = workspace.parse_form_submit(_payload("Form.Submit"))
    assert request.product_type == "game"
    assert request.answers["name"] == "Arena"
    assert request.answers["pvp"] == "open"


def test_workspace_request_fixture_round_trips_as_inbound_gmcp() -> None:
    payload = _payload("Workspace.Request")
    assert payload == {"tier": "prototype"}
    assert read_gmcp_package(gmcp_frame(workspace.WORKSPACE_REQUEST_PACKAGE, payload)) == (
        "Workspace.Request",
        payload,
    )


def test_seed_created_fixture_matches_the_engine_verdict_builder() -> None:
    assert _payload("Seed.Created") == workspace.seed_created(
        "job-tracker", True, seed_id="seed-job-tracker"
    )


def test_profile_fixture_is_emitted_by_forge() -> None:
    profile = _packages()["Seed.Profile"]
    assert profile["status"] == "implemented"
    assert profile["direction"] == "server_to_client"
