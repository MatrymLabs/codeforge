"""Test twin for kernel/world/guild_store.py -- the guild treasury row.

Acceptance: ensure opens a row at zero, adjust adds and subtracts and returns the new balance, coins
reads it, remove drops it. Refusal / floor: adjust never lets the balance fall below zero, and coins
reads zero for a guild with no row. Uses the real table, quarantined to tmp by conftest.
"""

from __future__ import annotations

from kernel.world import guild_store


def test_ensure_opens_a_treasury_at_zero_and_is_idempotent():
    guild_store.ensure("ironforge")
    assert guild_store.coins("ironforge") == 0
    guild_store.ensure("ironforge")  # again: no error, still zero
    assert guild_store.coins("ironforge") == 0


def test_adjust_adds_and_subtracts_and_returns_the_new_balance():
    guild_store.ensure("ironforge")
    assert guild_store.adjust("ironforge", 50) == 50
    assert guild_store.adjust("ironforge", -20) == 30
    assert guild_store.coins("ironforge") == 30


def test_adjust_creates_the_row_if_it_is_missing():
    assert guild_store.coins("newborn") == 0  # no row yet
    assert guild_store.adjust("newborn", 15) == 15  # adjust opens it


def test_the_balance_never_falls_below_zero():
    guild_store.ensure("ironforge")
    guild_store.adjust("ironforge", 10)
    assert guild_store.adjust("ironforge", -999) == 0  # floored, not negative


def test_remove_drops_the_row():
    guild_store.ensure("ironforge")
    guild_store.adjust("ironforge", 40)
    guild_store.remove("ironforge")
    assert guild_store.coins("ironforge") == 0  # gone
    guild_store.remove("ironforge")  # again: a clean no-op


def test_coins_reads_zero_for_a_guild_with_no_row():
    assert guild_store.coins("nonexistent") == 0
