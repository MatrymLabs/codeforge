"""Test twin for parts/world/guild.py -- the PERSISTED player guild.

Acceptance: founding a guild persists it (the stored row carries the guild, so it survives a
relogin); invite + accept grows it; ranks gate invite/promote/disband; promotion transfers lead;
disband clears every member, including one offline; guild chat reaches online members; the roster
names all members with ranks. Refusal: an invalid or taken name, founding while guilded, a
non-officer inviting, accepting with no invite, a non-leader disbanding, and a leader leaving with
members still in the guild are all refused. Uses the real store, quarantined to tmp by conftest.
"""

from __future__ import annotations

import copy

import pytest

from parts.world import events, guild, guild_store
from parts.world import items as _items
from parts.world.character_store import CharacterRecord
from parts.world.characters import _default_store, load_character, restore_character, save_character
from parts.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def _fresh_items():
    """Snapshot ITEMS so a vault test's cloned items never leak into the next test."""
    snap = copy.deepcopy(_items.ITEMS)
    yield
    _items.ITEMS.clear()
    _items.ITEMS.update(snap)


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


# --- the guild bank (a persisted shared treasury) ---------------------------------------------
def test_a_member_deposits_and_the_treasury_persists():
    try:
        alia = _hero("alia")
        alia.coins = 100
        guild.found(alia, "ironforge")
        out = guild.bank_deposit(alia, "40")
        assert "deposit 40 coins" in out.lower()
        assert alia.coins == 60  # left the purse
        assert guild_store.coins("ironforge") == 40  # persisted in the treasury row
    finally:
        _teardown()


def test_only_an_officer_may_withdraw_and_never_beyond_the_balance():
    try:
        guild.found(
            _hero(
                "alia",
            ),
            "ironforge",
        )
        SESSIONS["alia"].coins = 100
        guild.bank_deposit(SESSIONS["alia"], "50")
        # a plain member cannot drain the treasury
        _hero("bram")
        guild.invite(SESSIONS["alia"], "bram")
        guild.accept(SESSIONS["bram"])
        assert "officer or the leader" in guild.bank_withdraw(SESSIONS["bram"], "10").lower()
        # the leader can, but never beyond the balance
        assert "does not hold that many" in guild.bank_withdraw(SESSIONS["alia"], "999").lower()
        out = guild.bank_withdraw(SESSIONS["alia"], "30")
        assert "withdraw 30" in out.lower() and guild_store.coins("ironforge") == 20
        assert SESSIONS["alia"].coins == 80  # 100 - 50 deposited + 30 withdrawn
    finally:
        _teardown()


def test_depositing_more_than_you_hold_is_refused():
    try:
        alia = _hero("alia")
        alia.coins = 10
        guild.found(alia, "ironforge")
        assert "do not have that many" in guild.bank_deposit(alia, "50").lower()
        assert guild_store.coins("ironforge") == 0
    finally:
        _teardown()


def test_disband_removes_the_treasury_row():
    try:
        alia = _hero("alia")
        alia.coins = 100
        guild.found(alia, "ironforge")
        guild.bank_deposit(alia, "40")
        guild.disband(alia)
        assert guild_store.coins("ironforge") == 0  # the row is gone
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


# --- the guild item-vault -----------------------------------------------------------------------
def _guilded_pair():
    """A founded guild: alia (leader) + bram (member), both online."""
    guild.found(_hero("alia"), "ironforge")
    _hero("bram")  # bram must be seated before he can be invited/accept
    guild.invite(SESSIONS["alia"], "bram")
    guild.accept(SESSIONS["bram"])
    return SESSIONS["alia"], SESSIONS["bram"]


def test_a_member_can_deposit_to_the_guild_vault():
    from parts.world import loose_store
    from parts.world.items import carrier

    try:
        _alia, bram = _guilded_pair()
        _items.clone("forge_wrench", carrier("bram"))
        out = guild.vault_deposit(bram, "wrench")
        assert "deposit" in out.lower()
        assert len(loose_store.contents("guildvault:ironforge")) == 1
        assert "ironforge' vault (1)" in guild.vault_render(bram)
    finally:
        _teardown()


def test_only_an_officer_may_withdraw_from_the_vault():
    from parts.world.items import carrier

    try:
        alia, bram = _guilded_pair()  # alia leader, bram member
        _items.clone("forge_wrench", carrier("bram"))
        guild.vault_deposit(bram, "wrench")
        # a plain member is refused
        assert "officer or the leader" in guild.vault_withdraw(bram, "1").lower()
        # the leader may take it
        out = guild.vault_withdraw(alia, "1")
        assert "withdraw" in out.lower()
        assert any(
            _items.prototype_of(i) == "forge_wrench" for i in _items.items_in(carrier("alia"))
        )
    finally:
        _teardown()


def test_the_guild_vault_is_scoped_to_its_guild():
    from parts.world import loose_store
    from parts.world.items import carrier

    try:
        _a, bram = _guilded_pair()
        _items.clone("forge_wrench", carrier("bram"))
        guild.vault_deposit(bram, "wrench")
        # a different guild's vault is empty and untouched
        assert loose_store.contents("guildvault:otherclan") == []
        assert len(loose_store.contents("guildvault:ironforge")) == 1
    finally:
        _teardown()


def test_vault_ops_refuse_the_guildless():
    try:
        loner = _hero("loner")
        assert "not in a guild" in guild.vault_render(loner).lower()
        assert "not in a guild" in guild.vault_deposit(loner, "wrench").lower()
        assert "not in a guild" in guild.vault_withdraw(loner, "1").lower()
    finally:
        _teardown()


def test_the_guild_vault_verb_is_reachable():
    import forge
    from parts.world.items import carrier

    try:
        _a, bram = _guilded_pair()
        _items.clone("forge_wrench", carrier("bram"))
        assert "deposit" in forge.handle_command(bram, "guild vault deposit wrench").lower()
        assert "vault" in forge.handle_command(bram, "guild vault").lower()
    finally:
        _teardown()
