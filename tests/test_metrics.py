"""Test twin for parts/world/metrics.py -- the live-ops storage snapshot.

Acceptance: an empty world reports zeros; after seeding characters (with coin), a guild treasury, an
auction listing, mail, and a ban, snapshot reports the right counts and the coin-in-circulation sum
(purses + treasuries); render labels them. Read-only: it mutates nothing. Real store, tmp.
"""

from __future__ import annotations

from parts.world import auction_store, bans, guild_store, mail_store, metrics
from parts.world.characters import put_record


def test_an_empty_world_reports_zeros():
    snap = metrics.snapshot()
    assert snap["characters"] == 0 and snap["coins_in_circulation"] == 0
    assert snap["guilds"] == 0 and snap["auction_listings"] == 0 and snap["bans"] == 0


def test_snapshot_counts_and_sums_across_storage():
    put_record("ada", {"job": "vanguard", "level": 5, "coins": 100})
    put_record("bram", {"job": "vanguard", "level": 3, "coins": 40})
    guild_store.ensure("ironforge")
    guild_store.adjust("ironforge", 60)  # a guild treasury of 60
    auction_store.create("ada", {"prototype": "forge_wrench", "name": "x", "mods": {}}, 25, 900)
    mail_store.send("bram", "ada", "hi", sent_utc="2026-07-29T00:00:00Z")
    bans.ban("griefer", "spite", "root")

    snap = metrics.snapshot()
    assert snap["characters"] == 2
    assert snap["coins_in_circulation"] == 200  # 100 + 40 purses + 60 treasury
    assert snap["guild_treasuries"] == 60 and snap["guilds"] == 1
    assert snap["auction_listings"] == 1
    assert snap["mail_in_flight"] == 1
    assert snap["bans"] == 1


def test_render_labels_the_snapshot():
    put_record("ada", {"job": "vanguard", "coins": 10})
    out = metrics.render()
    assert "World metrics" in out and "Coins in circulation" in out and "10" in out
