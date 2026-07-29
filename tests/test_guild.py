"""Test twin for parts/world/guild.py -- the PERSISTED player guild.

Acceptance: founding a guild persists it (the stored row carries the guild, so it survives a
relogin); invite + accept grows it; ranks gate invite/promote/disband; promotion transfers lead;
disband clears every member, including one offline; guild chat reaches online members; the roster
names all members with ranks. Refusal: an invalid or taken name, founding while guilded, a
non-officer inviting, accepting with no invite, a non-leader disbanding, and a leader leaving with
members still in the guild are all refused. Uses the real store, quarantined to tmp by conftest.
"""

from __future__ import annotations

from parts.world import events, guild
from parts.world.character_store import CharacterRecord
from parts.world.characters import _default_store, load_character, restore_character, save_character
from parts.world.session import SESSIONS, Session


def _hero(name: str, room: str = "hall") -> Session:
    s = SESSIONS[name] = Session(player_id=name, location=room, named=True)
    save_character(s)  # a real saved character, so the guild can persist onto its row
    return s


def _offline_member(name: str, guild_name: str, rank: str = "member") -> None:
    """A stored character in a guild who is NOT logged in (not in SESSIONS)."""
    _default_store().upsert_full(CharacterRecord(name=name, guild=guild_name, guild_rank=rank))


def _teardown() -> None:
    guild._reset()
    for name in list(SESSIONS):
        events.unbind_echo(name)
        SESSIONS.pop(name, None)


# --- acceptance: persistence ------------------------------------------------------------------
def test_founding_a_guild_persists_it():
    try:
        alia = _hero("alia")
        assert "found the guild" in guild.found(alia, "ironforge")
        assert alia.guild == "ironforge" and alia.guild_rank == "leader"
        assert guild._members("ironforge") == ["alia"]  # the persisted roster
        assert load_character("alia")["guild"] == "ironforge"  # written to the stored row
    finally:
        _teardown()


def test_the_guild_survives_a_relogin():
    try:
        guild.found(_hero("alia"), "ironforge")
        SESSIONS.pop("alia", None)  # log out
        casefile = load_character("alia")
        fresh = Session(player_id="alia")  # log back in from the saved casefile
        restore_character(fresh, casefile)
        assert fresh.guild == "ironforge" and fresh.guild_rank == "leader"
    finally:
        _teardown()


def test_invite_and_accept_grow_the_guild():
    try:
        guild.found(_hero("alia"), "ironforge")
        _hero("bram")
        assert "invite" in guild.invite(SESSIONS["alia"], "bram").lower()
        assert "join the guild" in guild.accept(SESSIONS["bram"])
        assert set(guild._members("ironforge")) == {"alia", "bram"}
    finally:
        _teardown()


def test_promoting_to_leader_transfers_leadership():
    try:
        guild.found(_hero("alia"), "ironforge")
        _hero("bram")
        guild.invite(SESSIONS["alia"], "bram")
        guild.accept(SESSIONS["bram"])
        guild.promote(SESSIONS["alia"], "bram")  # member -> officer
        assert SESSIONS["bram"].guild_rank == "officer"
        guild.promote(SESSIONS["alia"], "bram")  # officer -> leader (transfer)
        assert SESSIONS["bram"].guild_rank == "leader" and SESSIONS["alia"].guild_rank == "officer"
    finally:
        _teardown()


def test_disband_clears_every_member_including_an_offline_one():
    try:
        guild.found(_hero("alia"), "ironforge")
        _offline_member("cade", "ironforge")  # a guild-mate who is logged out
        assert set(guild._members("ironforge")) == {"alia", "cade"}
        assert "disband" in guild.disband(SESSIONS["alia"]).lower()
        assert guild._members("ironforge") == []  # gone for all
        assert load_character("cade")["guild"] == ""  # the offline member's row was cleared too
    finally:
        _teardown()


def test_guild_chat_reaches_online_members():
    inbox_b: list[str] = []
    try:
        guild.found(_hero("alia"), "ironforge")
        _hero("bram")
        events.bind_echo("bram", inbox_b.append)
        guild.invite(SESSIONS["alia"], "bram")
        guild.accept(SESSIONS["bram"])
        own = guild.guild_say(SESSIONS["alia"], "Muster at the gate")
        assert "You: Muster at the gate" in own
        assert any("Muster at the gate" in line for line in inbox_b)
    finally:
        _teardown()


def test_the_roster_lists_all_members_with_ranks():
    try:
        guild.found(_hero("alia"), "ironforge")
        _offline_member("cade", "ironforge")
        out = guild.render_guild(SESSIONS["alia"])
        assert "ironforge" in out and "(leader)" in out and "[offline]" in out
    finally:
        _teardown()


# --- refusal ----------------------------------------------------------------------------------
def test_bad_and_taken_names_and_double_membership_are_refused():
    try:
        alia = _hero("alia")
        assert "3 to 21" in guild.found(alia, "no")  # too short
        guild.found(alia, "ironforge")
        assert "already in a guild" in guild.found(alia, "second").lower()  # already guilded
        assert "already exists" in guild.found(_hero("bram"), "ironforge").lower()  # taken
    finally:
        _teardown()


def test_only_an_officer_may_invite_and_only_the_leader_disbands():
    try:
        guild.found(_hero("alia"), "ironforge")
        _hero("bram")
        guild.invite(SESSIONS["alia"], "bram")
        guild.accept(SESSIONS["bram"])  # bram is a plain member
        _hero("cade")
        assert "officer or the leader" in guild.invite(SESSIONS["bram"], "cade").lower()
        assert "only the guild leader" in guild.disband(SESSIONS["bram"]).lower()
    finally:
        _teardown()


def test_accept_with_no_invite_and_a_leader_leaving_with_members_are_refused():
    try:
        assert "no guild has invited" in guild.accept(_hero("alia")).lower()
        guild.found(SESSIONS["alia"], "ironforge")
        _offline_member("cade", "ironforge")
        assert "promote a new leader" in guild.leave(SESSIONS["alia"]).lower()
    finally:
        _teardown()


# --- the verbs are reachable through the engine tick ------------------------------------------
def test_the_guild_and_gsay_verbs_are_reachable():
    import forge

    try:
        alia = _hero("alia")
        assert "found the guild" in forge.handle_command(alia, "guild found ironforge")
        assert "[Guild] You:" in forge.handle_command(alia, "gsay hail")
    finally:
        _teardown()
