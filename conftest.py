import pytest


@pytest.fixture(autouse=True)
def _isolated_characters(tmp_path, monkeypatch):
    """No test may ever touch the real characters.json."""
    from parts import characters

    monkeypatch.setattr(characters, "CHARACTERS_PATH", tmp_path / "characters.json")
