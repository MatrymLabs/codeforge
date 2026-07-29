"""Test twin for parts/world/mail_store.py -- the stored-letter adapter.

Acceptance: a sent letter lands in the recipient's inbox (newest first), count reports the total,
mark_read flips the flag, delete removes it. Refusal / safety: delete is scoped to the recipient, so
one hero cannot remove another's mail by id; an inbox read for a stranger is empty. Real table,
quarantined to tmp by conftest.
"""

from __future__ import annotations

from parts.world import mail_store

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
