"""Test twin for parts/world/audit.py -- the tamper-evident admin/economy log.

Acceptance: record appends an entry that tail reads back with its who/what/detail; verify passes
on a clean chain and fails once a past record is tampered. Refusal: an unwritable audit path is
swallowed (logging must never abort the action it records). The path is quarantined to tmp.
"""

from __future__ import annotations

from parts.world import audit


def test_record_and_tail_round_trip_an_entry():
    audit.record("root", "grant", "ada -> wizard", ts="2026-07-29T00:00:00Z")
    entries = audit.tail(10)
    assert len(entries) == 1
    assert entries[0] == {
        "ts": "2026-07-29T00:00:00Z",
        "actor": "root",
        "action": "grant",
        "detail": "ada -> wizard",
    }


def test_tail_returns_the_most_recent_entries_oldest_first():
    for i in range(5):
        audit.record("root", "act", str(i), ts=f"2026-07-29T00:00:0{i}Z")
    entries = audit.tail(3)  # the last three of five
    assert [e["detail"] for e in entries] == ["2", "3", "4"]


def test_verify_passes_on_a_clean_chain():
    audit.record("root", "grant", "a", ts="2026-07-29T00:00:00Z")
    audit.record("root", "auction-buy", "b", ts="2026-07-29T00:00:01Z")
    assert audit.verify() is True


def test_verify_fails_when_a_past_record_is_tampered():
    audit.record("root", "grant", "clean", ts="2026-07-29T00:00:00Z")
    audit.record("root", "grant", "also clean", ts="2026-07-29T00:00:01Z")
    path = audit._audit_path()
    # tamper with the first record's payload directly in the ledger file
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("clean", "FORGED")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert audit.verify() is False  # the chain no longer links; tampering is detected


def test_an_unwritable_path_does_not_abort_the_action(monkeypatch, tmp_path):
    # point the ledger at a path whose PARENT is a file, so append raises OSError -- record must
    # swallow it, because failing to LOG must never crash the command that was being logged.
    bad = tmp_path / "afile"
    bad.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("CODEFORGE_AUDIT", str(bad / "nested" / "audit.jsonl"))
    audit.record("root", "grant", "should not raise")  # must not raise


def test_an_empty_log_tails_to_nothing():
    assert audit.tail() == [] and audit.verify() is True
