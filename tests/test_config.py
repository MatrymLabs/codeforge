"""Test twin for parts/config.py -- the typed, validated environment catalog.

Acceptance: defaults hold, values load and coerce, the render redacts credentials. Refusal
(hostile cases): a non-numeric PORT and an out-of-range port fail loud with a named error.
"""

import pytest
from pydantic import ValidationError

from parts.config import ConfigError, Settings, render_config


def test_defaults_when_the_env_is_empty():
    s = Settings.load(env={})
    assert s.port == 8000
    assert s.architect_brain == "local"
    assert s.database_url == ""
    assert s.anthropic_key_present is False


def test_loads_and_coerces_values():
    s = Settings.load(
        env={
            "PORT": "9000",
            "CODEFORGE_ARCHITECT": "claude",
            "DATABASE_URL": "postgresql+psycopg://u:p@db:5432/cf",
            "ANTHROPIC_API_KEY": "sk-live-xxx",  # pragma: allowlist secret
        }
    )
    assert s.port == 9000  # coerced str -> int
    assert s.architect_brain == "claude"
    assert s.anthropic_key_present is True


def test_odd_architect_value_is_normalized_not_crashed():
    # architect.py treats only "claude" specially; the catalog mirrors that, never crashes.
    assert Settings.load(env={"CODEFORGE_ARCHITECT": "gpt"}).architect_brain == "local"


def test_settings_are_frozen():
    s = Settings.load(env={})
    with pytest.raises(ValidationError):
        s.port = 1234


@pytest.mark.parametrize("bad_port", ["abc", "0", "70000", "-1"])
def test_bad_port_fails_loud(bad_port):
    with pytest.raises(ConfigError) as err:
        Settings.load(env={"PORT": bad_port})
    assert "invalid environment" in str(err.value)


def test_render_redacts_database_credentials():
    url = "postgresql+psycopg://user:secretpw@host:5432/cf"  # pragma: allowlist secret
    out = Settings.load(env={"DATABASE_URL": url}).render()
    assert "secretpw" not in out
    assert "[redacted]" in out
    assert "host:5432/cf" in out  # scheme + host still shown


def test_render_reports_key_presence_never_the_key():
    key = "sk-do-not-print"  # pragma: allowlist secret
    out = Settings.load(env={"ANTHROPIC_API_KEY": key}).render()
    assert "sk-do-not-print" not in out
    assert "present" in out


def test_render_config_program_reads_the_live_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("PORT", "8080")
    out = render_config()
    assert "8080" in out
    assert "CONFIGURATION" in out


def test_render_config_is_resilient_to_a_bad_env(monkeypatch):
    # A read-only display must surface a bad value, not crash the terminal.
    monkeypatch.setenv("PORT", "not-a-port")
    out = render_config()
    assert "INVALID ENVIRONMENT" in out
