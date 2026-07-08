import pytest


@pytest.fixture(autouse=True)
def _isolated_database(tmp_path, monkeypatch):
    """No test may ever touch the real codeforge.db."""
    from parts import db

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
