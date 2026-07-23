"""Fuzz harness for the hostile-input gates: seed YAML, catalog YAML, part manifests.

The law under test: a validating gate either returns a valid object or raises ITS OWN
error type (SeedError, CatalogError, ManifestError, yaml.YAMLError). It must never
escape with an unexpected TypeError/KeyError/AttributeError -- that is a crash, not a
refusal, and crashes at a trust boundary are security findings.

Hypothesis-driven (no new dependency): structured junk exercises the validators, raw
text exercises the YAML parse itself. Run the deep lane with `make fuzz`.
"""

from __future__ import annotations

import tempfile
from contextlib import suppress
from pathlib import Path

import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from parts.hardware import CatalogError, _parse_catalog
from parts.manifest import ManifestError, from_dict
from parts.world.seed import SeedError, load_rooms

# YAML-representable junk: scalars, lists, and dicts, recursively (depth-capped).
_scalars = (
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(max_size=30)
)
_junk = st.recursive(
    _scalars,
    lambda children: (
        st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=10), children, max_size=4)
    ),
    max_leaves=12,
)

_GATE_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


def _write_yaml_text(text: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115 - handed to the gate, closed here
        mode="w", suffix=".yaml", encoding="utf-8", delete=False
    )
    with tmp:
        tmp.write(text)
    return Path(tmp.name)


@pytest.mark.fuzz
@_GATE_SETTINGS
@given(_junk)
def test_manifest_gate_never_crashes_on_structured_junk(raw):
    """from_dict returns a PartManifest or raises ManifestError -- nothing else."""
    with suppress(ManifestError):  # a refusal is the contract
        from_dict(raw)


_VALID_MANIFEST = {
    "part_id": "fuzz-part",
    "name": "Fuzz Part",
    "version": "0.1",
    "maturity": "beta",
    "purpose": "exercise the gate",
    "source": "parts/fuzz.py",
    "domain": "testing",
}
_FIELDS = (*_VALID_MANIFEST, "interfaces", "dependencies", "tests", "adapters", "inputs")


@pytest.mark.fuzz
@_GATE_SETTINGS
@given(st.sampled_from(_FIELDS), _junk)
def test_manifest_gate_never_crashes_when_one_field_is_corrupted(field, junk):
    """Random junk rarely has all required keys, so it only tests the missing-field
    path. This starts VALID and corrupts one field, driving junk into the coercion
    lines -- the mutation-style fuzz that reaches past the front gate."""
    raw = dict(_VALID_MANIFEST)
    raw[field] = junk
    with suppress(ManifestError):
        from_dict(raw)


@pytest.mark.fuzz
@_GATE_SETTINGS
@given(st.text(max_size=300))
def test_seed_gate_never_crashes_on_raw_text(text):
    """load_rooms on arbitrary YAML text refuses with SeedError/YAMLError, never crashes."""
    path = _write_yaml_text(text)
    try:
        load_rooms(path)
    except (SeedError, yaml.YAMLError):
        pass  # the contract: a loud, typed refusal
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.fuzz
@_GATE_SETTINGS
@given(_junk)
def test_seed_gate_never_crashes_on_structured_junk(raw):
    """load_rooms on arbitrary YAML documents refuses, never crashes."""
    path = _write_yaml_text(yaml.safe_dump(raw, allow_unicode=True))
    try:
        load_rooms(path)
    except (SeedError, yaml.YAMLError):
        pass
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.fuzz
@_GATE_SETTINGS
@given(_junk)
def test_catalog_gate_never_crashes_on_structured_junk(raw):
    """_parse_catalog on arbitrary YAML documents refuses with CatalogError, never crashes."""
    path = _write_yaml_text(yaml.safe_dump(raw, allow_unicode=True))
    try:
        _parse_catalog(path)
    except (CatalogError, yaml.YAMLError):
        pass
    finally:
        path.unlink(missing_ok=True)
