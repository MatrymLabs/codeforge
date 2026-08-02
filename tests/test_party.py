"""Test twin for kernel/world/party.py -- the fellowship (the first shared-purpose primitive).

Acceptance: an invite plus a join forms a band; the roster shows it; party chat reaches the members;
leaving hands off leadership then disbands the last seat; disband dissolves it; a logout leaves the
band; members_in_room reports co-located mates. Refusal (fail loud, never a silent bad group): a
self-invite, an offline or already-partied target, a non-leader inviting, a full party, a join with
no invitation, and party actions while unpartied all return a refusal and mutate nothing.
"""

from __future__ import annotations

import forge
from kernel.world import events, party
from kernel.world.session import SESSIONS, Session


def _seat(name: str, location: str = "courtyard", *, sink: list[str] | None = None) -> Session:
    """Seat a live player, optionally with a capturing echo sink so party delivery is observable."""
    s = SESSIONS[name] = Session(player_id=name, location=location)
    if sink is not None:
        events.bind_echo(name, sink.append)
    return s


def _teardown() -> None:
    party._reset()
    for name in list(SESSIONS):
        events.unbind_echo(name)
        SESSIONS.pop(name, None)


# --- acceptance --------------------------------------------------------------------------------
def test_invite_then_join_forms_a_band_led_by_the_inviter():
    try:
        _seat("alia")
        _seat("bram")
        assert "invite bram" in party.invite("alia", "bram").lower()
        assert "join alia" in party.join("bram", "alia").lower()
        band = party.party_of("alia")
        assert band is not None and band is party.party_of("bram")
        assert band.leader == "alia" and set(band.members) == {"alia", "bram"}
    finally:
        _teardown()


def test_party_chat_reaches_the_members():
    inbox_b: list[str] = []
    try:
        _seat("alia")
        _seat("bram", sink=inbox_b)
        party.invite("alia", "bram")
        party.join("bram", "alia")
        own = party.party_say("alia", "Form up on me")
        assert "You: Form up on me" in own  # the speaker's own echo keeps case
        assert any("Form up on me" in line and "alia" in line.lower() for line in inbox_b)
    finally:
        _teardown()


def test_leaving_hands_off_leadership_then_disbands_the_last_seat():
    try:
        _seat("alia")
        _seat("bram")
        party.invite("alia", "bram")
        party.join("bram", "alia")
        party.leave("alia")  # the leader leaves
        band = party.party_of("bram")
        assert band is not None and band.leader == "bram"  # leadership handed off
        assert party.party_of("alia") is None
        assert "disbands" in party.leave("bram").lower()  # last member out -> party gone
        assert party.party_of("bram") is None
    finally:
        _teardown()


def test_disband_dissolves_the_band_for_everyone():
    try:
        _seat("alia")
        _seat("bram")
        party.invite("alia", "bram")
        party.join("bram", "alia")
        assert "disband" in party.disband("alia").lower()
        assert party.party_of("alia") is None and party.party_of("bram") is None
    finally:
        _teardown()


def test_a_logout_leaves_the_fellowship():
    try:
        _seat("alia")
        _seat("bram")
        _seat("cade")
        party.invite("alia", "bram")
        party.join("bram", "alia")
        party.invite("alia", "cade")
        party.join("cade", "alia")
        party.on_disconnect("alia")  # the leader logs out
        band = party.party_of("bram")
        assert band is not None and "alia" not in band.members and band.leader == "bram"
    finally:
        _teardown()


def test_members_in_room_reports_co_located_matesand_a_lone_player():
    try:
        _seat("alia", "greenhold")
        _seat("bram", "greenhold")
        _seat("cade", "the-deep")  # a mate elsewhere
        party.invite("alia", "bram")
        party.join("bram", "alia")
        party.invite("alia", "cade")
        party.join("cade", "alia")
        here = party.members_in_room("alia", "greenhold")
        assert set(here) == {"alia", "bram"} and "cade" not in here
        # an unpartied player is a party of one, in their own room
        _seat("dane", "greenhold")
        assert party.members_in_room("dane", "greenhold") == ["dane"]
    finally:
        _teardown()


def test_render_roster_marks_the_leader_and_offline_members():
    try:
        _seat("alia")
        _seat("bram")
        party.invite("alia", "bram")
        party.join("bram", "alia")
        SESSIONS.pop("bram", None)  # bram drops without cleanup: still a member, now offline
        out = party.render_party("alia")
        assert "(leader)" in out and "[offline]" in out
    finally:
        _teardown()


# --- refusal / hostile -------------------------------------------------------------------------
def test_a_self_invite_is_refused():
    try:
        _seat("alia")
        assert "yourself" in party.invite("alia", "alia").lower()
        assert party.party_of("alia") is None  # no band formed
    finally:
        _teardown()


def test_inviting_someone_offline_or_already_partied_is_refused():
    try:
        _seat("alia")
        assert "no one named" in party.invite("alia", "ghost").lower()
        _seat("bram")
        _seat("cade")
        party.invite("bram", "cade")
        party.join("cade", "bram")  # cade is now in bram's party
        assert "already in a party" in party.invite("alia", "cade").lower()
    finally:
        _teardown()


def test_only_the_leader_may_invite_or_disband():
    try:
        _seat("alia")
        _seat("bram")
        _seat("cade")
        party.invite("alia", "bram")
        party.join("bram", "alia")
        assert "only the party leader may invite" in party.invite("bram", "cade").lower()
        assert "only the party leader may disband" in party.disband("bram").lower()
    finally:
        _teardown()


def test_a_full_party_refuses_a_join():
    try:
        _seat("lead")
        members = [f"m{i}" for i in range(party.MAX_PARTY)]  # one more than fits with the leader
        for m in members:
            _seat(m)
            party.invite("lead", m)
        # fill to MAX_PARTY: the leader plus MAX_PARTY-1 joiners succeed, the last is refused
        results = [party.join(m, "lead") for m in members]
        assert any("full" in r.lower() for r in results)
        assert len(party.party_of("lead").members) == party.MAX_PARTY
    finally:
        _teardown()


def test_a_join_with_no_invitation_is_refused():
    try:
        _seat("alia")
        _seat("bram")
        assert "no invitation" in party.join("bram", "alia").lower()
    finally:
        _teardown()


def test_party_actions_while_unpartied_fail_loud():
    try:
        _seat("alia")
        assert "not in a party" in party.leave("alia").lower()
        assert "not in a party" in party.disband("alia").lower()
        assert "not in a party" in party.party_say("alia", "hello").lower()
        assert "not in a party" in party.render_party("alia").lower()
    finally:
        _teardown()


def test_empty_party_chat_is_refused():
    try:
        _seat("alia")
        _seat("bram")
        party.invite("alia", "bram")
        party.join("bram", "alia")
        assert "say what" in party.party_say("alia", "   ").lower()
    finally:
        _teardown()


# --- the verbs are reachable through the engine tick -------------------------------------------
def test_the_party_and_psay_verbs_are_reachable():
    try:
        _seat("alia")
        _seat("bram")
        assert "invite" in forge.handle_command(SESSIONS["alia"], "party invite bram").lower()
        forge.handle_command(SESSIONS["bram"], "party join alia")
        assert "1/" not in forge.handle_command(SESSIONS["alia"], "party")  # roster shows 2 members
        assert "You:" in forge.handle_command(SESSIONS["alia"], "psay Hold the line")
    finally:
        _teardown()


def test_party_changes_push_char_party_frames_to_every_member():
    from kernel.world import events
    from kernel.world.session import SESSIONS, Session

    frames: dict[str, list] = {"alia": [], "bram": []}
    try:
        SESSIONS["alia"] = Session(player_id="alia")
        SESSIONS["bram"] = Session(player_id="bram")
        events.bind_gmcp("alia", lambda pkg, data: frames["alia"].append((pkg, data)))
        events.bind_gmcp("bram", lambda pkg, data: frames["bram"].append((pkg, data)))
        party.invite("alia", "bram")
        party.join("bram", "alia")
        # both members got a Char.Party roster the instant bram joined
        assert frames["alia"][-1] == (
            "Char.Party",
            {"members": ["Alia", "Bram"], "leader": "Alia", "size": 2},
        )
        assert frames["bram"][-1] == (
            "Char.Party",
            {"members": ["Alia", "Bram"], "leader": "Alia", "size": 2},
        )
        party.leave("bram")
        assert frames["bram"][-1] == ("Char.Party", {})  # the leaver's panel cleared
        assert frames["alia"][-1] == (
            "Char.Party",
            {"members": ["Alia"], "leader": "Alia", "size": 1},
        )
    finally:
        party._reset()
        for name in ("alia", "bram"):
            events.unbind_gmcp(name)
            SESSIONS.pop(name, None)
