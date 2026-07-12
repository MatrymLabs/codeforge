"""Test twin for parts/manifest.py -- the typed Part Manifest."""

import pytest

from parts.manifest import ManifestError, PartManifest, find_manifest, from_dict, to_dict, to_markdown


def _valid_raw():
    return {
        "part_id": "test-part",
        "name": "Test Part",
        "version": "0.1",
        "maturity": "beta",
        "purpose": "A test part for the test suite.",
        "source": "parts/test.py",
        "domain": "testing",
    }


def test_from_dict_creates_a_valid_manifest():
    m = from_dict(_valid_raw())
    assert isinstance(m, PartManifest)
    assert m.part_id == "test-part"
    assert m.maturity == "beta"


def test_from_dict_fails_loud_on_missing_required_field():
    raw = _valid_raw()
    del raw["name"]
    with pytest.raises(ManifestError, match="name"):
        from_dict(raw)


def test_from_dict_fails_loud_on_unknown_maturity():
    raw = _valid_raw()
    raw["maturity"] = "gold"
    with pytest.raises(ManifestError, match="maturity"):
        from_dict(raw)


def test_from_dict_fails_loud_on_unknown_source_status():
    raw = _valid_raw()
    raw["source_status"] = "stolen"
    with pytest.raises(ManifestError, match="source_status"):
        from_dict(raw)


def test_from_dict_fails_loud_on_non_mapping():
    with pytest.raises(ManifestError, match="mapping"):
        from_dict("not a dict")


def test_round_trip_through_to_dict():
    m = from_dict(_valid_raw())
    reconstructed = from_dict(to_dict(m))
    assert reconstructed == m


def test_to_markdown_renders_key_fields():
    m = from_dict(_valid_raw())
    md = to_markdown(m)
    assert "test-part" in md
    assert "Test Part" in md
    assert "testing" in md


def test_shipped_workflow_engine_manifest_loads():
    """The real workflow-engine.yaml loads and validates."""
    m = find_manifest("workflow-engine")
    assert m is not None
    assert m.part_id == "workflow-engine"
    assert m.maturity == "beta"
    assert len(m.interfaces) > 0
    assert len(m.tests) > 0
    assert len(m.adapters) > 0


def test_find_manifest_returns_none_for_unknown():
    assert find_manifest("no-such-part-ever") is None
