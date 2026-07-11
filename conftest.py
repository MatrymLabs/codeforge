import pytest


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
    from parts import accounts, db, loader_cache

    # The shared parse-once cache is keyed by resolved path + mtime; clear it so a tmp file
    # reused across tests (same path, coarse mtime granularity) can never serve stale data.
    loader_cache.clear()

    # A DATABASE_URL in the ambient shell must never redirect the suite at a real
    # PostgreSQL: the unit tests always run on a fresh, quarantined SQLite tmp file.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(accounts, "_ITERATIONS", 1000)
