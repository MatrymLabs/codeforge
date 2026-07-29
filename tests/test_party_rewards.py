"""Test twin for parts/world/party_rewards.py -- shared combat's reward half.

Acceptance: when a partied hero fells a foe with a mate present, the mate earns the full kill reward
and is told so, and the killer sees a share summary; wired through combat.land_hit end to end.
Refusal (no reward leaks where it should not): a solo kill shares nothing, a kill while the mates
are in another room shares nothing, and an offline or callingless mate earns nothing without error.
"""

from __future__ import annotations

from parts.world import events, party
from parts.world.combat import land_hit
from parts.world.jobs import bind_calling
from parts.world.party_rewards import share_kill
from parts.world.session import SESSIONS, Session


def _hero(name: str, room: str = "greenhold") -> Session:
    s = SESSIONS[name] = Session(player_id=name, location=room)
    bind_calling(s, "vanguard")  # a calling gives the stats/level XP awards need
    return s


def _band(*names: str) -> None:
    """Form a party of the given already-seated players, first as leader."""
    lead, rest = names[0], names[1:]
    for other in rest:
        party.invite(lead, other)
        party.join(other, lead)


def _teardown() -> None:
    party._reset()
    for name in list(SESSIONS):
        events.unbind_echo(name)
        SESSIONS.pop(name, None)


def _foe() -> dict:
    """A minimal felled-ready tutorial foe: flat xp, one hit from death, no zone/quest tangle."""
    return {"name": "a straw dummy", "hp": 10, "hp_now": 1, "xp": 20, "keywords": []}


# --- acceptance --------------------------------------------------------------------------------
def test_a_present_mate_shares_the_kill_reward():
    inbox_b: list[str] = []
    try:
        _hero("alia")
        _hero("bram")
        events.bind_echo("bram", inbox_b.append)
        _band("alia", "bram")
        before = SESSIONS["bram"].xp
        summary = share_kill("alia", "greenhold", "a straw dummy", 20, 0, 0)
        assert SESSIONS["bram"].xp == before + 20  # the mate earned the full reward
        assert "shares the kill (1 ally)" in summary
        assert any("share the kill" in line for line in inbox_b)  # and was told
    finally:
        _teardown()


def test_the_reward_shares_through_the_land_hit_seam():
    try:
        _hero("alia")
        _hero("bram")
        _band("alia", "bram")
        before = SESSIONS["bram"].xp
        defeated, tail = land_hit(SESSIONS["alia"], _foe(), "dummy", 5)  # 5 dmg fells the 1-hp foe
        assert defeated and "shares the kill" in tail
        assert SESSIONS["bram"].xp > before  # the co-located mate advanced from alia's kill
    finally:
        _teardown()


# --- refusal / no-leak -------------------------------------------------------------------------
def test_a_solo_kill_shares_nothing():
    try:
        _hero("alia")
        assert share_kill("alia", "greenhold", "a foe", 20, 0, 0) == ""
    finally:
        _teardown()


def test_a_kill_shares_nothing_when_mates_are_elsewhere():
    try:
        _hero("alia", "greenhold")
        _hero("bram", "the-deep")  # a party-mate in another room
        _band("alia", "bram")
        before = SESSIONS["bram"].xp
        assert share_kill("alia", "greenhold", "a foe", 20, 0, 0) == ""
        assert SESSIONS["bram"].xp == before  # earned nothing: not present for the kill
    finally:
        _teardown()


def test_an_offline_mate_earns_nothing_without_error():
    try:
        _hero("alia")
        _hero("bram")
        _band("alia", "bram")
        SESSIONS.pop("bram", None)  # bram drops without cleanup: still a member, now offline
        # the offline member is the only mate, so nothing is shared and no lookup crashes
        assert share_kill("alia", "greenhold", "a foe", 20, 0, 0) == ""
    finally:
        _teardown()


def test_a_callingless_mate_earns_nothing():
    try:
        _hero("alia")
        SESSIONS["bram"] = Session(player_id="bram", location="greenhold")  # no bind_calling
        _band("alia", "bram")
        assert share_kill("alia", "greenhold", "a foe", 20, 0, 0) == ""  # bram cannot advance
        assert SESSIONS["bram"].xp == 0
    finally:
        _teardown()
