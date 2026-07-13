"""Test twin for parts/cli.py -- the dispatch table, not the servers."""

from parts.characters import save_character
from parts.cli import main
from parts.session import SESSIONS, Session


def test_unknown_verbs_print_usage_and_fail(capsys):
    assert main(["dance"]) == 1
    assert "hardware-store counter" in capsys.readouterr().out


def test_help_prints_usage_and_succeeds(capsys):
    assert main(["help"]) == 0
    assert "spark" in capsys.readouterr().out


def test_grant_dispatches_to_the_record_layer(capsys):
    hero = Session(player_id="matrym", named=True)
    SESSIONS["matrym"] = hero
    save_character(hero)
    SESSIONS.clear()
    assert main(["grant", "matrym", "owner"]) == 0
    assert "matrym is now rank: owner." in capsys.readouterr().out


def test_grant_with_wrong_arity_is_usage(capsys):
    assert main(["grant", "matrym"]) == 1


def test_api_command_serves_on_the_configured_port(monkeypatch):
    # The `api` command must honor the configured port, not a hardcoded 8000.
    import uvicorn

    from parts import config

    calls: dict = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: calls.update(kw))
    monkeypatch.setattr(config.Settings, "load", classmethod(lambda cls, env=None: cls(port=4321)))
    assert main(["api"]) == 0
    assert calls["port"] == 4321  # from Settings, not a hardcoded literal
    assert calls["host"] == "0.0.0.0"
