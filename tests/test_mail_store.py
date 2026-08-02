"""Test twin for kernel/world/mail_store.py -- the stored-letter adapter.

Acceptance: a sent letter lands in the recipient's inbox (newest first), count reports the total,
mark_read flips the flag, delete removes it. Refusal / safety: delete is scoped to the recipient, so
one hero cannot remove another's mail by id; an inbox read for a stranger is empty. Real table,
quarantined to tmp by conftest.
"""

from __future__ import annotations

from kernel.world import mail_store

_T = "2026-07-28T12:00:00Z"


def test_a_sent_letter_lands_in_the_inbox_newest_first():
    mail_store.send("alia", "bram", "first", sent_utc=_T)
    mail_store.send("alia", "cade", "second", sent_utc=_T)
    box = mail_store.inbox("alia")
    assert [ltr.body for ltr in box] == ["second", "first"]  # newest first
    assert box[0].sender == "cade" and box[0].read is False


def test_count_reports_the_inbox_size():
    assert mail_store.count("alia") == 0
    mail_store.send("alia", "bram", "hi", sent_utc=_T)
    assert mail_store.count("alia") == 1


def test_mark_read_flips_the_flag():
    mail_store.send("alia", "bram", "hi", sent_utc=_T)
    letter_id = mail_store.inbox("alia")[0].id
    mail_store.mark_read(letter_id)
    assert mail_store.inbox("alia")[0].read is True


def test_delete_removes_a_letter_from_its_own_inbox():
    mail_store.send("alia", "bram", "hi", sent_utc=_T)
    letter_id = mail_store.inbox("alia")[0].id
    assert mail_store.delete(letter_id, "alia") is True
    assert mail_store.inbox("alia") == []


def test_delete_is_scoped_to_the_recipient():
    mail_store.send("alia", "bram", "private", sent_utc=_T)
    letter_id = mail_store.inbox("alia")[0].id
    # cade tries to delete alia's letter by id: refused, nothing removed
    assert mail_store.delete(letter_id, "cade") is False
    assert len(mail_store.inbox("alia")) == 1


def test_a_stranger_has_an_empty_inbox():
    assert mail_store.inbox("nobody") == [] and mail_store.count("nobody") == 0


def test_unread_count_tallies_only_unread_letters():
    mail_store.send("alia", "bram", "one", sent_utc=_T)
    mail_store.send("alia", "bram", "two", sent_utc=_T)
    assert mail_store.unread_count("alia") == 2
    mail_store.mark_read(mail_store.inbox("alia")[0].id)
    assert mail_store.unread_count("alia") == 1  # one read, one still unread
    assert mail_store.unread_count("nobody") == 0


def test_a_letter_can_carry_and_yield_an_item_attachment():
    snap = {
        "prototype": "warm_cloak",
        "name": "a Cruel cloak [rare]",
        "mods": {"MAG DEF": 8},
        "rarity": "rare",
    }
    mail_store.send("ada", "bram", "a gift", sent_utc=_T, attachment=snap)
    letter = mail_store.inbox("ada")[0]
    assert letter.attachment == snap  # the parcel rides the letter
    claimed = mail_store.claim(letter.id, "ada")
    assert claimed == snap
    # the letter stays but the parcel is gone: a second claim yields nothing (no dupe)
    assert mail_store.inbox("ada")[0].attachment is None
    assert mail_store.claim(letter.id, "ada") is None


def test_claim_is_scoped_to_the_recipient():
    snap = {"prototype": "forge_wrench", "name": "a wrench", "mods": {}, "rarity": "common"}
    mail_store.send("ada", "bram", "yours", sent_utc=_T, attachment=snap)
    letter_id = mail_store.inbox("ada")[0].id
    assert mail_store.claim(letter_id, "cade") is None  # not cade's to claim
    assert mail_store.inbox("ada")[0].attachment == snap  # still ada's, unclaimed


def test_a_plain_letter_has_no_attachment():
    mail_store.send("ada", "bram", "just words", sent_utc=_T)
    assert mail_store.inbox("ada")[0].attachment is None
    assert mail_store.claim(mail_store.inbox("ada")[0].id, "ada") is None
