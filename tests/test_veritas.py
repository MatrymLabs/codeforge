"""Test twin for parts/veritas.py -- VeritasGate (`truth check`).

Acceptance (the real repo's claims verify) and refusal (a planted overclaim, a
hardcoded count, and a missing doc are FLAGGED, not hidden) are both pinned; the
command is proven reachable through the engine tick.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from forge import handle_command
from parts.session import SESSIONS, Session
from parts.veritas import FLAGGED, VERIFIED, render_truth, truth_checks


def test_the_real_repo_passes_its_own_truth_checks() -> None:
    # every claim VeritasGate makes about this repo must currently hold
    checks = truth_checks()
    flagged = [c.claim for c in checks if c.status != VERIFIED]
    assert not flagged, f"VeritasGate flagged real claims: {flagged}"


def test_render_reports_the_overall_verdict() -> None:
    out = render_truth()
    assert "No claim without correspondence" in out
    assert "ALL VERIFIED" in out  # the repo is currently honest


def test_a_planted_overclaim_and_hardcoded_count_are_flagged(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("CodeForge is production-ready. 999 tests pass.")
    checks = truth_checks(root=tmp_path)
    by_claim = {c.claim: c.status for c in checks}
    # overclaim word -> flagged
    assert any(s == FLAGGED for c, s in by_claim.items() if "compliance" in c or "production" in c)
    # hardcoded "999 tests" -> flagged
    assert any(s == FLAGGED for c, s in by_claim.items() if "hardcoded" in c or "test count" in c)
    # missing docs (tmp has only README) -> flagged
    assert any(s == FLAGGED for c, s in by_claim.items() if "documentation" in c)


@pytest.fixture(autouse=True)
def fresh() -> Iterator[None]:
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def test_truth_check_reachable_through_the_tick() -> None:
    session = Session(player_id="veritas")
    SESSIONS["veritas"] = session
    out = handle_command(session, "truth check")
    assert "VeritasGate" in out
    assert "Verdict:" in out
