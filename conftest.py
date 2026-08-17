from pathlib import Path

import pytest
from hypothesis import settings
from hypothesis.database import DirectoryBasedExampleDatabase

# Hypothesis corpus persistence (AP-08 / RD-2026-0002 #22). A falsifying example Hypothesis
# finds is written to a COMMITTED directory, so it replays on every other machine and CI run
# instead of only where it was found. `tests/corpora/` is git-tracked; commit a new example
# alongside the fix that provoked it. This is settings config, not a fixture, so it does not
# touch the DB-quarantine fixture below.
_CORPORA = Path(__file__).parent / "tests" / "corpora"
_CORPORA.mkdir(exist_ok=True)
settings.register_profile("ci", database=DirectoryBasedExampleDatabase(str(_CORPORA)))
settings.load_profile("ci")


class _NeutralRng:
    """A stand-in for combat's variance RNG whose roll always lands in the NORMAL band (no miss,
    no crit, no glance). Installed for the whole suite so every deterministic exact-damage assertion
    still holds; a variance test replaces `combat._COMBAT_RNG` with its own forcing stub."""

    @staticmethod
    def random() -> float:
        return 0.99  # > MISS + CRIT + GLANCE: always a normal hit


@pytest.fixture(autouse=True)
def _isolated_database(tmp_path, monkeypatch):
    """Every test runs isolated and fast:

    - No test may ever touch the real codeforge.db (quarantine DB_PATH into tmp).
    - Password hashing drops to a low pbkdf2 iteration count so the suite isn't
      dominated by deliberately-expensive hashing. Production stays 600k -- the
      constant is read at call time and this override only exists inside the test
      process. The tests still prove hash/verify/rotate LOGIC, just not the 600k
      strength (that's a production config, not a behavior).
    """
    from kernel.shelf import loader_cache
    from kernel.world import accounts, db
    from kernel.world.session import SESSIONS

    # The shared parse-once cache is keyed by resolved path + mtime; clear it so a tmp file
    # reused across tests (same path, coarse mtime granularity) can never serve stale data.
    loader_cache.clear()

    # SESSIONS is a process-global registry. A test that leaves a session in it (e.g. one named
    # "matrym") would collide with another test's rename -- an isolation flake that only surfaces
    # under some -n auto orderings. Clear it before every test so none inherits a stray session.
    SESSIONS.clear()

    # A DATABASE_URL in the ambient shell must never redirect the suite at a real
    # PostgreSQL: the unit tests always run on a fresh, quarantined SQLite tmp file.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(accounts, "_ITERATIONS", 1000)

    # The audit ledger is a real runtime state file too: quarantine it into tmp so a test never
    # appends to (or reads) the real audit.jsonl at the repo root.
    monkeypatch.setenv("CODEFORGE_AUDIT", str(tmp_path / "audit.jsonl"))

    # The Chronicle ledger is a real, git-tracked state file too. Now that main RETAINS evidence
    # (no longer an empty vault), a test that reads it with the default root would depend on the
    # committed ledger's contents. Quarantine root=None into tmp, so tests see an empty store unless
    # they populate their own; a test that means to read the real ledger passes an explicit root.
    from kernel import chronicle

    _real_ledger_path = chronicle._ledger_path
    _repo_root = Path(chronicle.__file__).resolve().parent.parent
    # Redirect BOTH the default (root=None) and an explicit repo-root read to tmp: ARC reads the
    # Chronicle with root=repo_root, so covering only root=None would let a test read the real one.
    monkeypatch.setattr(
        chronicle,
        "_ledger_path",
        lambda root: _real_ledger_path(
            tmp_path if root is None or Path(root).resolve() == _repo_root else root
        ),
    )

    # Combat variance rolls a die on every blow (miss/glance/crit). Neutralize it suite-wide so the
    # deterministic damage assertions stay exact; a variance test installs its own forcing RNG.
    from kernel.world import combat

    monkeypatch.setattr(combat, "_COMBAT_RNG", _NeutralRng())
