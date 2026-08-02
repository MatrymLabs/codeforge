"""Honesty gate for the security control crosswalk (docs/reports/security/control-crosswalk.yaml).

A control-to-framework crosswalk is only worth anything if it cannot rot into fiction or drift into
an overclaim. This is the EvidenceGate for it (the same "every claim cites a source that exists" rule
the repo applies elsewhere): every cited path must exist on disk, every control carries an allowed
(non-compliance) status, and the file must state plainly that it is NOT a compliance claim.

If someone deletes a cited test/config, or edits a status to "compliant"/"certified", this test
fails loudly -- so the crosswalk stays honest evidence, not decorative metadata.
"""

from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
_CROSSWALK = _ROOT / "docs" / "reports" / "security" / "control-crosswalk.yaml"

# Words a control status must never contain -- the crosswalk records evidence, never compliance.
_FORBIDDEN_STATUS_WORDS = ("compliant", "certified", "authorized", "satisfied", "assessment-ready")


@pytest.fixture(scope="module")
def crosswalk() -> dict:
    return yaml.safe_load(_CROSSWALK.read_text(encoding="utf-8"))


def test_the_crosswalk_declares_it_is_not_a_compliance_claim(crosswalk):
    meta = crosswalk["meta"]
    assert meta["compliance_claim"] == "none"
    disclaimer = meta["disclaimer"].lower()
    assert "not a compliance claim" in disclaimer
    assert "independent assessment" in disclaimer


def test_every_control_has_a_valid_non_compliance_status(crosswalk):
    allowed = set(crosswalk["meta"]["allowed_status"])
    # the allowed set itself must not smuggle in a compliance word
    assert not any(w in s for s in allowed for w in _FORBIDDEN_STATUS_WORDS)
    for control in crosswalk["controls"]:
        status = control["status"]
        assert status in allowed, f"{control['id']}: status '{status}' is not allowed"


def test_every_cited_path_exists(crosswalk):
    # The core guard: a control's implementation path and every evidence path must be a real file,
    # so the crosswalk can never cite a deleted or imaginary control.
    missing: list[str] = []
    for control in crosswalk["controls"]:
        cited: list[str] = []
        if "implementation" in control:
            cited.append(str(control["implementation"]).split("#", 1)[0].strip())
        for ev in control.get("evidence", []):
            cited.append(str(ev["path"]).split("#", 1)[0].strip())
        for path in cited:
            if not (_ROOT / path).exists():
                missing.append(f"{control['id']} -> {path}")
    assert not missing, f"crosswalk cites paths that do not exist: {missing}"


def test_applicable_controls_carry_evidence_and_a_framework_mapping(crosswalk):
    for control in crosswalk["controls"]:
        if control["applicability"] != "applicable":
            continue  # not-applicable rows record scope only; no evidence required
        assert control.get("evidence"), f"{control['id']}: an applicable control needs evidence"
        assert control.get("frameworks"), f"{control['id']}: an applicable control needs a mapping"


def test_control_ids_are_unique(crosswalk):
    ids = [c["id"] for c in crosswalk["controls"]]
    assert len(ids) == len(set(ids)), "duplicate control ids in the crosswalk"
