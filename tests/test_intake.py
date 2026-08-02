"""Test twin for kernel/intake.py -- the Technology Intake Office.

Acceptance: the real intake ledger is clean (every onboarding record is complete and consistent).
Refusal (the point): an approved technology missing a requirement fails, an unknown class or
decision fails, a NATIVE_PYTHON row that is not Python fails, an external role with no boundary,
and a malformed or missing ledger fails loud. This test rides `make check`, so a technology adopted
without a complete, consistent onboarding record cannot merge silently.
"""

from __future__ import annotations

import pytest

from kernel.intake import (
    CLASSIFICATIONS,
    DECISIONS,
    REQUIRED,
    IntakeError,
    TechnologyIntakeRecord,
    audit_intake,
    gaps,
    read_ledger,
    render_intake,
)

# A complete APPROVED record: every one of the ten requirements filled, consistent.
_COMPLETE = {
    "technology_name": "Example",
    "classification": "PYTHON_PACKAGE",
    "language": "python",
    "decision": "approved",
    **{req: "answered" for req in REQUIRED},
}


def _record(**overrides) -> TechnologyIntakeRecord:
    return TechnologyIntakeRecord("example", {**_COMPLETE, **overrides})


# --- acceptance: the real ledger and a complete record ---------------------------------


def test_the_real_ledger_is_clean():
    audit = audit_intake()  # the repo's own intake_ledger.toml
    assert audit.passed, audit.flagged
    assert audit.records  # it is not empty


def test_a_complete_consistent_record_has_no_gaps():
    assert gaps(_record()) == []


def test_a_research_only_record_need_not_carry_every_requirement():
    # a not-yet-approved record may still be filling in the ten requirements
    record = TechnologyIntakeRecord(
        "study",
        {
            "technology_name": "X",
            "classification": "RESEARCH_REFERENCE",
            "decision": "research_only",
        },
    )
    assert gaps(record) == []


# --- refusal: incompleteness and inconsistency -----------------------------------------


def test_an_approved_record_missing_a_requirement_is_flagged():
    record = _record(removal_strategy="")  # no exit plan
    assert any("missing removal_strategy" in g for g in gaps(record))


def test_an_unknown_classification_is_flagged():
    assert any("unknown classification" in g for g in gaps(_record(classification="MAGIC")))


def test_an_unknown_decision_is_flagged():
    assert any("unknown decision" in g for g in gaps(_record(decision="maybe")))


def test_a_native_python_row_that_is_not_python_is_flagged():
    record = _record(classification="NATIVE_PYTHON", language="rust")
    assert any("not python" in g for g in gaps(record))


def test_an_external_role_without_a_boundary_is_flagged():
    record = _record(classification="EXTERNAL_SERVICE", proposed_boundary="")
    assert any("no proposed_boundary" in g for g in gaps(record))


def test_an_external_role_with_a_boundary_passes():
    record = _record(classification="SUBPROCESS_WORKER", proposed_boundary="a JSON stdio contract")
    assert gaps(record) == []


# --- the ledger reader and report ------------------------------------------------------


def test_a_missing_ledger_fails_loud(tmp_path):
    with pytest.raises(IntakeError):
        read_ledger(tmp_path / "nope.toml")


def test_a_malformed_ledger_fails_loud(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text("this is = = not toml")
    with pytest.raises(IntakeError):
        read_ledger(bad)


def test_a_flagged_ledger_makes_the_report_fail(tmp_path):
    ledger = tmp_path / "intake.toml"
    ledger.write_text('[tech.x]\nclassification = "MAGIC"\ndecision = "approved"\n')
    report = render_intake(ledger)
    assert "FAIL" in report and "x" in report


def test_the_taxonomies_are_coherent():
    # the doctrine's vocabulary is fixed and non-overlapping where it must be
    assert "NATIVE_PYTHON" in CLASSIFICATIONS and "REJECTED" in CLASSIFICATIONS
    assert "approved" in DECISIONS and "research_only" in DECISIONS
    assert len(REQUIRED) == 10  # the ten requirements every integration must carry
