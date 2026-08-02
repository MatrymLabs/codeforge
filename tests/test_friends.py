"""Test twin for kernel/world/friends.py -- a hero's personal friends list.

Acceptance: a real hero is added and appears on the list; render marks who is online; remove drops a
name; the list survives a save + restore. Refusal: a missing name, yourself, an unknown hero, a
duplicate, a full list, and removing someone never added are all refused. One-directional: adding
someone does NOT add you to their list. Real store, quarantined to tmp by conftest.
"""

from __future__ import annotations

from kernel.world import events, friends
from kernel.world.character_store import CharacterRecord
from kernel.world.characters import (
    _default_store,
    load_character,
    restore_character,
    save_character,
)
from kernel.world.session import SESSIONS, Session


def _hero(name: str = "alia") -> Session:
    """A saved, logged-in hero (save_character needs a named session)."""
    s = SESSIONS[name] = Session(player_id=name, location="hall", named=True)
    save_character(s)
    return s


def _other(name: str = "bram") -> None:
    """A real saved hero who is NOT logged in (a friend may be offline)."""
    _default_store().upsert_full(CharacterRecord(name=name))


def _teardown() -> None:
    for name in list(SESSIONS):
        events.unbind_echo(name)
        SESSIONS.pop(name, None)


# --- acceptance -------------------------------------------------------------------------------
def test_a_real_hero_is_added_to_the_list():
    try:
        alia = _hero()
        _other("bram")
        out = friends.add(alia, "bram")
        assert "add Bram" in out
        assert alia.friends == ["bram"]
    finally:
        _teardown()


def test_render_marks_online_and_offline():
    try:
        alia = _hero("alia")
        _hero("cade")  # cade is online
        _other("bram")  # bram is offline
        friends.add(alia, "bram")
        friends.add(alia, "cade")
        out = friends.render(alia)
        assert "Cade (online)" in out and "Bram (offline)" in out
        assert "1/2 online" in out
    finally:
        _teardown()


def test_remove_drops_a_name():
    try:
        alia = _hero()
        _other("bram")
        friends.add(alia, "bram")
        assert "remove Bram" in friends.remove(alia, "bram")
        assert alia.friends == []
    finally:
        _teardown()


def test_the_list_survives_a_save_and_restore():
    try:
        alia = _hero()
        _other("bram")
        friends.add(alia, "bram")  # add() already saves
        # a fresh session for the same hero, restored from the store, keeps the roster
        reborn = SESSIONS["alia"] = Session(player_id="alia", named=True)
        restore_character(reborn, load_character("alia"))
        assert reborn.friends == ["bram"]
    finally:
        _teardown()


def test_befriending_is_one_directional():
    try:
        alia = _hero("alia")
        bram = _hero("bram")
        friends.add(alia, "bram")
        assert alia.friends == ["bram"]
        assert bram.friends == []  # bram was not enlisted into anything
    finally:
        _teardown()


# --- refusal ----------------------------------------------------------------------------------
def test_a_missing_name_and_yourself_are_refused():
    try:
        alia = _hero()
        assert "whom" in friends.add(alia, "").lower()
        assert "own best company" in friends.add(alia, "alia").lower()
        assert alia.friends == []
    finally:
        _teardown()


def test_an_unknown_hero_is_refused():
    try:
        alia = _hero()
        assert "no hero named" in friends.add(alia, "ghost").lower()
        assert alia.friends == []
    finally:
        _teardown()


def test_a_duplicate_is_refused():
    try:
        alia = _hero()
        _other("bram")
        friends.add(alia, "bram")
        assert "already on your friends" in friends.add(alia, "bram").lower()
        assert alia.friends == ["bram"]
    finally:
        _teardown()


def test_a_full_list_is_refused():
    try:
        alia = _hero()
        alia.friends = [f"pal{i}" for i in range(friends.MAX_FRIENDS)]
        _other("bram")
        assert "list is full" in friends.add(alia, "bram").lower()
    finally:
        _teardown()


def test_removing_someone_never_added_is_refused():
    try:
        alia = _hero()
        assert "not on your friends" in friends.remove(alia, "bram").lower()
    finally:
        _teardown()


def test_serialize_and_restore_round_trip():
    s = Session(player_id="alia")
    s.friends = ["bram", "cade"]
    blob = friends.serialize(s)
    assert blob == "bram,cade"
    fresh = Session(player_id="alia")
    friends.restore(fresh, blob)
    assert fresh.friends == ["bram", "cade"]
    # a forgiving restore drops blank entries
    friends.restore(fresh, "")
    assert fresh.friends == []


# --- the verb is reachable through the engine tick --------------------------------------------
def test_the_friend_verb_is_reachable():
    import forge

    try:
        alia = _hero()
        _other("bram")
        assert "add Bram" in forge.handle_command(alia, "friend add bram")
        assert "friends" in forge.handle_command(alia, "friends").lower()
    finally:
        _teardown()
