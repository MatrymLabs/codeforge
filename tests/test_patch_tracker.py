"""Test twin for parts/patch_tracker.py -- the practical adapter for the change ledger."""

from parts.change_ledger import ChangeLedger
from parts.patch_tracker import PatchTracker
from parts.statemachine import Fired, Refusal


def _walk_to_verified(tracker: PatchTracker, patch_id: str) -> None:
    tracker.advance(patch_id, "triage")
    tracker.advance(patch_id, "approve", actor="approver")
    tracker.advance(patch_id, "build")
    tracker.advance(patch_id, "test")
    tracker.pass_tests(patch_id)
    tracker.advance(patch_id, "canary", actor="operator")
    tracker.review_arc(patch_id)  # slice 4: deploy needs a non-blocked ARC verdict
    tracker.advance(patch_id, "deploy", actor="operator")
    tracker.advance(patch_id, "verify", actor="operator")


def test_a_cve_patch_walks_the_full_lifecycle_to_closed():
    tracker = PatchTracker()
    patch = tracker.record_cve_patch(
        "CVE-FIX-1", "Bump urllib3", "high", "CVE-2026-9", "urllib3", rollback_plan="pin prior"
    )
    assert patch.cve_refs == ("CVE-2026-9",) and patch.components == ("urllib3",)
    _walk_to_verified(tracker, "CVE-FIX-1")
    assert isinstance(tracker.advance("CVE-FIX-1", "close"), Fired)
    assert tracker.status("CVE-FIX-1") == "closed"


def test_a_patch_cannot_deploy_without_an_arc_review():
    tracker = PatchTracker()
    tracker.record_dependency_bump("DEP-2", "Bump ruff", "ruff")
    tracker.advance("DEP-2", "triage")
    tracker.advance("DEP-2", "approve", actor="approver")
    tracker.advance("DEP-2", "build")
    tracker.advance("DEP-2", "test")
    tracker.pass_tests("DEP-2")
    tracker.advance("DEP-2", "canary", actor="operator")
    assert isinstance(tracker.advance("DEP-2", "deploy", actor="operator"), Refusal)  # no ARC yet


def test_a_patch_cannot_reach_canary_before_its_tests_pass():
    tracker = PatchTracker()
    tracker.record_dependency_bump("DEP-1", "Bump ruff", "ruff")
    tracker.advance("DEP-1", "triage")
    tracker.advance("DEP-1", "approve", actor="approver")
    tracker.advance("DEP-1", "build")
    tracker.advance("DEP-1", "test")
    assert isinstance(tracker.advance("DEP-1", "canary", actor="operator"), Refusal)


def test_one_core_two_adapters_share_the_change_ledger():
    # The practical tracker holds a ChangeLedger, exactly as the game maintenance log does.
    assert isinstance(PatchTracker()._ledger, ChangeLedger)
