"""Test twin for parts/manifest.py -- the typed Part Manifest."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from parts.manifest import (
    ManifestError,
    PartManifest,
    find_manifest,
    from_dict,
    to_dict,
    to_markdown,
)


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


# --- Hypothesis property tests: laws the manifest gate must always hold ---

_MATURITIES = ("prototype", "beta", "shipped")
# visible, non-empty text: the gate strips whitespace, so generate around that law
_field = st.text(min_size=1, max_size=40).filter(lambda s: s.strip())
_fields = st.lists(_field, max_size=4)


@st.composite
def _raw_manifests(draw):
    return {
        "part_id": draw(_field),
        "name": draw(_field),
        "version": draw(_field),
        "maturity": draw(st.sampled_from(_MATURITIES)),
        "purpose": draw(_field),
        "source": draw(_field),
        "domain": draw(_field),
        "inputs": draw(st.text(max_size=40)),
        "interfaces": draw(_fields),
        "dependencies": draw(_fields),
        "tests": draw(_fields),
        "adapters": draw(_fields),
    }


@pytest.mark.property
@given(_raw_manifests())
def test_round_trip_law_holds_for_any_valid_manifest(raw):
    """from_dict(to_dict(m)) == m -- serialization must never lose or invent data."""
    m = from_dict(raw)
    assert from_dict(to_dict(m)) == m


@pytest.mark.property
@given(_raw_manifests(), st.sampled_from(("part_id", "name", "purpose", "source")))
def test_a_whitespace_only_required_field_always_fails_loud(raw, field):
    """The gate strips before checking: '   ' is as missing as ''."""
    raw[field] = "   "
    with pytest.raises(ManifestError, match=field):
        from_dict(raw)


@pytest.mark.property
@given(_raw_manifests(), st.text(max_size=20).filter(lambda s: s not in _MATURITIES))
def test_any_maturity_outside_the_enum_is_refused(raw, bad):
    raw["maturity"] = bad
    with pytest.raises(ManifestError, match="maturity"):
        from_dict(raw)
