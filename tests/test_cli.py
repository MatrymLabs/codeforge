"""Test twin for parts/cli.py -- the dispatch table, not the servers."""

from parts.cli import main
from parts.world.characters import save_character
from parts.world.session import SESSIONS, Session


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

    from parts.shelf import config

    calls: dict = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: calls.update(kw))
    monkeypatch.setattr(config.Settings, "load", classmethod(lambda cls, env=None: cls(port=4321)))
    assert main(["api"]) == 0
    assert calls["port"] == 4321  # from Settings, not a hardcoded literal
    assert calls["host"] == "0.0.0.0"


# --- one test per dispatch-table handler (servers/loops mocked, never launched) ---


def test_seeds_lists_installed_games(capsys, monkeypatch):
    monkeypatch.setattr("parts.cli._seeds_available", lambda: ["alpha", "beta"])
    assert main(["seeds"]) == 0
    out = capsys.readouterr().out
    assert "alpha" in out and "beta" in out


def test_a_valid_seed_sets_the_env_before_dispatch(monkeypatch):
    import os

    monkeypatch.setattr("parts.cli._seeds_available", lambda: ["alpha", "beta"])
    monkeypatch.setattr("parts.gateway.serve", lambda: None)
    monkeypatch.setenv("FORGE_SEED", "unset")  # tracked by monkeypatch -> restored after the test
    assert main(["--seed", "beta", "serve"]) == 0  # env must be set before the world imports
    assert os.environ["FORGE_SEED"] == "beta"


def test_no_args_defaults_to_serve(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr("parts.gateway.serve", lambda: calls.append(1))
    assert main([]) == 0  # bare `codeforge` ignites the server
    assert calls == [1]


def test_serve_dispatches_to_the_gateway(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr("parts.gateway.serve", lambda: calls.append(1))
    assert main(["serve"]) == 0
    assert calls == [1]


def test_play_dispatches_to_the_game_loop(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr("forge.game_loop", lambda: calls.append(1))
    assert main(["play"]) == 0
    assert calls == [1]


def test_onboard_dispatches_to_the_workflow(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr("parts.onboarding.drive", lambda: calls.append(1))
    assert main(["onboard"]) == 0
    assert calls == [1]


def test_web_serves_on_the_configured_port(monkeypatch):
    import uvicorn

    from parts.shelf import config

    calls: dict = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: calls.update(kw))
    monkeypatch.setattr(config.Settings, "load", classmethod(lambda cls, env=None: cls(port=5555)))
    assert main(["web"]) == 0
    assert calls["port"] == 5555
    assert calls["host"] == "0.0.0.0"


def test_migrate_dispatches_and_validates_arity(capsys, monkeypatch):
    monkeypatch.setattr("parts.world.accounts.migrate", lambda c, a: f"{c}@{a} moved")
    assert main(["migrate", "matrym", "matlabs"]) == 0
    assert "matrym@matlabs moved" in capsys.readouterr().out
    assert main(["migrate", "matrym"]) == 1  # wrong arity -> usage


def test_migrate_db_reports_when_no_legacy_files(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # empty dir -- no characters.json / accounts.json
    assert main(["migrate-db"]) == 0
    assert "No legacy JSON found" in capsys.readouterr().out


def test_passwd_rotates_when_the_confirmations_match(capsys, monkeypatch):
    import getpass

    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "MatchingPw1")
    monkeypatch.setattr("parts.world.accounts.rotate_account_secret", lambda a, pw: f"Rotated {a}.")
    assert main(["passwd", "matlabs"]) == 0
    assert "Rotated matlabs." in capsys.readouterr().out


def test_passwd_refuses_a_mismatch_and_wrong_arity(capsys, monkeypatch):
    import getpass

    answers = iter(["FirstEntry1", "SecondEntry2"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": next(answers))
    assert main(["passwd", "matlabs"]) == 1  # the two entries differ
    assert "Mismatch" in capsys.readouterr().out
    assert main(["passwd"]) == 1  # wrong arity -> usage
