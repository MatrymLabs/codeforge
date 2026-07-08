"""Test twin for parts/cli.py -- the dispatch table, not the servers."""

from parts.characters import save_character
from parts.cli import main
from parts.session import SESSIONS, Session


def test_unknown_verbs_print_usage_and_fail(capsys):
    assert main(["dance"]) == 1
    assert "codeforge -- the world engine" in capsys.readouterr().out


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
