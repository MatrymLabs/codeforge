"""Test twin for parts/world/mail.py -- asynchronous letters between heroes.

Acceptance: a letter to a real hero is sent and lands in their inbox; the inbox lists newest-first
with unread marked; read shows the body and clears the unread mark; delete discards it; an online
recipient is nudged. Refusal: a missing recipient/message, an unknown hero, an over-long body, and a
full inbox are all refused. Real store, quarantined to tmp by conftest.
"""

from __future__ import annotations

import copy

import pytest

from parts.world import events, mail, mail_store
from parts.world import items as _items
from parts.world.character_store import CharacterRecord
from parts.world.characters import _default_store, save_character
from parts.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def _fresh_items():
    """Snapshot ITEMS so a gift test's cloned items never leak into the next test."""
    snap = copy.deepcopy(_items.ITEMS)
    yield
    _items.ITEMS.clear()
    _items.ITEMS.update(snap)


def _sender(name: str = "alia") -> Session:
    s = SESSIONS[name] = Session(player_id=name, location="hall", named=True)
    save_character(s)
    return s


def _recipient(name: str = "bram") -> None:
    """A real saved hero who is NOT logged in (mail must reach the offline)."""
    _default_store().upsert_full(CharacterRecord(name=name))


def _teardown() -> None:
    for name in list(SESSIONS):
        events.unbind_echo(name)
        SESSIONS.pop(name, None)


# --- acceptance -------------------------------------------------------------------------------
def test_a_letter_to_a_real_hero_is_delivered():
    try:
        alia = _sender()
        _recipient("bram")
        out = mail.send(alia, "bram Meet me at the gate")
        assert "sent to Bram" in out
        box = mail_store.inbox("bram")
        assert len(box) == 1 and box[0].body == "Meet me at the gate" and box[0].sender == "alia"
    finally:
        _teardown()


def test_the_inbox_lists_reads_and_deletes():
    try:
        _sender()
        mail_store.send("alia", "bram", "hello alia", sent_utc="2026-07-28T12:00:00Z")
        listing = mail.render_inbox(SESSIONS["alia"])
        assert "*1. from Bram" in listing  # unread star
        body = mail.read_mail(SESSIONS["alia"], "1")
        assert "hello alia" in body
        assert mail_store.inbox("alia")[0].read is True  # now marked read
        assert "discarded" in mail.delete_mail(SESSIONS["alia"], "1")
        assert mail_store.inbox("alia") == []
    finally:
        _teardown()


def test_an_online_recipient_is_nudged():
    inbox_b: list[str] = []
    try:
        alia = _sender("alia")
        _sender("bram")  # bram is online
        events.bind_echo("bram", inbox_b.append)
        mail.send(alia, "bram ping")
        assert any("new mail from Alia" in line for line in inbox_b)
    finally:
        _teardown()


# --- refusal ----------------------------------------------------------------------------------
def test_a_letter_needs_a_recipient_and_a_body():
    try:
        alia = _sender()
        assert "whom, and what" in mail.send(alia, "bram").lower()  # no message
        assert "whom, and what" in mail.send(alia, "").lower()  # nothing
    finally:
        _teardown()


def test_writing_to_an_unknown_hero_is_refused():
    try:
        alia = _sender()
        assert "no hero named" in mail.send(alia, "ghost hello").lower()
        assert mail_store.count("ghost") == 0
    finally:
        _teardown()


def test_an_over_long_letter_is_refused():
    try:
        alia = _sender()
        _recipient("bram")
        assert "at most" in mail.send(alia, "bram " + "x" * (mail.MAX_BODY + 1)).lower()
    finally:
        _teardown()


def test_a_full_inbox_returns_the_letter():
    try:
        alia = _sender()
        _recipient("bram")
        for i in range(mail.MAX_INBOX):
            mail_store.send("bram", "alia", f"n{i}", sent_utc="2026-07-28T12:00:00Z")
        assert "inbox is full" in mail.send(alia, "bram one too many").lower()
    finally:
        _teardown()


# --- the verb is reachable through the engine tick --------------------------------------------
def test_the_mail_verb_is_reachable():
    import forge

    try:
        alia = _sender()
        _recipient("bram")
        assert "sent to Bram" in forge.handle_command(alia, "mail send bram hi there")
        assert "inbox" in forge.handle_command(alia, "mail").lower()
    finally:
        _teardown()


# --- item attachments (mail gift / mail claim) --------------------------------------------------
def test_gift_mails_a_carried_item_and_claim_brings_it_back():
    from parts.world.items import carrier, items_in, prototype_of

    try:
        alia = _sender("alia")
        _recipient("bram")  # bram exists, offline
        _items.clone("forge_wrench", carrier("alia"))
        out = mail.gift(alia, "bram wrench")
        assert "mail" in out.lower() and "bram" in out.lower()
        # it left alia's bag
        assert [prototype_of(i) for i in items_in(carrier("alia"))].count("forge_wrench") == 0
        # it rides bram's letter as a parcel
        letter = mail_store.inbox("bram")[0]
        assert letter.attachment is not None and letter.attachment["prototype"] == "forge_wrench"
        # bram logs in and claims it into his bag
        bram = SESSIONS["bram"] = Session(player_id="bram", location="hall", named=True)
        assert "claim" in mail.claim(bram, "1").lower()
        assert any(prototype_of(i) == "forge_wrench" for i in items_in(carrier("bram")))
        assert mail_store.inbox("bram")[0].attachment is None  # claimed once, gone
    finally:
        _teardown()


def test_gift_refuses_a_bad_target_uncarried_or_worn_item():
    from parts.world.items import carrier

    try:
        alia = _sender("alia")
        assert "gift whom" in mail.gift(alia, "bram").lower()  # no item
        assert "no hero named" in mail.gift(alia, "ghost forge_wrench").lower()
        _recipient("bram")
        assert "aren't carrying" in mail.gift(alia, "bram dragon").lower()
        iid = _items.clone("forge_wrench", carrier("alia"))
        alia.equipped["weapon"] = iid  # worn
        assert "worn" in mail.gift(alia, "bram wrench").lower()
    finally:
        _teardown()


def test_claiming_a_letter_with_no_parcel_is_refused():
    try:
        alia = _sender("alia")
        mail_store.send("alia", "bram", "just words", sent_utc="2026-07-28T12:00:00Z")
        assert "no parcel" in mail.claim(alia, "1").lower()
    finally:
        _teardown()
