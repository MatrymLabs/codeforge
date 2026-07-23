"""Test twin for parts/veritas.py -- VeritasGate (`truth check`).

Acceptance (the real repo's claims verify) and refusal (a planted overclaim, a
hardcoded count, and a missing doc are FLAGGED, not hidden) are both pinned; the
command is proven reachable through the engine tick.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from forge import handle_command
from parts.veritas import FLAGGED, VERIFIED, main, render_truth, truth_checks
from parts.world.session import SESSIONS, Session


def test_the_real_repo_passes_its_own_truth_checks() -> None:
    # every claim VeritasGate makes about this repo must currently hold
    checks = truth_checks()
    flagged = [c.claim for c in checks if c.status != VERIFIED]
    assert not flagged, f"VeritasGate flagged real claims: {flagged}"


def test_render_reports_the_overall_verdict() -> None:
    out = render_truth()
    assert "No claim without correspondence" in out
    assert "ALL VERIFIED" in out  # the repo is currently honest


def test_truth_cli_exits_zero_when_the_repo_is_honest(capsys) -> None:
    # `make truth` / `python -m parts.veritas`: the gate the ritual and CI call.
    code = main()
    out = capsys.readouterr().out
    assert code == 0  # the real repo currently verifies
    assert "VeritasGate" in out


def test_truth_cli_exits_one_when_a_claim_is_flagged(monkeypatch, capsys) -> None:
    # A FLAGGED claim must fail the gate loud (exit 1), never pass silently.
    from parts import veritas as v

    flagged = [v.TruthCheck("some claim", FLAGGED, "does not correspond")]
    monkeypatch.setattr(v, "truth_checks", lambda: flagged)
    assert main() == 1
    assert "FLAGGED" in capsys.readouterr().out


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


def test_a_hardcoded_test_count_in_living_docs_is_flagged_but_snapshots_are_exempt(
    tmp_path: Path,
) -> None:
    from parts.veritas import _hardcoded_counts

    (tmp_path / "README.md").write_text("a clean readme with no counts")
    docs = tmp_path / "docs"
    (docs / "reports").mkdir(parents=True)
    # living doc -> a test count AND a coverage % are both caught
    (docs / "scorecard.md").write_text("the suite has 1234 tests today at 91.5% branch coverage")
    (docs / "reports" / "2026-07-13.md").write_text("500 tests, 88% coverage")  # snapshot -> exempt
    hits = _hardcoded_counts(tmp_path)
    assert any("scorecard.md" in h and "1234 tests" in h for h in hits)
    assert any("scorecard.md" in h and "coverage" in h for h in hits)
    assert not any("2026-07-13" in h for h in hits)  # the dated snapshot stays exempt
    assert not any("2026-07-13" in h for h in hits)


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
