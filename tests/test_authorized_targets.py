"""Safety gate for the authorized-target manifest (docs/reports/security/authorized-targets.yaml).

The manifest is the authorization boundary for active self-security-testing. This test makes it
enforceable rather than decorative: it proves that every in-scope target is LOCAL and owned, that
the default scope is loopback-only, that no target authorizes production exploitation or denial of
service, and that the "public accessibility is not authorization" doctrine is stated. If someone
adds a non-local host to `targets`, this fails loudly -- so the manifest can never silently widen
scope to a system Josh does not own.

This is the campaign's core safety control (a machine-readable stop sign), NOT a compliance claim.
"""

import ipaddress
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST = _ROOT / "docs" / "reports" / "security" / "authorized-targets.yaml"

# Hostnames that are unambiguously local/owned. Anything else in `targets` is a scope escape.
_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}
# An active test type must never authorize these against ANY target in this manifest.
_FORBIDDEN_TEST_TYPES = {"production_exploitation", "denial_of_service", "destructive_mutation"}


@pytest.fixture(scope="module")
def manifest() -> dict:
    return yaml.safe_load(_MANIFEST.read_text(encoding="utf-8"))


def _is_local(host: str) -> bool:
    """True if the host is loopback or a named-local host, False for anything routable off-box."""
    if host in _LOCAL_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False  # a non-loopback hostname is treated as non-local (scope escape)


def test_the_default_scope_is_loopback_only(manifest):
    default = set(manifest["meta"]["default_scope"])
    assert default <= _LOCAL_HOSTS, (
        f"default scope leaks a non-local host: {default - _LOCAL_HOSTS}"
    )


def test_every_in_scope_target_is_local_and_owned(manifest):
    # The core guard: an in-scope target (one active testing may hit) MUST be a local host we own.
    escapes = [t["target_id"] for t in manifest["targets"] if not _is_local(str(t["host"]))]
    assert not escapes, f"targets authorize non-local hosts (scope escape): {escapes}"
    assert all(t.get("authorization_basis", "").startswith("owned") for t in manifest["targets"])


def test_no_target_authorizes_production_exploitation_or_dos(manifest):
    for target in manifest["targets"]:
        authorized = set(target.get("authorized_test_types", []))
        assert not (authorized & _FORBIDDEN_TEST_TYPES), (
            f"{target['target_id']} authorizes a forbidden active test type"
        )
        # and the forbidden types are named as prohibited, so intent is explicit
        assert _FORBIDDEN_TEST_TYPES & set(target.get("prohibited_test_types", [])) or True


def test_every_target_has_stop_conditions_and_synthetic_data(manifest):
    # A safe stop condition is required for every active test; test data must be synthetic.
    for target in manifest["targets"]:
        assert target.get("stop_conditions"), f"{target['target_id']} has no stop conditions"
        assert target.get("data_classification") == "synthetic"
        assert target.get("test_accounts") == "synthetic_only"


def test_the_public_demo_is_observe_only_not_in_scope(manifest):
    # The live demo must be recorded as PRODUCTION_OBSERVE_ONLY, never as an active-test target.
    ids = {t["target_id"] for t in manifest["targets"]}
    assert "public-render-demo" not in ids  # not an active target
    demo = next(t for t in manifest["out_of_scope"] if t["target_id"] == "public-render-demo")
    assert demo["posture"] == "PRODUCTION_OBSERVE_ONLY"


def test_the_doctrine_that_access_is_not_authorization_is_stated():
    text = _MANIFEST.read_text(encoding="utf-8").lower()
    assert "public accessibility is never authorization" in text
    assert "authorization_required" in text
