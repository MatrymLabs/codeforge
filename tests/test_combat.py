"""Test twin for parts/combat.py -- deterministic training-loop math."""

import copy

import pytest

from parts import npcs
from parts.combat import attack, award_xp, strike_power
from parts.events import bind_echo, unbind_echo
from parts.jobs import bind_calling
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    yield
    npcs.NPCS = npcs_snap
    SESSIONS.clear()


def _fighter(job: str = "vanguard", location: str = "courtyard") -> Session:
    s = Session(player_id="matrym", location=location)
    SESSIONS["matrym"] = s
    bind_calling(s, job)
    return s


def test_attack_without_a_calling_is_refused():
    s = Session(player_id="matrym", location="courtyard")
    assert "no calling yet" in attack(s, "dummy")


def test_peaceful_npcs_cannot_be_fought():
    s = _fighter(location="library")
    assert "not something you can fight" in attack(s, "librarian")


def test_damage_comes_from_strength():
    assert strike_power(_fighter("vanguard")) == 3 + 14 // 3  # 7
    SESSIONS.clear()
    assert strike_power(_fighter("scholar")) == 3 + 5 // 3  # 4


def test_strikes_wear_the_dummy_down_and_it_reassembles():
    s = _fighter()  # 7 damage vs 20 hp: 13, 6, defeat
    assert "(13/20)" in attack(s, "dummy")
    assert "(6/20)" in attack(s, "dummy")
    final = attack(s, "dummy")
    assert "reassembles" in final
    assert "You gain 30 XP." in final
    assert npcs.NPCS["training_dummy"]["hp_now"] == 20


def test_level_up_crosses_the_locked_curve_and_grows_resources():
    s = _fighter()  # vanguard: sta 12, mag 4; level 2 needs 75 XP
    hp_before = s.resources["hp"].maximum
    message = award_xp(s, 80)
    assert "LEVEL UP" in message
    assert s.level == 2
    assert s.resources["hp"].maximum == hp_before + 4 + 12 // 4  # mk1 formula
    assert s.resources["hp"].is_full


def test_the_room_witnesses_the_level_up():
    s = _fighter()
    b = Session(player_id="bystander", location="courtyard")
    SESSIONS["bystander"] = b
    heard: list[str] = []
    bind_echo("bystander", heard.append)
    award_xp(s, 80)
    assert "Matrym has reached level 2!" in heard
    unbind_echo("bystander")


def test_attack_flows_through_the_engine_tick():
    from forge import handle_command

    s = _fighter()
    out = handle_command(s, "attack dummy")
    assert "You strike the training dummy" in out
