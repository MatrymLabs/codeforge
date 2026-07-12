"""Test twin for parts/paths.py -- the env-override path resolver."""

from pathlib import Path

from parts.paths import resolved_path


def test_default_used_when_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("CF_TEST_PATH", raising=False)
    default = tmp_path / "d"
    assert resolved_path("CF_TEST_PATH", default) == default


def test_override_wins_and_is_expanded(monkeypatch):
    monkeypatch.setenv("CF_TEST_PATH", "~/custom/thing")
    result = resolved_path("CF_TEST_PATH", Path("/default"))
    assert result == Path("~/custom/thing").expanduser()
    assert str(result).startswith(str(Path.home()))  # ~ was expanded


def test_empty_override_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("CF_TEST_PATH", "")
    default = Path("/default")
    assert resolved_path("CF_TEST_PATH", default) == default  # empty string is falsy
