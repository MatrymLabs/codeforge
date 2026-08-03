"""CARD: test_hypothesis_corpus -- the committed Hypothesis corpus profile persists failing cases.

AP-08 / RD-2026-0002 #22. Acceptance: conftest registered + loaded a `ci` profile backed by a
committed directory database; a failing example stored by a test replays for that SAME test in a
later, independent run (Hypothesis keys its database by test-function identity - the real-CI case).
Refusal: a fresh empty corpus does not fabricate a replay (no false green); a corrupt corpus entry
is tolerated, not crashed on.
"""

from __future__ import annotations

from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.database import DirectoryBasedExampleDatabase

_NEEDLE = 480_017  # a rare regression ordinary integer search finds unreliably


def _run(corpus_dir: Path, budget: int, lo: int, hi: int) -> bool:
    """Run a rare-needle round-trip property under a corpus dir. True iff a failure reproduced.

    All calls share one function identity, so an example stored by one call is keyed to replay for
    the next - the situation the committed corpus exists to make reliable.
    """

    @settings(
        database=DirectoryBasedExampleDatabase(str(corpus_dir)),
        max_examples=budget,
        deadline=None,
        suppress_health_check=list(HealthCheck),
    )
    @given(st.integers(min_value=lo, max_value=hi))
    def prop(n: int) -> None:
        # identity except at the needle -> a rare, deterministic falsifier to persist
        assert (n + 1 if n == _NEEDLE else n) == n

    try:
        prop()
    except AssertionError:
        return True
    return False


def test_ci_profile_is_active_and_directory_backed() -> None:
    prof = settings.get_profile("ci")
    assert isinstance(prof.database, DirectoryBasedExampleDatabase)


def test_a_committed_example_replays_in_a_later_run(tmp_path: Path) -> None:
    corpus = tmp_path / "corpora"
    assert _run(corpus, budget=400, lo=_NEEDLE - 50, hi=_NEEDLE + 50) is True
    assert any(p.is_file() for p in corpus.rglob("*")), "discovery must store an example"
    # a fresh, tiny-budget run replays the stored example deterministically
    assert _run(corpus, budget=1, lo=_NEEDLE - 50, hi=_NEEDLE + 50) is True


def test_empty_corpus_does_not_fabricate_a_replay(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    # ordinary wide search, tiny budget, no stored example -> must not reproduce the rare needle
    assert _run(empty, budget=1, lo=-(2**31), hi=2**31) is False


def test_a_corrupt_corpus_entry_is_tolerated(tmp_path: Path) -> None:
    corpus = tmp_path / "corpora"
    corpus.mkdir()
    (corpus / "garbage").write_bytes(b"\x00\xff not a real entry \x00")
    assert _run(corpus, budget=1, lo=-(2**31), hi=2**31) in (True, False)
