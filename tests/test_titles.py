"""Test twin for parts/titles.py -- the game adapter: a sanitized player title."""

import pytest

from parts.titles import reset_titles, title
from parts.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh():
    reset_titles()
    SESSIONS.clear()
    yield
    reset_titles()
    SESSIONS.clear()


def _player() -> Session:
    s = Session(player_id="matrym", location="courtyard")
    SESSIONS["matrym"] = s
    return s


def test_setting_a_title_sanitizes_it():
    out = title(_player(), "  Grand\x07  Artificer  ")
    assert out == "Your title is now: Grand Artificer"  # control char and extra spaces gone


def test_a_title_is_capped_in_length():
    out = title(_player(), "x" * 100)
    assert len(out.removeprefix("Your title is now: ")) == 24  # capped


def test_an_all_control_title_is_refused():
    assert "empty once cleaned" in title(_player(), "\x00\x07\x1f")


def test_title_flows_through_the_engine_tick():
    from forge import handle_command

    handle_command(_player(), "title Keeper Of The Forge")
    assert "Keeper Of The Forge" in handle_command(_player(), "title")  # original case kept
