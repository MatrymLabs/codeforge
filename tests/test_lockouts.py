"""Test twin for parts/world/lockouts.py -- daily reset markers (the endgame cap).

Acceptance: the first claim of a key on a day succeeds and stamps it; a second claim the same day is
refused; a new day clears the way to claim again; is_locked reads the mark; serialize/deserialize
round-trip a ledger. Refusal / robustness: a blank or garbled stored ledger restores empty (a lost
lockout never locks a hero out), and a non-dict payload is rejected.
"""

from __future__ import annotations

from parts.world import lockouts
from parts.world.session import Session


def test_the_first_claim_of_the_day_succeeds_then_is_refused():
    s = Session(player_id="bram")
    assert lockouts.claim(s, "boss:reaver", "2026-07-29") is True  # first kill today
    assert lockouts.claim(s, "boss:reaver", "2026-07-29") is False  # already claimed
    assert lockouts.is_locked(s, "boss:reaver", "2026-07-29") is True


def test_a_new_day_reopens_the_claim():
    s = Session(player_id="bram")
    lockouts.claim(s, "boss:reaver", "2026-07-29")
    assert lockouts.claim(s, "boss:reaver", "2026-07-30") is True  # the date rolled
    assert lockouts.is_locked(s, "boss:reaver", "2026-07-29") is False  # yesterday's mark is stale


def test_keys_lock_independently():
    s = Session(player_id="bram")
    lockouts.claim(s, "boss:reaver", "2026-07-29")
    assert lockouts.claim(s, "boss:golem", "2026-07-29") is True  # a different boss, own lock


def test_is_locked_is_false_for_an_unclaimed_key():
    assert lockouts.is_locked(Session(player_id="bram"), "boss:reaver", "2026-07-29") is False


def test_serialize_round_trips_a_ledger():
    ledger = {"boss:reaver": "2026-07-29", "boss:golem": "2026-07-28"}
    assert lockouts.deserialize(lockouts.serialize(ledger)) == ledger


def test_an_empty_ledger_serializes_to_the_blank_string():
    assert lockouts.serialize({}) == ""
    assert lockouts.deserialize("") == {}


def test_a_garbled_ledger_restores_empty_not_crashing():
    assert lockouts.deserialize("{not json") == {}  # a lost lockout is forgiving, never a crash
    assert lockouts.deserialize("[1, 2, 3]") == {}  # a non-dict payload is rejected


def test_today_utc_is_an_iso_date():
    day = lockouts.today_utc()
    assert len(day) == 10 and day[4] == "-" and day[7] == "-"  # YYYY-MM-DD
